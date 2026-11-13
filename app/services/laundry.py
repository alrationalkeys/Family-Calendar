"""
Laundry done: watches the washer/dryer entities Home Assistant gets from GE's SmartHQ cloud (HACS "GE Home
(SmartHQ)", simbaja/ha_gehome) — or any entity whose name says washer/dryer/laundry.

A cycle counts as finished when the machine's state sensor goes from running (run / wash / rinse / spin /
dry / cool down…) to an end state (end of cycle / complete / done / idle / off / clean). Then:
  daytime (settings.laundryQuietStart..End not covering now)  -> wall says "🧺 The washer is done" + phone push
  quiet hours (default 21:30-07:30)                            -> silent push only, no voice
Also exposes status() for the wall: [{name, running, remaining_min}].
Settings: laundryAlerts (bool), laundryQuietStart / laundryQuietEnd "HH:MM".
"""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime

_MACH = re.compile(r"washer|dryer|laundry", re.I)
_RUN = re.compile(r"run|wash|rinse|spin|dry|cool ?down|fill|soak|steam|tumbl|sens|delay", re.I)
_END = re.compile(r"end|complete|done|finish|clean|idle|^off$|standby|ready", re.I)
_SKIP = re.compile(r"time|remaining|door|lock|temp|soil|level|option|setting|dispens|count|error|wifi|signal|"
                   r"remote|delay_time|cycle$|^cycle", re.I)
_PROBLEM = re.compile(r"vent|block|clog|error|fault|service|water_?supply|supply|leak|fail|alert|warning|maintenance", re.I)
_OK_VALUES = {"", "off", "none", "no error", "no_error", "ok", "normal", "unknown", "unavailable", "---", "0", "false", "no"}
_LOG: list = []           # recent washer/dryer state changes (diagnostics: GET /api/ha/laundry)
_SENT: list = []          # recent laundry messages and who they went to
_last: dict = {}          # machine -> time announced
_done_at: dict = {}       # machine -> when it finished (cleared when its door opens or a new cycle starts)
_nudged: set = set()      # machines already nudged about clothes sitting in them
_soon: set = set()        # machines already warned "done in ~10 min" this cycle


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def _machine(eid: str, name: str) -> str | None:
    txt = f"{eid} {name}".lower()
    return "dryer" if "dryer" in txt else "washer" if ("washer" in txt or "laundry" in txt) else None


def is_state_sensor(eid: str, attrs: dict) -> bool:
    if not eid.startswith("sensor."):
        return False
    name = str(attrs.get("friendly_name", ""))
    if not _MACH.search(eid + " " + name):
        return False
    obj = eid.split(".", 1)[1]
    if re.search(r"machine_state|machine_status|run_status|cycle_status|operation_state|_state$|_status$", obj):
        return True
    return not (_SKIP.search(obj) or _SKIP.search(name))


def _quiet(s: dict) -> bool:
    a, b = str(s.get("laundryQuietStart") or "21:30"), str(s.get("laundryQuietEnd") or "07:30")
    now = datetime.now().strftime("%H:%M")
    return (a <= now or now < b) if a > b else (a <= now < b)


def on_state(eid: str, old: dict | None, new: dict | None):
    try:
        if not new or not old:
            return
        attrs = new.get("attributes") or {}
        o, n = str(old.get("state") or ""), str(new.get("state") or "")
        if _MACH.search(eid + " " + str(attrs.get("friendly_name", ""))) and o != n and not re.search(r"time|remaining|delay", eid):
            _LOG.append({"at": datetime.now().strftime("%H:%M:%S"), "entity": eid, "from": o, "to": n})
            del _LOG[:-40]
        fname = str(attrs.get("friendly_name", ""))
        if _MACH.search(eid + " " + fname) and _PROBLEM.search(eid + " " + fname) and eid.split(".")[0] in ("binary_sensor", "sensor"):
            bad = (n == "on") if eid.startswith("binary_sensor.") else (n.lower() not in _OK_VALUES)
            was = (o == "on") if eid.startswith("binary_sensor.") else (o.lower() not in _OK_VALUES)
            if bad and not was:
                mach = _machine(eid, fname) or "laundry"
                key = f"{mach}:{eid}"
                if time.time() - _last.get(key, 0) > 6 * 3600:      # once per problem per 6 h
                    _last[key] = time.time()
                    what = re.sub(r"^[A-Z0-9]{6,}\s+|laundry\s+", "", fname, flags=re.I).strip() or "a problem"
                    extra = "" if eid.startswith("binary_sensor.") else f": {n}"
                    threading.Thread(target=_announce, args=(mach, False, f"⚠️ {mach.title()}: {what}{extra}. Check it when you can.", True), daemon=True).start()
            return
        if eid.startswith("binary_sensor.") and "door" in eid and _MACH.search(eid + " " + str(attrs.get("friendly_name", ""))):
            if n == "on" and o != "on":                   # door opened: someone's dealing with it
                _done_at.pop(_machine(eid, attrs.get("friendly_name", "")) or "laundry", None)
            return
        if eid.startswith("binary_sensor.") and "end_of_cycle" in eid and _MACH.search(eid + " " + str(attrs.get("friendly_name", ""))):
            if not (o == "off" and n == "on"):          # GE SmartHQ: "Laundry End of Cycle" flips on when it's done
                return
        elif not is_state_sensor(eid, attrs):
            return
        elif o == n or not _RUN.search(o) or _END.search(o) or not _END.search(n):
            return
        mach = _machine(eid, attrs.get("friendly_name", "")) or "laundry"
        if time.time() - _last.get(mach, 0) < 600:
            return
        _last[mach] = time.time()
        _done_at[mach] = time.time(); _nudged.discard(mach); _soon.discard(mach)
        s = _settings()
        if s.get("laundryAlerts", True) is False:
            return
        threading.Thread(target=_announce, args=(mach, _quiet(s)), daemon=True).start()
    except Exception:
        pass


def _message(mach: str) -> str:
    if mach == "washer":
        try:
            d = next((m for m in status() if m["name"] == "Dryer"), None)
            if d and not d["running"]:
                return "🧺 The washer is done, ready to move to the dryer."
        except Exception:
            pass
    return f"🧺 The {mach} is done." if mach != "laundry" else "🧺 The laundry is done."


def _announce(mach: str, quiet: bool, text: str | None = None, speak: bool = True):
    """Wall (spoken, daytime only) + phones (silent in quiet hours)."""
    from ..db import get_db
    from . import ha_svc
    text = text or _message(mach)
    if not quiet and speak:
        try:
            with get_db() as conn:          # the wall shows + speaks announcements
                conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                             ("🧺 Laundry", text.replace("🧺 ", ""), "announce", datetime.now().isoformat()))
        except Exception:
            pass
    sent_to, err = [], ""
    try:
        for dom in ha_svc._request("/api/services") or []:
            if dom.get("domain") == "notify":
                for svc in (dom.get("services") or {}):
                    if svc.startswith("mobile_app_"):
                        sent_to.append(svc)
                        data = {"tag": f"familyhub-{mach}"}
                        if quiet:
                            data["push"] = {"interruption-level": "passive"}
                        r = ha_svc.call_service("notify", svc, "", {"title": "FamilyHub", "message": text, "data": data})
                        if isinstance(r, dict) and r.get("ok") is False:
                            err = r.get("reason") or "Home Assistant refused the push"
    except Exception as e:
        err = str(e)[:120]
    _SENT.append({"at": datetime.now().strftime("%H:%M:%S"), "text": text, "quiet": quiet, "to": sent_to, "error": err})
    del _SENT[:-20]
    return {"to": sent_to, "error": err}


def test():
    """Send a test laundry push right now (not quiet) and say who it went to."""
    r = _announce("washer", False, "🧺 Test from FamilyHub: laundry alerts are working.", False)
    if not r["to"] and not r["error"]:
        r["error"] = "No phones found: install the Home Assistant app on each phone and sign in (it creates notify.mobile_app_<phone>)."
    return {"ok": bool(r["to"]) and not r["error"], **r}


def diag() -> dict:
    try:
        from . import ha_live
        live = ha_live.states() is not None
    except Exception:
        live = False
    return {"live": live, "seen": _LOG[-15:], "sent": _SENT[-10:]}


def tick():
    """Every minute from the house-watch loop: 'done in ~10 min' and 'clothes still sitting there'."""
    s = _settings()
    if s.get("laundryAlerts", True) is False:
        return
    soon = int(s.get("laundrySoonMin", 10) or 0)
    nudge = int(s.get("laundryNudgeMin", 30) or 0)
    quiet = _quiet(s)
    for m in status():
        mach = m["name"].lower()
        if m["running"]:
            _done_at.pop(mach, None)                  # a new cycle: forget the old one
            r = m.get("remaining_min")
            if soon and r is not None and 0 < r <= soon and mach not in _soon:
                _soon.add(mach)
                threading.Thread(target=_announce, args=(mach, quiet, f"🧺 The {mach} is done in about {r} min.", False), daemon=True).start()
            elif r is not None and r > soon + 5:
                _soon.discard(mach)
        t = _done_at.get(mach)
        if nudge and t and mach not in _nudged and time.time() - t >= nudge * 60 and not quiet:
            _nudged.add(mach)
            mins = int((time.time() - t) // 60)
            threading.Thread(target=_announce, args=(mach, False, f"🧺 The {mach} finished {mins} min ago, the clothes are still in there.", False), daemon=True).start()


def status() -> list:
    """Washer/dryer now: running? minutes left (from a *time_remaining* sensor when there is one)."""
    try:
        from . import ha_live, ha_svc
        states = ha_live.states() or ha_svc._request("/api/states") or []
    except Exception:
        return []
    out = {}
    for st in states:
        eid, a = st.get("entity_id", ""), st.get("attributes") or {}
        if not eid.startswith("sensor.") or a.get("integration") == "x":
            continue
        mach = _machine(eid, a.get("friendly_name", "")) if _MACH.search(eid + " " + str(a.get("friendly_name", ""))) else None
        if not mach:
            continue
        m = out.setdefault(mach, {"name": mach.title(), "running": False, "remaining_min": None, "state": ""})
        if is_state_sensor(eid, a):
            v = str(st.get("state") or "")
            m["state"] = v
            m["running"] = bool(_RUN.search(v)) and not _END.search(v)
        elif re.search(r"remaining|time_left", eid):
            try:
                v = float(st.get("state"))
                unit = str(a.get("unit_of_measurement", "min")).lower()
                m["remaining_min"] = round(v * 60 if unit.startswith("h") else v / 60 if unit.startswith("s") else v)
            except (TypeError, ValueError):
                pass
    return [v for v in out.values() if v["state"]]
