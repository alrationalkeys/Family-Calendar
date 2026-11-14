"""
Keeping an eye on the house, quietly. One background loop (every minute) does four things:

  health()      low batteries + devices that dropped off (unavailable) -> the "Needs attention" card
  peak alert    heat/AC still on 3+ min into the Santee Cooper peak -> one push per thermostat per day,
                logged in settings row 'peak_log' for the weekly note
  night check   at settings.nightCheckTime (default 22:30): doors unlocked, garage/doors open, alarm not set
                -> one quiet push listing them (nothing if all is well). Never changes anything.
  weekly note   Sunday at 18:00: heat/AC hours, any peak use, low batteries -> one push

Settings: nightCheck (bool), nightCheckTime "HH:MM", peakAlerts (bool), weeklySummary (bool), batteryLow (%).
Pushes go through Home Assistant's mobile_app notifiers (the HA companion app), like the rest of FamilyHub.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import date, datetime, timedelta

from . import ha_svc
from ..db import get_db

_SENT: dict = {}            # dedupe key -> day it was sent
_PEAK_SEEN: dict = {}       # climate id -> first time seen on during this peak


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def _states() -> list:
    try:
        from . import ha_live
        s = ha_live.states()
        return s if s is not None else (ha_svc._request("/api/states") or [])
    except Exception:
        return []


def _push(text: str, tag: str):
    try:
        _push_tag(text, tag)
    except Exception:
        pass


def _push_tag(text: str, tag: str):
    if ha_svc.demo_mode() or not ha_svc.ha_url():
        return
    for dom in ha_svc._request("/api/services") or []:
        if dom.get("domain") == "notify":
            for name in (dom.get("services") or {}):
                if name.startswith("mobile_app_"):
                    ha_svc.call_service("notify", name, "", {"title": "FamilyHub", "message": text, "data": {"tag": tag}})


# ---------------------------------------------------------------- health
_WATCH = ("light", "switch", "lock", "climate", "cover", "alarm_control_panel", "camera", "media_player")


def health() -> dict:
    s = _settings()
    try:
        low_at = float(s.get("batteryLow") or 25)
    except (TypeError, ValueError):
        low_at = 25
    if ha_svc.demo_mode() or not ha_svc.ha_url():
        return {"ok": True, "demo": True, "low": [{"entity_id": "sensor.back_door_battery", "name": "Back Door sensor", "level": 15}],
                "offline": [{"entity_id": "light.stove_upper_led", "name": "Stove Upper LED", "since": None}]}
    try:
        ha_svc.entity_areas()                 # fills _CATEGORY / _PLATFORM (cached)
    except Exception:
        pass
    low, offline = [], []
    for st in _states():
        eid, a = st.get("entity_id", ""), st.get("attributes") or {}
        dom = eid.split(".", 1)[0]
        name = a.get("friendly_name") or eid
        try:
            if ha_svc.is_blink(eid, a):
                continue
        except Exception:
            pass
        if dom == "sensor" and a.get("device_class") == "battery":
            try:
                v = float(st.get("state"))
            except (TypeError, ValueError):
                continue
            if v <= low_at:
                low.append({"entity_id": eid, "name": name.replace(" Battery", "").replace(" battery", ""), "level": round(v)})
        elif dom == "binary_sensor" and a.get("device_class") == "battery" and st.get("state") == "on":
            low.append({"entity_id": eid, "name": name.replace(" Battery", ""), "level": None})
        elif st.get("state") == "unavailable" and (dom in _WATCH or (dom == "binary_sensor" and a.get("device_class") in
                                                   ("door", "window", "garage_door", "opening", "motion", "occupancy"))):
            if ha_svc._CATEGORY.get(eid) in ("config", "diagnostic"):
                continue
            if dom == "switch" and eid.startswith("switch.fh"):
                continue
            offline.append({"entity_id": eid, "name": name, "since": st.get("last_changed")})
    low.sort(key=lambda x: (x["level"] is None, x["level"] or 0))
    offline.sort(key=lambda x: x["name"].lower())
    return {"ok": True, "low": low, "offline": offline}


# ---------------------------------------------------------------- peak alerts
def _peak_log(add: dict | None = None) -> list:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='peak_log'").fetchone()
        log = json.loads(row["value"]) if row and row["value"] else []
        if add:
            log = [x for x in log if x.get("day", "") >= (date.today() - timedelta(days=40)).isoformat()] + [add]
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('peak_log', ?)", (json.dumps(log),))
        return log


def _peak_tick(s: dict):
    if not s.get("peakAlerts", True) or not ha_svc.peak_now():
        _PEAK_SEEN.clear()
        return
    now = time.time()
    for st in _states():
        eid = st.get("entity_id", "")
        if not eid.startswith("climate."):
            continue
        a = st.get("attributes") or {}
        on = st.get("state") not in ("off", "unavailable", "unknown")
        if not on:
            _PEAK_SEEN.pop(eid, None)
            continue
        first = _PEAK_SEEN.setdefault(eid, now)
        key = f"peak:{eid}"
        if now - first >= 180 and _SENT.get(key) != date.today():
            _SENT[key] = date.today()
            name = (a.get("friendly_name") or eid).replace(" Thermostat", "")
            _push(f"Peak hours: the {name} thermostat is still on ({st.get('state').replace('_', '/')}). "
                  "Santee Cooper bills on peak use. Turn it off or check the peak schedule.", "familyhub-peak")
            _peak_log({"day": date.today().isoformat(), "at": datetime.now().strftime("%H:%M"), "name": name})


# ---------------------------------------------------------------- nightly check
def night_report() -> list:
    """What's not buttoned up right now (names only). Empty = all good."""
    issues = []
    tiles = []
    try:
        tiles = [t for g in ha_svc.get_home().get("groups", []) for t in g.get("tiles", [])]
    except Exception:
        pass
    gcover = ha_svc.has_garage_cover([t for t in tiles if t["domain"] == "cover"])
    for t in tiles:
        d = t["domain"]
        if d == "lock" and t["state"] not in ("locked", "unavailable", "unknown"):
            issues.append(f"{t['name']} is unlocked")
        elif d == "cover" and t["state"] in ("open", "opening"):
            issues.append(f"{t['name']} is open")
        elif d == "binary_sensor" and t.get("device_class") in ("door", "window", "garage_door", "opening") and t.get("on"):
            lbl = ha_svc.opening_label(t, gcover)
            if lbl:
                issues.append(f"{lbl} is open")
        elif d == "alarm_control_panel" and t["state"] == "disarmed":
            issues.append("the alarm isn't set")
    return list(dict.fromkeys(issues))


def _night_tick(s: dict, now: datetime):
    if not s.get("nightCheck", True):
        return
    at = str(s.get("nightCheckTime") or "22:30")
    if now.strftime("%H:%M") != at[:5] or _SENT.get("night") == now.date():
        return
    _SENT["night"] = now.date()
    issues = night_report()
    if issues:
        _push("Night check: " + "; ".join(issues) + ". (Good night on the wall locks up and sets the alarm.)", "familyhub-night")


# ---------------------------------------------------------------- weekly
def week(end: date | None = None) -> list:
    """Last 7 days of heat/AC minutes (oldest first), from the Today timeline. Past days are cached."""
    from . import timeline
    end = end or date.today()
    out = []
    for i in range(6, -1, -1):
        d = end - timedelta(days=i)
        key = d.isoformat()
        cached = _WEEK_CACHE.get(key) if d < date.today() else None
        if cached is None:
            r = timeline.get(key)
            st = (r or {}).get("stats") or {}
            cached = {"day": key, "heat_min": st.get("heat_min", 0), "cool_min": st.get("cool_min", 0),
                      "hvac_peak_min": st.get("hvac_peak_min", 0), "ok": bool(r and r.get("ok")),
                      "estimated": any(x.get("estimated") for x in (r or {}).get("rows", []))}
            if d < date.today() and cached["ok"]:
                _WEEK_CACHE[key] = cached
        out.append(cached)
    return out


_WEEK_CACHE: dict = {}


def _weekly_tick(s: dict, now: datetime):
    if not s.get("weeklySummary", True) or now.weekday() != 6 or now.strftime("%H:%M") != "18:00" or _SENT.get("week") == now.date():
        return
    _SENT["week"] = now.date()
    days = week()
    heat = sum(d["heat_min"] for d in days) / 60
    cool = sum(d["cool_min"] for d in days) / 60
    peak = sum(d["hvac_peak_min"] for d in days)
    parts = [f"This week (both thermostats): heat ran about {heat:.0f} h, AC about {cool:.0f} h."]
    parts.append("No heat/AC during peak ✓." if not peak else f"Heat/AC ran {peak} min during peak hours.")
    h = health()
    if h.get("low"):
        parts.append("Low batteries: " + ", ".join(x["name"] + (f" {x['level']}%" if x["level"] is not None else "") for x in h["low"][:5]) + ".")
    _push(" ".join(parts), "familyhub-week")


def _rain_openings() -> list:
    """Things rain would get into: an open garage door (cover) or an open window."""
    try:
        tiles = [t for g in ha_svc.get_home().get("groups", []) for t in g.get("tiles", [])]
    except Exception:
        return []
    out = [t["name"] for t in tiles if t["domain"] == "cover" and t["state"] in ("open", "opening")]
    out += [t["name"] for t in tiles if t["domain"] == "binary_sensor" and t.get("device_class") == "window" and t.get("on")]
    return out


# ---------------------------------------------------------------- loop
def _loop():
    time.sleep(30)
    while True:
        try:
            if not ha_svc.demo_mode() and ha_svc.ha_url():
                s, now = _settings(), datetime.now()
                _peak_tick(s)
                _night_tick(s, now)
                _weekly_tick(s, now)
                from . import laundry
                laundry.tick()
                from . import xmas
                xmas.tick()
                from . import wx_alerts
                wx_alerts.tick(_push, s)
                wx_alerts.rain_tick(_push, s, _rain_openings)
        except Exception:
            pass
        time.sleep(60 - datetime.now().second % 60 or 60)


def start():
    threading.Thread(target=_loop, daemon=True, name="house-watch").start()
