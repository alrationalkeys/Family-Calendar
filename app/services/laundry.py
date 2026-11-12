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
_last: dict = {}          # machine -> time announced


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
    return not _SKIP.search(obj + " " + name)


def _quiet(s: dict) -> bool:
    a, b = str(s.get("laundryQuietStart") or "21:30"), str(s.get("laundryQuietEnd") or "07:30")
    now = datetime.now().strftime("%H:%M")
    return (a <= now or now < b) if a > b else (a <= now < b)


def on_state(eid: str, old: dict | None, new: dict | None):
    try:
        if not new or not old:
            return
        attrs = new.get("attributes") or {}
        if not is_state_sensor(eid, attrs):
            return
        o, n = str(old.get("state") or ""), str(new.get("state") or "")
        if o == n or not _RUN.search(o) or _END.search(o) or not _END.search(n):
            return
        mach = _machine(eid, attrs.get("friendly_name", "")) or "laundry"
        if time.time() - _last.get(mach, 0) < 600:
            return
        _last[mach] = time.time()
        s = _settings()
        if s.get("laundryAlerts", True) is False:
            return
        threading.Thread(target=_announce, args=(mach, _quiet(s)), daemon=True).start()
    except Exception:
        pass


def _announce(mach: str, quiet: bool):
    from ..db import get_db
    from . import ha_svc
    text = f"🧺 The {mach} is done." if mach != "laundry" else "🧺 The laundry is done."
    if not quiet:
        try:
            with get_db() as conn:          # the wall shows + speaks announcements
                conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                             ("🧺 Laundry", text.replace("🧺 ", ""), "announce", datetime.now().isoformat()))
        except Exception:
            pass
    try:
        for dom in ha_svc._request("/api/services") or []:
            if dom.get("domain") == "notify":
                for svc in (dom.get("services") or {}):
                    if svc.startswith("mobile_app_"):
                        data = {"tag": f"familyhub-{mach}"}
                        if quiet:
                            data["push"] = {"interruption-level": "passive"}
                        ha_svc.call_service("notify", svc, "", {"title": "FamilyHub", "message": text, "data": data})
    except Exception:
        pass


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
        if not eid.startswith("sensor."):
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
