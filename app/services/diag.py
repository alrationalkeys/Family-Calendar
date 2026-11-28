"""
"Copy diagnostics": one block of plain text about FamilyHub + Home Assistant (optionally about one device) that
Alex pastes into a chat when something misbehaves. Read-only: it never calls a service or changes anything.
Left out on purpose: tokens, keys, PINs, alarm codes, addresses and map positions.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from datetime import datetime, timedelta, timezone

from . import ha_svc

_SECRET = re.compile(r"token|password|passwd|secret|api_?key|code$|^code|pin$|latitude|longitude|gps|address|ssid|mac|ip_address|entity_picture|access"
                     r"|location|street|locality|postal|thoroughfare|country|zip|host|url|user|email|phone_number", re.I)
# whole entities that say where people are or how the network is laid out: never listed, whatever was typed
_PRIVATE = re.compile(r"^(device_tracker|person|zone)\.|geocoded|location|ssid|bssid|_ip\b|ip_address|wifi_connection|latitude|longitude", re.I)
_ROOT = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))


def _clean(attrs: dict) -> dict:
    out = {}
    for k, v in (attrs or {}).items():
        if _SECRET.search(str(k)):
            continue
        s = json.dumps(v, default=str)
        out[k] = v if len(s) <= 160 else s[:157] + "..."
    return out


def _local(ts) -> str:
    """HA timestamps are UTC; show them in this computer's time so they line up with the voice log."""
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone().strftime("%m-%d %H:%M:%S")
    except Exception:
        return str(ts)[:19]


def _git() -> str:
    try:
        r = subprocess.run(["git", "log", "-1", "--format=%h %cs %s"], cwd=_ROOT, capture_output=True, text=True, timeout=5)
        return r.stdout.strip()[:90] or "?"
    except Exception:
        return "?"


def _text(path: str, timeout: float = 6.0) -> str:
    req = urllib.request.Request(ha_svc.ha_url() + path, headers={"Authorization": f"Bearer {ha_svc.ha_token()}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _template(t: str) -> str:
    try:
        req = urllib.request.Request(ha_svc.ha_url() + "/api/template", method="POST", data=json.dumps({"template": t}).encode(),
                                     headers={"Authorization": f"Bearer {ha_svc.ha_token()}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.read().decode("utf-8", "replace").strip()
    except Exception as e:
        return f"(n/a: {str(e)[:60]})"


def _match(states: list, q: str) -> list:
    words = [w for w in re.findall(r"[a-z0-9]+", q.lower()) if w not in ("the", "a", "light", "lights")] or re.findall(r"[a-z0-9]+", q.lower())
    hits = []
    for st in states:
        if _PRIVATE.search(st.get("entity_id", "")) or "latitude" in (st.get("attributes") or {}):
            continue
        hay = (st.get("entity_id", "") + " " + str((st.get("attributes") or {}).get("friendly_name", ""))).lower().replace("_", " ")
        if q.lower() == st.get("entity_id") or all(w in hay for w in words):
            hits.append(st)
    order = {"light": 0, "switch": 1, "cover": 2, "lock": 3, "climate": 4, "media_player": 5, "camera": 6}
    hits.sort(key=lambda s: (order.get(s["entity_id"].split(".")[0], 9), s["entity_id"]))
    return hits


def report(q: str = "") -> str:
    L = [f"FamilyHub diagnostics · {datetime.now().strftime('%Y-%m-%d %H:%M')}", f"version: {_git()}"]
    demo = ha_svc.demo_mode()
    if demo:
        L.append("Home Assistant: NOT connected (demo mode: HA_URL / HA_TOKEN missing or HA_DEMO=1)")
    states = []
    if not demo:
        try:
            cfg = ha_svc._request("/api/config") or {}
            L.append(f"Home Assistant: connected, version {cfg.get('version')}, {cfg.get('time_zone')}")
        except Exception as e:
            L.append(f"Home Assistant: can't reach it ({str(e)[:80]})")
        try:
            states = ha_svc._request("/api/states", timeout=8) or []
        except Exception as e:
            L.append(f"states: failed ({str(e)[:80]})")
    else:
        states = [{"entity_id": k, "state": v["state"], "attributes": v.get("attributes", {})} for k, v in ha_svc._DEMO.items()]
    try:
        from . import ha_live
        L.append(f"live link to HA: {'up' if ha_live.connected() else 'down'}")
    except Exception:
        pass

    doms = {}
    for st in states:
        d = st["entity_id"].split(".")[0]
        doms[d] = doms.get(d, 0) + 1
    L.append("entities: " + ", ".join(f"{k} {v}" for k, v in sorted(doms.items(), key=lambda x: -x[1])[:14]))
    dead = [str((s.get("attributes") or {}).get("friendly_name") or s["entity_id"]) for s in states
            if s.get("state") == "unavailable" and s["entity_id"].split(".")[0] in ("light", "switch", "cover", "lock", "climate", "camera", "media_player", "alarm_control_panel")]
    L.append(f"unavailable right now ({len(dead)}): " + (", ".join(dead[:25]) or "none"))

    if q.strip():
        hits = _match(states, q.strip())
        L.append("")
        L.append(f"== devices matching \"{q.strip()}\": {len(hits)} ==")
        for st in hits[:6]:
            eid = st["entity_id"]
            L.append(f"- {eid} = {st.get('state')}  (changed {_local(st.get('last_changed'))}, updated {_local(st.get('last_updated'))})")
            L.append("  attributes: " + json.dumps(_clean(st.get("attributes")), default=str))
            if not demo:
                L.append("  device: " + _template("{{ device_attr('%s','manufacturer') }} / {{ device_attr('%s','model') }} / area {{ area_name('%s') }} / via {{ device_attr('%s','identifiers') | map('first') | list }}" % (eid, eid, eid, eid)))
                try:
                    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
                    log = ha_svc._request(f"/api/logbook/{since}?entity={eid}", timeout=8) or []
                    L.append(f"  last 24 h ({len(log)} changes), newest last:")
                    for e in log[-12:]:
                        who = _who(e)
                        L.append(f"    {_local(e.get('when'))}  {e.get('state', e.get('message', ''))}  {who}")
                except Exception as e:
                    L.append(f"  history: n/a ({str(e)[:60]})")
        if len(hits) > 6:
            L.append(f"  (+{len(hits) - 6} more: " + ", ".join(h["entity_id"] for h in hits[6:20]) + ")")
        if not demo and hits:
            try:
                keys = {h["entity_id"].split(".", 1)[1] for h in hits[:6]} | set(re.findall(r"[a-z0-9]{4,}", q.lower()))
                lines = [ln for ln in _text("/api/error_log").splitlines() if any(k in ln.lower() for k in keys)]
                L.append(f"  Home Assistant log lines mentioning it ({len(lines)}):")
                L += ["    " + _hide(ln)[:260] for ln in lines[-10:]]
            except Exception as e:
                L.append(f"  Home Assistant log: not available on this Home Assistant ({str(e)[:40]})")

    if not demo and states:
        L += routines(states)

    L.append("")
    L.append("== FamilyHub ==")
    try:
        from . import watch
        L.append("house checks failing: " + (json.dumps(watch.TICK_ERRORS) if watch.TICK_ERRORS else "none"))
    except Exception:
        pass
    try:
        from . import village
        a = village._auto()
        fol = village._follows()
        try:
            from . import ha_live
            on = {x["entity_id"] for x in (ha_live.states() or []) if x.get("state") == "on"}
            lights = village.open_lights(ha_live.states() or [])
        except Exception:
            on, lights = set(), []
        L.append(f"village: board follows FamilyHub: {fol}; tonight: {json.dumps(a)}; auto on: {village._settings().get('villageAuto', True) is not False}; "
                 f"lights that open it: {', '.join(lights) or 'NONE FOUND'} (on now: {', '.join(e for e in lights if e in on) or 'none'})")
    except Exception as e:
        L.append(f"village: {str(e)[:80]}")
    try:
        from . import display_svc
        d = display_svc.state()
        L.append(f"screen: {'on' if d.get('on') else 'OFF'}, night mode (dark until disarm): {d.get('sleep_mode')}, in the night window: {d.get('night')}, "
                 f"alarm as the wall sees it: {display_svc._state.get('alarm')}, night mode ended by the safety net: {d.get('sleep_failsafe') or 'no'}")
    except Exception:
        pass
    try:
        from . import gameday
        g = gameday.status()
        L.append(f"game day: {len(g.get('games') or [])} game(s) today, error: {g.get('error') or 'none'}; last light flash: {json.dumps(g.get('flash') or {})}")
        for ln in (g.get("log") or [])[-10:]:
            L.append("  game day: " + _hide(ln)[:200])
    except Exception:
        pass
    try:
        from . import speech
        L.append(f"speech: {json.dumps(speech.status())}; last clip: {json.dumps(speech.last_clip)}")
    except Exception:
        pass
    try:
        from . import outdoor_power
        o = outdoor_power.status()
        L.append(f"outside power watch: {len(o['watched'])} lights/plugs, down since: {datetime.fromtimestamp(o['down_since']).strftime('%H:%M') if o['down_since'] else '-'}, told: {o['told']}")
    except Exception:
        pass
    try:
        from . import wake
        w = wake.status()
        L.append(f"wake word: installed {'yes' if w['installed'] else 'no'}, word {w['word'] or 'off'}, running {'yes' if w['running'] else 'no'}, "
                 f"mic {w['mic'] or '-'}, wakes {w['wakes']}, last {w['last_wake'] or '-'}, score now {w['last_score']} (best in 5 s {w['best_recent']}, "
                 f"needs {w['threshold']}), error: {w['error'] or 'none'}")
    except Exception:
        pass
    try:
        from . import cloud_voice
        L.append(f"cloud voice: key {'yes' if cloud_voice._key() else 'no'}, error: {cloud_voice._S.get('error') or 'none'}")
    except Exception:
        pass
    try:
        from .voice_cmd import get_db as _db
        with _db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='voice_log'").fetchone()
        for e in (json.loads(row["value"]) if row else [])[:6]:
            L.append(f"voice {e.get('at', '')[5:16]} \"{e.get('heard', '')[:60]}\" -> {e.get('reply', '')[:150]} {('[' + e['took'] + ']') if e.get('took') else ''}")
    except Exception:
        pass
    return _hide("\n".join(L))


_EID = re.compile(r"\b(?:light|switch|binary_sensor|sensor|cover|lock|climate|media_player|scene|script|input_boolean|"
                  r"input_text|input_datetime|input_number|fan|camera|alarm_control_panel|event|button)\.[a-z0-9_]+\b")


def routines(states: list) -> list:
    """Every Home Assistant automation: on/off, when it last ran, and any device it names that HA no longer has
    (re-adding an integration renames things to *_2, and the routine silently does nothing)."""
    have = {s["entity_id"] for s in states}
    autos = sorted((s for s in states if s["entity_id"].startswith("automation.")),
                   key=lambda s: str((s.get("attributes") or {}).get("friendly_name") or s["entity_id"]).lower())
    L = ["", f"== Home Assistant routines ({len(autos)}) =="]
    missing_all = set()
    for a in autos:
        at = a.get("attributes") or {}
        name = str(at.get("friendly_name") or a["entity_id"])
        last = _local(at["last_triggered"]) if at.get("last_triggered") else "never"
        gone = []
        if at.get("id"):
            try:
                cfg = ha_svc._request(f"/api/config/automation/config/{at['id']}", timeout=6) or {}
                refs = set(_EID.findall(json.dumps(cfg)))
                gone = sorted(e for e in refs if e not in have and not e.startswith(("input_", "script.", "scene."))
                              and not re.search(r"\.(turn_on|turn_off|toggle|set_\w+|lock|unlock|open_cover|close_cover|"
                                                r"select_\w+|press|reload|trigger|alarm_\w+|media_\w+|volume_\w+|play_media)$", e))
            except Exception:
                pass                                    # a packaged (YAML) routine: its lists are checked below
        missing_all |= set(gone)
        flag = "" if a.get("state") == "on" else f"  <-- {a.get('state', '?').upper()}"
        L.append(f"  {name}: last ran {last}{flag}" + (f"  <-- names devices HA doesn't have: {', '.join(gone[:6])}" if gone else ""))
    # the light lists the packaged routines read (outdoor / kitchen / Christmas windows): stale ids there do nothing too
    packaged_on = any(a.get("state") == "on" and re.match(r"automation\.(outdoor|kitchen|christmas|patio)_", a["entity_id"]) for a in autos)
    for st in states if packaged_on else []:          # lists only matter while the packaged routines that read them are on
        eid = st["entity_id"]
        if eid.startswith("input_text.fh_"):
            ids = [x.strip() for x in str(st.get("state") or "").split(",") if "." in x]
            gone = [x for x in ids if x not in have]
            if gone:
                L.append(f"  list {(st.get('attributes') or {}).get('friendly_name') or eid}: HA doesn't have {', '.join(gone)}")
                missing_all |= set(gone)
    if missing_all:
        # suggest the renamed one: same name with _2 / _3 on the end, or the old name without it
        sug = []
        for g in sorted(missing_all):
            base = re.sub(r"_\d+$", "", g)
            alt = [e for e in have if e != g and (re.sub(r"_\d+$", "", e) == base)]
            if alt:
                sug.append(f"{g} -> {alt[0]}")
        if sug:
            L.append("  probably renamed: " + "; ".join(sug[:12]))
    try:
        lines = [ln for ln in _text("/api/error_log").splitlines()
                 if re.search(r"automation|script|homeassistant\.helpers\.(script|service)", ln, re.I) and re.search(r"error|warning|not found|unavailable", ln, re.I)]
        if lines:
            L.append(f"  Home Assistant log, routine problems ({len(lines)}, newest last):")
            L += ["    " + _hide(ln)[:240] for ln in lines[-12:]]
    except Exception:
        pass
    return L


def _who(e: dict) -> str:
    """Who changed it, from HA's logbook: the routine / script by name, a person or FamilyHub, or the device itself."""
    ent = e.get("context_entity_id") or ""
    if ent:
        return "by " + str(e.get("context_entity_id_name") or ent) + (f" ({ent})" if e.get("context_entity_id_name") else "")
    if e.get("context_user_id"):
        return "by a person or FamilyHub" + (f" ({e['context_domain']}.{e.get('context_service', '')})" if e.get("context_domain") else "")
    if e.get("context_event_type"):
        return "by " + str(e["context_event_type"])
    return "by the device / its own app"


def _hide(s: str) -> str:
    s = re.sub(r"(?i)(bearer\s+|token[=: ]+|key[=: ]+|password[=: ]+)[A-Za-z0-9._\-]{8,}", r"\1[hidden]", s)
    s = re.sub(r"://[^/\s:@]+:[^/\s@]+@", "://[hidden]@", s)                      # user:password@ inside a URL
    s = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[ip]", s)                        # network addresses
    return re.sub(r"\b[A-Za-z0-9_\-]{40,}\b", "[hidden]", s)
