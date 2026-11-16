"""
Game day: follow the family's teams and celebrate when they score.

  settings.teams       [{league, id, name, abbr, color, alt}]   (picked on the phone: Settings > Game day)
  settings.gameLights  [light entity ids] that flash in the team's colours, then go back to how they were
  settings.gameFlash / gameSpeak / gameChip   lights / wall voice + banner / live score chip on the wall
  settings.gameDelay   seconds to wait before celebrating (streams run behind the live score: no spoilers)

Scores come from ESPN's public scoreboard (no key). One small thread: every 20 s while one of our games is live,
every 5 min otherwise, nothing at all when no team is picked. A score change for OUR team -> wall announcement (kind
"score:#colour", the wall bursts in the team colour and says it) + lights. Never flashes lights while the house is
asleep (after Good night, or 23:30-08:00): nothing at all happens then.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from . import ha_svc

API = "https://site.api.espn.com/apis/site/v2/sports"
LEAGUES = {                                    # key -> (ESPN path, label, extra scoreboard query)
    "nfl": ("football/nfl", "NFL", ""),
    "cfb": ("football/college-football", "College football", "groups=80&limit=300"),
    "nba": ("basketball/nba", "NBA", ""),
    "cbb": ("basketball/mens-college-basketball", "College basketball", "groups=50&limit=400"),
    "mlb": ("baseball/mlb", "MLB", ""),
    "nhl": ("hockey/nhl", "NHL", ""),
}
_S: dict = {"games": [], "at": 0.0, "last": {}, "teams": {}, "error": "", "flash": {}, "told": []}


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def _get(url: str) -> dict:
    r = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (familyhub)"})
    with urllib.request.urlopen(r, timeout=8) as resp:
        return json.loads(resp.read().decode())


def _hex(c: str, default: str) -> str:
    c = str(c or "").strip().lstrip("#")
    return "#" + c.lower() if len(c) == 6 and all(x in "0123456789abcdefABCDEF" for x in c) else default


def league_teams(league: str) -> list:
    """Every team in a league (for the picker). Kept a day."""
    if league not in LEAGUES:
        return []
    hit = _S["teams"].get(league)
    if hit and time.time() - hit[0] < 86400:
        return hit[1]
    d = _get(f"{API}/{LEAGUES[league][0]}/teams?limit=1000")
    out = []
    for lg in (d.get("sports") or [{}])[0].get("leagues") or []:
        for t in lg.get("teams") or []:
            t = t.get("team") or {}
            if t.get("id"):
                out.append({"league": league, "id": str(t["id"]), "name": t.get("displayName") or t.get("name") or "?",
                            "short": t.get("shortDisplayName") or t.get("name") or "",
                            "abbr": t.get("abbreviation") or "", "color": _hex(t.get("color"), "#3b82f6"),
                            "alt": _hex(t.get("alternateColor"), "#ffffff")})
    out.sort(key=lambda t: t["name"])
    _S["teams"][league] = (time.time(), out)
    return out


def _mine(s: dict) -> list:
    return [t for t in (s.get("teams") or []) if isinstance(t, dict) and t.get("league") in LEAGUES and t.get("id")]


def _parse(league: str, d: dict, mine: dict) -> list:
    """Scoreboard JSON -> our games: {key, league, team, opp, us, them, state pre|in|post, detail, start, won}."""
    out = []
    for ev in d.get("events") or []:
        comp = (ev.get("competitions") or [{}])[0]
        cs = comp.get("competitors") or []
        if len(cs) != 2:
            continue
        for i, c in enumerate(cs):
            tid = str((c.get("team") or {}).get("id") or "")
            if tid not in mine:
                continue
            o = cs[1 - i]
            st = (ev.get("status") or comp.get("status") or {}).get("type") or {}

            def pts(x):
                try:
                    return int(x.get("score") or 0)
                except (TypeError, ValueError):
                    return 0
            out.append({"key": f"{league}:{ev.get('id')}:{tid}", "event": str(ev.get("id") or ""), "league": league, "team": mine[tid],
                        "opp": (o.get("team") or {}).get("shortDisplayName") or (o.get("team") or {}).get("displayName") or "?",
                        "opp_abbr": (o.get("team") or {}).get("abbreviation") or "",
                        "us": pts(c), "them": pts(o), "home": c.get("homeAway") == "home",
                        "state": st.get("state") or "pre", "detail": st.get("shortDetail") or st.get("detail") or "",
                        "start": ev.get("date") or "", "won": bool(c.get("winner")) if st.get("state") == "post" else None})
    return out


def fetch(s: dict | None = None) -> list:
    s = s if s is not None else _settings()
    mine = _mine(s)
    games = []
    for league in sorted({t["league"] for t in mine}):
        path, _label, q = LEAGUES[league]
        d = _get(f"{API}/{path}/scoreboard" + (f"?{q}" if q else ""))
        games += _parse(league, d, {str(t["id"]): t for t in mine if t["league"] == league})
    return games


def _what(league: str, gained: int) -> str:
    if league in ("nfl", "cfb"):
        return {1: "Extra point", 2: "Two points", 3: "Field goal", 6: "Touchdown", 7: "Touchdown", 8: "Touchdown"}.get(gained, "Score")
    if league == "nhl":
        return "Goal"
    if league == "mlb":
        return "Run scored" if gained == 1 else f"{gained} runs"
    return "Score"


def _asleep() -> bool:
    now = datetime.now()
    if now.hour * 60 + now.minute >= 23 * 60 + 30 or now.hour < 8:
        return True
    try:
        from . import display_svc
        return bool((display_svc.state() or {}).get("sleep_mode"))
    except Exception:
        return False


def _say(title: str, body: str, color: str):
    from ..db import get_db
    with get_db() as conn:
        conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                     (title, body, f"score:{color}", datetime.now().isoformat()))
    try:
        from . import ha_live
        ha_live.bump()                      # the wall picks it up right away over its live stream
    except Exception:
        pass


def _rgb(c: str) -> list:
    c = c.lstrip("#")
    return [int(c[i:i + 2], 16) for i in (0, 2, 4)]


def _restore(e: str, st: dict | None):
    attrs = (st or {}).get("attributes") or {}
    if not st or st.get("state") != "on":
        ha_svc.call_service("light", "turn_off", e)
        return
    extra = {"brightness": attrs.get("brightness") or 255}
    if attrs.get("color_mode") == "color_temp" and attrs.get("color_temp_kelvin"):
        extra["color_temp_kelvin"] = attrs["color_temp_kelvin"]
    elif attrs.get("rgb_color"):
        extra["rgb_color"] = list(attrs["rgb_color"])[:3]
    ha_svc.call_service("light", "turn_on", e, extra)


def _flash_one(e: str, a: list, b: list, rounds: int):
    """One light, on its own thread. Fast lights (Zigbee) blink between the two colours. Slow or cloud lights
    (Govee and the like drop or rate-limit rapid commands) just turn the team colour, hold it, and go back."""
    try:
        st = None if ha_svc.demo_mode() else ha_svc._request(f"/api/states/{e}")
    except Exception:
        st = None
    total = rounds * 2 * 0.7
    t0 = time.time()
    try:
        r = ha_svc.call_service("light", "turn_on", e, {"rgb_color": a, "brightness": 255})
        name = (e + " " + str(((st or {}).get("attributes") or {}).get("friendly_name", ""))).lower()
        slow = (not r.get("ok")) or time.time() - t0 > 0.45 or "govee" in name
        _S["flash"][e] = ("held" if slow else "blinked") if r.get("ok") else ("failed: " + str(r.get("reason", "")))
        if slow:
            time.sleep(max(2.5, total - (time.time() - t0)))
        else:
            for i in range(1, rounds * 2):
                time.sleep(0.7)
                ha_svc.call_service("light", "turn_on", e, {"rgb_color": a if i % 2 == 0 else b, "brightness": 255})
            time.sleep(0.7)
    finally:
        try:
            _restore(e, st)
        except Exception:
            pass


def flash(lights: list, color: str, alt: str, rounds: int = 3):
    """Team colours on the chosen lights, then each one back exactly as it was. Lights run side by side so a slow one
    never holds up the others."""
    lights = [e for e in lights if isinstance(e, str) and e.startswith("light.")][:12]
    a, b = _rgb(color), _rgb(alt)
    if sum(b) < 90:                               # a black second colour would just look like "off"
        b = [255, 255, 255]
    _S["flash"] = {}
    ts = [threading.Thread(target=_flash_one, args=(e, a, b, rounds), daemon=True) for e in lights]
    for t in ts:
        t.start()
    for t in ts:
        t.join(30)


_YD = r"(\d+)\s*(?:Yds?|Yards?|yd|yds)\.?"


def play_words(league: str, text: str) -> str:
    """ESPN's scoring-play line -> something nice to say.
    'CeeDee Lamb 12 Yd pass from Dak Prescott (Brandon Aubrey Kick)' -> '12-yard touchdown pass to CeeDee Lamb from Dak Prescott'."""
    t = re.sub(r"\s*\([^)]*\)\s*$", "", str(text or "")).strip()        # drop "(Kicker Kick)" / "(410 feet)"
    if not t:
        return ""
    if league in ("nfl", "cfb"):
        m = re.match(rf"(.+?)\s+{_YD}\s+pass from\s+(.+)$", t, re.I)
        if m:
            return f"{m.group(2)}-yard touchdown pass to {m.group(1)} from {m.group(3)}"
        m = re.match(rf"(.+?)\s+{_YD}\s+(?:run|rush)\b", t, re.I)
        if m:
            return f"{m.group(2)}-yard rushing touchdown by {m.group(1)}"
        m = re.match(rf"(.+?)\s+{_YD}\s+field goal\b", t, re.I)
        if m:
            return f"{m.group(2)}-yard field goal by {m.group(1)}"
        m = re.match(rf"(.+?)\s+{_YD}\s+(interception|fumble|kickoff|punt|blocked punt|blocked field goal|missed field goal)\s+(?:return|recovery)\b", t, re.I)
        if m:
            return f"{m.group(2)}-yard {m.group(3).lower()} return for a touchdown by {m.group(1)}"
        return re.sub(_YD, r"\1-yard", t)
    if league == "nhl":
        m = re.match(r"(.+?)\s*\(\d+\)", t) or re.match(r"([^,\-]+)", t)
        who = (m.group(1) if m else t).strip()
        a = re.search(r"assists?:\s*(.+)$", t, re.I)
        return f"Goal by {who}" + (f", assisted by {a.group(1).strip()}" if a and "unassisted" not in a.group(1).lower() else "")
    return re.sub(r"\s*\([^)]*\)", "", t).rstrip(".")


def describe(g: dict) -> str:
    """Who scored and how, from the game's scoring plays. "" when ESPN doesn't have the play yet (never an older one)."""
    if not g.get("event") or g.get("league") not in LEAGUES:
        return ""
    d = _get(f"{API}/{LEAGUES[g['league']][0]}/summary?event={g['event']}")
    plays = [p for p in (d.get("scoringPlays") or []) if str((p.get("team") or {}).get("id") or "") == str(g["team"].get("id"))]
    if not plays:
        return ""
    p = plays[-1]
    try:
        after = int(p.get("homeScore" if g.get("home") else "awayScore"))
    except (TypeError, ValueError):
        return ""
    if after < g["us"] or str(p.get("id")) in _S["told"]:        # still the previous score, or already announced
        return ""
    _S["told"].append(str(p.get("id")))
    del _S["told"][:-200]
    return play_words(g["league"], p.get("text") or "")


def celebrate(g: dict, title: str, body: str, s: dict, big: bool = False, force: bool = False, tail: str = ""):
    """body = the cheer ("Touchdown, Jets!"), tail = the score line. The play itself (who / how) is looked up after
    the delay and goes in between."""
    t = g["team"]
    delay = max(0, min(180, int(s.get("gameDelay", 15) or 0)))

    def go():
        time.sleep(delay)
        if _asleep() and not force:               # the Test button always fires
            return
        nonlocal body
        if tail:
            how = ""
            if s.get("gamePlays", True):
                for attempt in range(2):
                    try:
                        how = describe(g)
                    except Exception:
                        how = ""
                    if how or attempt:
                        break
                    time.sleep(5)                     # the play shows up a few seconds after the score does
            body = " ".join(x for x in (body, (how[:1].upper() + how[1:] + ".") if how else "", tail) if x)
        if s.get("gameSpeak", True):
            try:
                _say(title, body, t.get("color") or "#3b82f6")
            except Exception:
                pass
        if s.get("gameFlash", True):
            flash(s.get("gameLights") or [], t.get("color") or "#3b82f6", t.get("alt") or "#ffffff", 5 if big else 3)
    threading.Thread(target=go, daemon=True, name="gameday-celebrate").start()


def _name(g: dict) -> str:
    return g["team"].get("short") or g["team"].get("name") or "Our team"


def _line(g: dict) -> str:
    return f"{_name(g)} {g['us']}, {g['opp']} {g['them']}"


def check(games: list, s: dict):
    """Compare with the last look; celebrate what changed. The first sighting of a game never celebrates."""
    seen = _S["last"]
    for g in games:
        prev = seen.get(g["key"])
        seen[g["key"]] = {"us": g["us"], "state": g["state"], "at": time.time()}
        if not prev:
            continue
        name = _name(g)
        gained = g["us"] - prev["us"]
        if gained > 0 and g["state"] in ("in", "post") and g["league"] not in ("nba", "cbb"):   # basketball scores non-stop
            what = _what(g["league"], gained)
            if not (g["league"] in ("nfl", "cfb") and gained in (1, 2)):                        # extra points: no party
                celebrate(g, f"🎉 {what}, {name}!", f"{what}, {name}!", s, tail=f"{_line(g)}.")
        if g["state"] == "post" and prev["state"] == "in":
            if g["won"] or (g["won"] is None and g["us"] > g["them"]):
                celebrate(g, f"🏆 {name} win!", f"{name} win! Final score: {_line(g)}.", s, big=True)
            elif s.get("gameSpeak", True) and not _asleep():
                try:
                    _say(f"Final: {_line(g)}", "", "#555555")
                except Exception:
                    pass
    for k in [k for k, v in seen.items() if time.time() - v["at"] > 36 * 3600]:
        seen.pop(k, None)


def status() -> dict:
    """For the wall chip + phone: our games today (live first)."""
    order = {"in": 0, "pre": 1, "post": 2}
    return {"games": sorted(_S["games"], key=lambda g: (order.get(g["state"], 3), g["start"])), "error": _S["error"],
            "flash": _S["flash"]}


def test(s: dict | None = None) -> dict:
    s = s if s is not None else _settings()
    mine = _mine(s)
    if not mine:
        return {"ok": False, "reason": "Pick a team first"}
    t = mine[0]
    g = {"team": t, "us": 7, "them": 0, "opp": "the other guys", "league": t["league"]}
    celebrate(g, f"🎉 Touchdown, {t['name']}!", f"Touchdown, {t['name']}! This is a test.", {**s, "gameDelay": 0}, force=True)
    return {"ok": True}


def _loop():
    time.sleep(45)
    while True:
        wait = 300
        try:
            s = _settings()
            if _mine(s):
                games = fetch(s)
                _S.update(games=games, at=time.time(), error="")
                check(games, s)
                if any(g["state"] == "in" for g in games):
                    wait = 20
                else:                                          # a game about to start: look more often
                    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
                    soon = [g for g in games if g["state"] == "pre" and g["start"][:13] == now[:13]]
                    wait = 60 if soon else 300
            else:
                _S["games"] = []
        except Exception as e:
            _S["error"] = str(e)[:120]
        time.sleep(wait)


def start():
    threading.Thread(target=_loop, daemon=True, name="gameday").start()
