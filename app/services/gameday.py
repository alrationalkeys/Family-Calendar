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
    "epl": ("soccer/eng.1", "Soccer: Premier League", ""),
    "laliga": ("soccer/esp.1", "Soccer: La Liga", ""),
    "bundesliga": ("soccer/ger.1", "Soccer: Bundesliga", ""),
    "seriea": ("soccer/ita.1", "Soccer: Serie A", ""),
    "ligue1": ("soccer/fra.1", "Soccer: Ligue 1", ""),
    "intl": ("soccer/fifa.world", "Soccer: national teams", ""),
}
SOCCER = {"epl", "laliga", "bundesliga", "seriea", "ligue1", "intl"}
_EURO = ["soccer/uefa.champions", "soccer/uefa.europa"]
EXTRA = {                                      # other competitions the same teams play in (same team ids on ESPN)
    "epl": _EURO + ["soccer/eng.fa", "soccer/eng.league_cup"],
    "laliga": _EURO + ["soccer/esp.copa_del_rey"],
    "bundesliga": _EURO + ["soccer/ger.dfb_pokal"],
    "seriea": _EURO + ["soccer/ita.coppa_italia"],
    "ligue1": _EURO + ["soccer/fra.coupe_de_france"],
    "intl": ["soccer/fifa.friendly", "soccer/uefa.nations", "soccer/uefa.euro", "soccer/conmebol.america",
             "soccer/concacaf.nations.league", "soccer/concacaf.gold", "soccer/fifa.worldq.uefa",
             "soccer/fifa.worldq.conmebol", "soccer/fifa.worldq.concacaf"],
}
_BOARD: dict = {}                              # scoreboard path -> {"at", "games"} (each path refreshed only as often as it needs)
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


def _scorer(comp: dict, tid: str) -> str:
    """Soccer: the scoreboard lists each goal. -> 'Bukayo Saka in the 23rd minute' for our team's latest, or ''."""
    last = None
    for d in comp.get("details") or []:
        if d.get("scoringPlay") and str((d.get("team") or {}).get("id") or "") == tid:
            last = d
    if not last:
        return ""
    who = ", ".join(a.get("displayName") or a.get("fullName") or "" for a in (last.get("athletesInvolved") or [])[:1]).strip()
    kind = str((last.get("type") or {}).get("text") or "").lower()
    when = str((last.get("clock") or {}).get("displayValue") or "").replace("'", "").strip()
    m = re.match(r"(\d+)", when)
    minute = ""
    if m:
        n = int(m.group(1))
        minute = f" in the {n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')} minute"
    if "own" in kind:
        return "An own goal" + minute
    if not who:
        return ""
    return ("Penalty scored by " if "penalty" in kind else "Scored by ") + who + minute


def _parse(league: str, d: dict, mine: dict, path: str = "") -> list:
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
                        "path": path or LEAGUES[league][0],
                        "opp": (o.get("team") or {}).get("shortDisplayName") or (o.get("team") or {}).get("displayName") or "?",
                        "opp_abbr": (o.get("team") or {}).get("abbreviation") or "",
                        "us": pts(c), "them": pts(o), "home": c.get("homeAway") == "home",
                        "state": st.get("state") or "pre", "detail": st.get("shortDetail") or st.get("detail") or "",
                        "scorer": _scorer(comp, tid) if league in SOCCER else "",
                        "start": ev.get("date") or "", "won": bool(c.get("winner")) if st.get("state") == "post" else None})
    return out


def _due(path: str, primary: bool) -> bool:
    """A scoreboard is re-read every 20 s while one of our games on it is live, every minute in the hour before one,
    every 5 min otherwise; the extra cups/competitions only every 15 min while they have nothing of ours."""
    hit = _BOARD.get(path)
    if not hit:
        return True
    age = time.time() - hit["at"]
    games = hit["games"]
    if any(g["state"] == "in" for g in games):
        return age >= 18
    hour = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
    if any(g["state"] == "pre" and g["start"][:13] == hour for g in games):
        return age >= 55
    return age >= (290 if primary or games else 890)


def fetch(s: dict | None = None) -> list:
    s = s if s is not None else _settings()
    mine = _mine(s)
    games, live_paths = [], set()
    for league in sorted({t["league"] for t in mine}):
        path, _label, q = LEAGUES[league]
        ours = {str(t["id"]): t for t in mine if t["league"] == league}
        for pth in [path] + EXTRA.get(league, []):
            key = f"{league}|{pth}"
            live_paths.add(key)
            if _due(key, pth == path):
                try:
                    d = _get(f"{API}/{pth}/scoreboard" + (f"?{q}" if q else ""))
                    _BOARD[key] = {"at": time.time(), "games": _parse(league, d, ours, pth)}
                except Exception:
                    if pth == path:
                        raise
                    _BOARD[key] = {"at": time.time(), "games": []}        # a cup with no page this season
            games += [g for g in _BOARD[key]["games"] if str(g["team"].get("id")) in ours]
    for k in [k for k in _BOARD if k not in live_paths]:
        _BOARD.pop(k, None)
    return games


def _what(league: str, gained: int) -> str:
    if league in ("nfl", "cfb"):
        return {1: "Extra point", 2: "Two points", 3: "Field goal", 6: "Touchdown", 7: "Touchdown", 8: "Touchdown"}.get(gained, "Score")
    if league == "nhl" or league in SOCCER:
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


# Integrations that take a quick run of colour changes without choking. Everything else (Govee, Tuya, cloud lights...)
# gets ONE colour change, held, then put back: a burst over Wi-Fi/UDP left a Govee strip switched off (Nov 17).
_FAST = ("zha", "mqtt", "hue", "wled", "esphome", "zwave_js", "deconz", "lifx", "zigbee")
_VIA: dict = {}


def _via(e: str) -> str:
    """Which integration a light comes through ('govee_light_local', 'zha', ...). Asked once per light."""
    if e not in _VIA:
        try:
            from . import diag
            _VIA[e] = diag._template("{{ device_attr('%s','identifiers') | map('first') | join(',') }}" % e).lower()
        except Exception:
            _VIA[e] = ""
        if _VIA[e].startswith("(n/a"):
            _VIA.pop(e)
            return ""
    return _VIA[e]


def _put_back(e: str, st: dict):
    attrs = st.get("attributes") or {}
    if st.get("state") != "on":
        ha_svc.call_service("light", "turn_off", e)
        return
    extra = {"brightness": attrs.get("brightness") or 255}
    if attrs.get("effect") and str(attrs["effect"]).lower() not in ("none", "off", "solid"):
        extra = {"effect": attrs["effect"]}
    elif attrs.get("color_mode") == "color_temp" and attrs.get("color_temp_kelvin"):
        extra["color_temp_kelvin"] = attrs["color_temp_kelvin"]
    elif attrs.get("rgb_color"):
        extra["rgb_color"] = list(attrs["rgb_color"])[:3]
    ha_svc.call_service("light", "turn_on", e, extra)


def _restore(e: str, st: dict | None):
    """Back to how it was, and CHECK it: a light that was on must end up on, one that was off must end up off.
    If we never learned how it was, it is left alone (never switched off on a guess)."""
    if not st or st.get("state") not in ("on", "off"):
        _S["flash"][e] = _S["flash"].get(e, "") + "; left as is (didn't know how it was before)"
        return
    want = st["state"]
    for attempt in range(3):
        _put_back(e, st)
        if ha_svc.demo_mode():
            return
        time.sleep(3.0)
        try:
            now = (ha_svc._request(f"/api/states/{e}") or {}).get("state")
        except Exception:
            now = None
        if now == want:
            if attempt:
                _S["flash"][e] = _S["flash"].get(e, "") + f"; needed {attempt + 1} tries to go back {want}"
            return
    _S["flash"][e] = _S["flash"].get(e, "") + f"; could NOT put it back {want}"


def _flash_one(e: str, a: list, b: list, rounds: int):
    """One light, on its own thread. Zigbee-type lights blink between the two colours. Everything else just turns
    the team colour once, holds it, and goes back."""
    st = None
    if not ha_svc.demo_mode():
        for _ in range(2):                                   # knowing the starting state matters: try twice
            try:
                st = ha_svc._request(f"/api/states/{e}")
                break
            except Exception:
                time.sleep(0.5)
        if st is None or st.get("state") == "unavailable":
            _S["flash"][e] = "skipped: " + ("couldn't read it" if st is None else "unavailable")
            return
    total = rounds * 2 * 0.7
    t0 = time.time()
    try:
        via = "" if ha_svc.demo_mode() else _via(e)
        r = ha_svc.call_service("light", "turn_on", e, {"rgb_color": a, "brightness": 255})
        fast = ha_svc.demo_mode() or any(k in via for k in _FAST)
        slow = (not r.get("ok")) or not fast or time.time() - t0 > 0.45
        _S["flash"][e] = (("held" if slow else "blinked") + (f" ({via})" if via else "")) if r.get("ok") else ("failed: " + str(r.get("reason", "")))
        if slow:
            time.sleep(max(2.5, total - (time.time() - t0)))
        else:
            for i in range(1, rounds * 2):
                time.sleep(0.7)
                ha_svc.call_service("light", "turn_on", e, {"rgb_color": a if i % 2 == 0 else b, "brightness": 255})
            time.sleep(0.7)
    finally:
        try:
            _restore(e, st if st is not None else ({"state": "off"} if ha_svc.demo_mode() else None))
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
    _S["flashing"] = set(lights)
    ts = [threading.Thread(target=_flash_one, args=(e, a, b, rounds), daemon=True) for e in lights]
    for t in ts:
        t.start()
    for t in ts:
        t.join(45)
    _S["flashing"] = set()


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
    if g.get("league") in SOCCER:                 # already on the scoreboard, read with the score itself
        return g.get("scorer") or ""
    if not g.get("event") or g.get("league") not in LEAGUES:
        return ""
    d = _get(f"{API}/{g.get('path') or LEAGUES[g['league']][0]}/summary?event={g['event']}")
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
    what = _what(t["league"], 6)
    celebrate(g, f"🎉 {what}, {t['name']}!", f"{what}, {t['name']}! This is a test.", {**s, "gameDelay": 0}, force=True)
    return {"ok": True}


def _loop():
    time.sleep(45)
    while True:
        wait = 120
        try:
            s = _settings()
            if _mine(s):
                games = fetch(s)
                _S.update(games=games, at=time.time(), error="")
                check(games, s)
                wait = 20 if any(g["state"] == "in" for g in games) else 60     # each scoreboard paces itself (_due)
            else:
                _S["games"] = []
        except Exception as e:
            _S["error"] = str(e)[:120]
        time.sleep(wait)


def start():
    threading.Thread(target=_loop, daemon=True, name="gameday").start()
