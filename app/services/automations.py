"""Automations page: every Home Assistant routine in plain English, with on/off, last run, the settings
you can change (HA helpers), and a simple builder for new routines.

    list_all()             -> {connected, groups:[{key, title, blurb, status, automations, settings}], mine:[...], choices}
    set_automation(eid,on) -> automation.turn_on/off
    set_helper(eid,value)  -> input_number / input_datetime / input_boolean / input_text (light lists)
    get_routine(id) / save_routine(spec) / delete_routine(id)  -> "Your routines" made with the builder

Only automation.*, input_number.*, input_datetime.*, input_boolean.* and input_text.* can be changed here,
and the builder never unlocks a door or disarms the alarm.
The FamilyHub packages (docs/ha/*.yaml) give every automation an id starting fh_; builder routines use fhu_.
"""
from __future__ import annotations

import datetime
import json
import re
import time
import urllib.error

from . import ha_svc

# yaml id -> plain English. {input_x.y} is replaced with that setting's current value (8:00 PM, 10 %, ...).
DESCRIBE = {
    # peak_thermostat.yaml
    "fh_peak_precondition": "An hour before peak, pre-heat to {input_number.peak_preheat} (winter) or pre-cool to {input_number.peak_precool} (summer).",
    "fh_peak_start": "When peak starts, turn both thermostats off.",
    "fh_peak_end": "When peak ends, turn them back on in the mode they were in, at the schedule's temperatures.",
    "fh_sched_apply": "At {input_datetime.sched_day_start} (day) and {input_datetime.sched_night_start} (night): set both thermostats to the schedule.",
    "fh_peak_enforce": "During peak, if a thermostat gets turned back on, turn it off again (unless the safety limit is why).",
    "fh_outdoor_holiday_now": "If holiday season starts after dark (or 'tonight anyway' is switched on), the holiday lights come on right away.",
    "fh_peak_safety": "Safety only: if a room drops to {input_number.peak_safe_low} or reaches {input_number.peak_safe_high} during peak, that thermostat comes back on.",
    # outdoor_lights.yaml
    "fh_outdoor_sunset": "Sunset: holiday lights on in holiday season, otherwise the nightly lights on.",
    "fh_outdoor_1150": "Holiday season, {input_datetime.fh_outdoor_switchover}: holiday lights off, nightly lights on for the rest of the night.",
    "fh_outdoor_sunrise": "Sunrise: everything outside off.",
    "fh_christmas_upstairs_on": "Christmas season (from {input_datetime.fh_outdoor_xmas_start}): window lights on at sunset.",
    "fh_christmas_upstairs_off": "Window lights off at {input_datetime.fh_outdoor_windows_off}.",
    # kitchen_lights.yaml
    "fh_kitchen_evening": "{input_datetime.fh_kitchen_evening_on}: kitchen uppers on warm white {input_number.fh_kitchen_evening_bright}, back patio on.",
    "fh_patio_off": "{input_datetime.fh_kitchen_patio_off}: back patio off.",
    "fh_kitchen_uppers_midnight": "{input_datetime.fh_kitchen_uppers_off}: kitchen uppers off.",
    "fh_kitchen_uppers_motion_on": "{input_datetime.fh_kitchen_upper_motion_from}–{input_datetime.fh_kitchen_motion_until}: motion turns the uppers on at {input_number.fh_kitchen_motion_bright}.",
    "fh_kitchen_uppers_motion_off": "Overnight: uppers off after {input_number.fh_kitchen_quiet_minutes} with no motion.",
    "fh_kitchen_lowers_motion_on": "{input_datetime.fh_kitchen_lower_motion_from}–{input_datetime.fh_kitchen_motion_until}: motion turns the lowers on at {input_number.fh_kitchen_motion_bright}.",
    "fh_kitchen_lowers_motion_off": "At night: lowers off after {input_number.fh_kitchen_quiet_minutes} with no motion.",
    "fh_kitchen_morning_off": "{input_datetime.fh_kitchen_morning_off}: all kitchen lights off.",
}

# settings shown per group, in this order (anything else matching `helpers` follows, by name)
GROUPS = [
    {"key": "peak", "title": "Thermostats", "file": "peak_thermostat",
     "blurb": "The daily heat and AC schedule, plus Santee Cooper peak hours (heat and AC off so nothing sets a demand charge).",
     "auto": r"^fh_(peak|sched)_", "helpers": r"^(input_number|input_datetime|input_boolean)\.(peak_|sched_)",
     "order": [], "status": ["binary_sensor.santee_cooper_peak_now", "binary_sensor.peak_summer_season"]},
    {"key": "outdoor", "title": "Outdoor & holiday lights", "file": "outdoor_lights",
     "blurb": "Nightly lights from sunset to sunrise; holiday lights switch on by date (October, and Thanksgiving into January).",
     "auto": r"^fh_(outdoor|christmas)_", "helpers": r"^(input_boolean|input_datetime|input_number|input_text)\.(holiday_|fh_outdoor_)",
     "order": ["input_text.fh_outdoor_night_lights", "input_text.fh_outdoor_holiday_lights", "input_text.fh_outdoor_window_lights",
               "input_datetime.fh_outdoor_xmas_start", "input_datetime.fh_outdoor_switchover", "input_datetime.fh_outdoor_windows_off",
               "input_boolean.fh_outdoor_halloween", "input_boolean.fh_outdoor_christmas",
               "input_number.fh_outdoor_xmas_last_day", "input_boolean.holiday_lights_force"],
     "status": ["binary_sensor.halloween_season", "binary_sensor.christmas_season"]},
    {"key": "kitchen", "title": "Kitchen lights", "file": "kitchen_lights",
     "blurb": "Evening glow, night-light on motion, all off in the morning. Same as the old Alexa routines.",
     "auto": r"^fh_(kitchen|patio)_", "helpers": r"^(input_boolean|input_datetime|input_number|input_text)\.fh_kitchen_",
     "order": ["input_text.fh_kitchen_upper_lights", "input_text.fh_kitchen_lower_lights", "input_text.fh_kitchen_patio_lights",
               "input_datetime.fh_kitchen_evening_on", "input_number.fh_kitchen_evening_bright", "input_datetime.fh_kitchen_patio_off",
               "input_datetime.fh_kitchen_uppers_off", "input_datetime.fh_kitchen_lower_motion_from",
               "input_datetime.fh_kitchen_upper_motion_from", "input_datetime.fh_kitchen_motion_until",
               "input_number.fh_kitchen_motion_bright", "input_number.fh_kitchen_quiet_minutes",
               "input_datetime.fh_kitchen_morning_off"],
     "status": []},
]

# helpers that are bookkeeping, not settings
_HIDDEN = re.compile(r"saved|\(automatic\)|_active$|_ready$", re.I)
_WRITABLE = ("automation", "input_number", "input_datetime", "input_boolean", "input_text")
_PICKABLE = ("light", "switch")          # what a light list (input_text) may hold


def _states() -> list:
    if ha_svc.demo_mode():
        return [{"entity_id": e, "state": v["state"], "attributes": v.get("attributes", {})} for e, v in _DEMO.items()] \
            + [s for s in (_demo_devices())]
    try:
        from . import ha_live
        st = ha_live.states()
        if st is None or not any(x["entity_id"].startswith("automation.") for x in st):
            st = ha_svc._request("/api/states") or st or []       # mirror can be stale right after an HA restart
        return st
    except Exception:
        return []


def _demo_devices() -> list:
    out = []
    for e, v in getattr(ha_svc, "_DEMO", {}).items():
        out.append({"entity_id": e, "state": v.get("state"), "attributes": v.get("attributes", {})})
    return out


def _nice_time(v: str) -> str:
    try:
        h, m = int(v[:2]), int(v[3:5])
    except (ValueError, TypeError):
        return v or ""
    if h == 0 and m == 0:
        return "midnight"
    return f"{(h % 12) or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def _nice(s: dict | None) -> str:
    if not s:
        return "?"
    d, a, v = s["entity_id"].split(".")[0], s.get("attributes") or {}, s.get("state")
    if d == "input_datetime" and a.get("has_date") and not a.get("has_time"):
        try:
            dd = datetime.date.fromisoformat(str(v)[:10])
            return "the day after Thanksgiving" if dd.year == 1970 or dd.month < 11 else dd.strftime("%B %-d")
        except ValueError:
            return "the day after Thanksgiving"
    if d == "input_datetime":
        return _nice_time(v)
    if d == "input_number":
        try:
            n = float(v)
            n = int(n) if n == int(n) else n
        except (TypeError, ValueError):
            return str(v)
        u = a.get("unit_of_measurement") or ""
        return f"{n}°" if "°" in u else f"{n} min" if u == "min" else f"{n}{u}" if u else str(n)
    return str(v)


def _describe(yid: str, by_id: dict) -> str:
    text = DESCRIBE.get(yid, "")
    return re.sub(r"\{(input_[a-z_]+\.[a-z0-9_]+)\}", lambda m: _nice(by_id.get(m.group(1))), text)


def _setting(s: dict, names: dict) -> dict:
    eid, a = s["entity_id"], s.get("attributes") or {}
    d = eid.split(".")[0]
    out = {"entity_id": eid, "name": a.get("friendly_name") or eid, "value": s.get("state")}
    if d == "input_number":
        out.update(kind="number", min=a.get("min"), max=a.get("max"), step=a.get("step"), unit=a.get("unit_of_measurement") or "")
    elif d == "input_datetime" and a.get("has_date") and not a.get("has_time"):
        v = s.get("state") or ""
        out.update(kind="date", value=v[:10] if v[:4] not in ("", "1970", "unkn") else "")
    elif d == "input_datetime":
        out.update(kind="time", value=(s.get("state") or "")[:5])
    elif d == "input_boolean":
        out.update(kind="toggle")
    elif d == "input_text":
        ids = [x.strip() for x in str(s.get("state") or "").split(",") if x.strip() and x.strip() not in ("unknown", "unavailable")]
        out.update(kind="lights", value=ids, labels=[names.get(i, i) for i in ids])
        fixes = {i: _guess(i, names) for i in ids if i not in names}
        fixes = {k: v for k, v in fixes.items() if v}
        if fixes:       # e.g. switch.exterior_lights_smart_plug is really light.exterior_lights_smart_plug
            out["fixes"] = [{"from": k, "to": v, "name": names[v]} for k, v in fixes.items()]
    return out


def _guess(missing: str, names: dict):
    """The device a stale id most likely meant: same object id in the other domain, a _2-style rename, or the
    same words in the name. Only lights/switches, and only when there's exactly one candidate."""
    obj = missing.split(".", 1)[-1]
    pool = [e for e in names if e.split(".")[0] in ("light", "switch")]
    for test in (lambda e: e.split(".", 1)[1] == obj,
                 lambda e: re.fullmatch(re.escape(obj) + r"_\d+", e.split(".", 1)[1]) is not None,
                 lambda e: re.sub(r"[^a-z0-9]+", "_", str(names[e]).lower()).strip("_") == obj,
                 lambda e: e.split(".", 1)[1].startswith(obj + "_"),                     # fridge_upper -> fridge_upper_led
                 lambda e: set(obj.split("_")) <= set(re.findall(r"[a-z0-9]+", str(names[e]).lower()))):   # back_patio -> "Back Patio Govee"
        hits = [e for e in pool if test(e)]
        if len(hits) == 1:
            return hits[0]
    return None


def _choices(states: list) -> dict:
    """Devices the pickers and the routine builder can offer, grouped."""
    c = {k: [] for k in ("lights", "switches", "covers", "locks", "climates", "media", "sensors", "people", "alarms")}
    for s in states:
        eid, a = s["entity_id"], s.get("attributes") or {}
        d, name = eid.split(".")[0], a.get("friendly_name") or eid
        if d == "binary_sensor" and a.get("device_class") not in ("door", "window", "garage_door", "opening", "motion", "occupancy", "presence", "moisture"):
            continue
        key = {"light": "lights", "switch": "switches", "cover": "covers", "lock": "locks", "climate": "climates",
               "media_player": "media", "binary_sensor": "sensors", "person": "people", "alarm_control_panel": "alarms"}.get(d)
        if key:
            item = {"id": eid, "name": name}
            if d == "binary_sensor":
                item["kind"] = "motion" if a.get("device_class") in ("motion", "occupancy", "presence") else "leak" if a.get("device_class") == "moisture" else "door"
            c[key].append(item)
    for v in c.values():
        v.sort(key=lambda x: x["name"].lower())
    return c


def list_all() -> dict:
    states = _states()
    if not states and not ha_svc.demo_mode():
        return {"connected": False, "groups": []}
    by_id = {s["entity_id"]: s for s in states}
    names = {s["entity_id"]: (s.get("attributes") or {}).get("friendly_name") or s["entity_id"] for s in states}
    autos = [s for s in states if s["entity_id"].startswith("automation.")]
    used, groups = set(), []
    conv = set(_converted())
    for g in GROUPS:
        if g["key"] in conv:                       # rebuilt as "Your routines"; packaged versions are off
            used.update(s["entity_id"] for s in autos if re.search(g["auto"], str((s.get("attributes") or {}).get("id") or "")))
            continue
        items = []
        for s in autos:
            a = s.get("attributes") or {}
            yid = str(a.get("id") or "")
            if re.search(g["auto"], yid):
                used.add(s["entity_id"])
                if yid.endswith("_defaults"):
                    continue                       # one-time setup step, not a routine
                items.append({"entity_id": s["entity_id"], "name": a.get("friendly_name") or s["entity_id"],
                              "on": s.get("state") == "on", "last": a.get("last_triggered"), "about": _describe(yid, by_id)})
        settings = []
        if g["helpers"]:
            found = [s for s in states if re.search(g["helpers"], s["entity_id"])
                     and not _HIDDEN.search(s["entity_id"] + " " + str((s.get("attributes") or {}).get("friendly_name", "")))]
            order = {e: i for i, e in enumerate(g.get("order") or [])}
            found.sort(key=lambda s: (order.get(s["entity_id"], 999), names[s["entity_id"]].lower()))
            settings = [_setting(s, names) for s in found]
        status = [{"name": names.get(e, e), "on": by_id[e].get("state") == "on"} for e in g["status"] if e in by_id]
        groups.append({"key": g["key"], "title": g["title"], "blurb": g["blurb"], "file": g["file"], "installed": bool(items),
                       "status": status, "automations": items, "settings": settings})
    mine, other = [], []
    for s in autos:
        if s["entity_id"] in used:
            continue
        a = s.get("attributes") or {}
        row = {"entity_id": s["entity_id"], "name": a.get("friendly_name") or s["entity_id"],
               "on": s.get("state") == "on", "last": a.get("last_triggered"), "about": "", "id": str(a.get("id") or "")}
        (mine if row["id"].startswith("fhu_") else other).append(row)
    for r in mine[:40]:
        spec = _MINE.get(r["id"]) if ha_svc.demo_mode() else (get_routine(r["id"]).get("spec"))
        r["about"] = summary(spec, names) if spec else "Changed in Home Assistant; edit it there."
        r["editable"] = bool(spec)
    if other:
        groups.append({"key": "other", "title": "Made in Home Assistant", "blurb": "Routines created in the Home Assistant app.",
                       "installed": True, "status": [], "automations": other, "settings": []})
    return {"connected": True, "demo": ha_svc.demo_mode(), "groups": groups, "mine": mine, "choices": _choices(states),
            "ha_total": len(autos),
            "fh_ids": sorted(str((x.get("attributes") or {}).get("id") or "") for x in autos if str((x.get("attributes") or {}).get("id") or "").startswith("fh_")),
            "helpers_found": sum(1 for x in states if x["entity_id"].startswith(("input_number.peak_", "input_datetime.peak_", "input_boolean.holiday_")))}


def set_automation(entity_id: str, on: bool) -> dict:
    if not entity_id.startswith("automation."):
        return {"ok": False, "reason": "not an automation"}
    if ha_svc.demo_mode() and entity_id in _DEMO:
        _DEMO[entity_id]["state"] = "on" if on else "off"
        return {"ok": True, "demo": True}
    return ha_svc.call_service("automation", "turn_on" if on else "turn_off", entity_id)


def set_helper(entity_id: str, value) -> dict:
    r = _set_helper(entity_id, value)
    # a thermostat schedule change takes effect now, not at the next day/night switch-over
    if r.get("ok") and not r.get("demo") and re.match(r"^(input_number|input_datetime)\.sched_|^input_boolean\.sched_enabled$", entity_id):
        try:
            if ha_svc._current_state("input_boolean.sched_enabled") == "on" and ha_svc._current_state("input_boolean.peak_active") != "on":
                ha_svc.call_service("script", "turn_on", "script.fh_thermostat_schedule")
        except Exception:
            pass
    return r


def _set_helper(entity_id: str, value) -> dict:
    d = entity_id.split(".")[0]
    if d not in _WRITABLE[1:]:
        return {"ok": False, "reason": "can't change that from here"}
    if d == "input_text":
        ids = value if isinstance(value, list) else str(value or "").split(",")
        ids = [i.strip() for i in ids if i and i.strip()]
        if any(i.split(".")[0] not in _PICKABLE or not re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", i) for i in ids):
            return {"ok": False, "reason": "only lights and plugs can go in this list"}
        value = ",".join(dict.fromkeys(ids))
        if len(value) > 255:
            return {"ok": False, "reason": "too many lights in one list (Home Assistant's limit is 255 characters)"}
    if ha_svc.demo_mode() and entity_id in _DEMO:
        _DEMO[entity_id]["state"] = ("on" if value in (True, "on", "true", 1) else "off") if d == "input_boolean" \
            else (str(value)[:5] + ":00" if d == "input_datetime" else str(value))
        return {"ok": True, "demo": True}
    if d == "input_text":
        return ha_svc.call_service("input_text", "set_value", entity_id, {"value": value})
    if d == "input_number":
        try:
            num = float(value)
        except (TypeError, ValueError):
            return {"ok": False, "reason": "That needs to be a number"}
        return ha_svc.call_service("input_number", "set_value", entity_id, {"value": num})
    if d == "input_datetime" and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value)):
        return ha_svc.call_service("input_datetime", "set_datetime", entity_id, {"date": str(value)})
    if d == "input_datetime":
        v = str(value)
        if not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", v):
            return {"ok": False, "reason": "time must be HH:MM"}
        return ha_svc.call_service("input_datetime", "set_datetime", entity_id, {"time": v if v.count(":") == 2 else v + ":00"})
    on = value in (True, "on", "true", 1)
    return ha_svc.call_service("input_boolean", "turn_on" if on else "turn_off", entity_id)


# ---- "Your routines": the simple builder -----------------------------------------------------------
# A spec is what the builder form sends; it's stored (as JSON) in the automation's description so it can
# be opened and edited again. It becomes a normal HA automation (shows in HA's Automations list too).
#
# spec = {name, when:{type, at, event, offset, entity, to, person}, days:[mon..sun], dark:bool, home:bool,
#         do:[{type, entities, pct, mode, temp, message}]}
_TAG = "FamilyHub routine — edit it in FamilyHub. "
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DAYNAME = dict(zip(DAYS, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]))
_ID = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


def _ids(lst, *domains) -> list:
    out = [str(x) for x in (lst or []) if _ID.match(str(x)) and str(x).split(".")[0] in domains]
    return list(dict.fromkeys(out))


def _when_text(w: dict, names: dict) -> str:
    t, n = w.get("type"), lambda e: names.get(e, e)
    if t == "time":
        return f"At {_nice_time(w.get('at') or '')}"
    if t == "sun":
        off = int(w.get("offset") or 0)
        when = "sunset" if w.get("event") == "sunset" else "sunrise"
        return (f"{abs(off)} min {'before' if off < 0 else 'after'} {when}" if off else f"At {when}").capitalize()
    if t == "device":
        to = w.get("to")
        motion = bool(re.search(r"motion|occupancy|presence", str(w.get("entity") or "")))
        verb = {"on": "detects motion" if motion else "opens", "off": "goes quiet" if motion else "closes", "open": "opens",
                "closed": "closes", "unlocked": "is unlocked", "locked": "is locked"}.get(to, to)
        mins = int(w.get("for") or 0)
        return f"When {n(w.get('entity'))} {verb}" + (f" for {mins} min" if mins and to in ("off", "closed") else "")
    if t == "arrive":
        return "When the first person gets home" if not w.get("person") else f"When {n(w.get('person'))} gets home"
    if t == "leave":
        return "When everyone has left" if not w.get("person") else f"When {n(w.get('person'))} leaves"
    if t == "alarm":
        return {"armed_home": "When the alarm is armed Stay", "armed_away": "When the alarm is armed Away",
                "armed_night": "When the alarm is armed Night", "disarmed": "When the alarm is disarmed",
                "triggered": "When the alarm goes off"}.get(w.get("to"), "When the alarm changes")
    return "When…"


def _do_text(a: dict, names: dict) -> str:
    t = a.get("type")
    lst = ", ".join(names.get(e, e) for e in (a.get("entities") or [])) or "nothing picked"
    white = {"warm": " warm white", "cool": " cool white"}.get(a.get("white") or "", "")
    return {"on": f"turn on {lst}", "off": f"turn off {lst}",
            "dim": f"set {lst} to {a.get('pct', 50)}%{white}",
            "thermostat": f"set {lst} to {('off' if a.get('mode') == 'off' else str(a.get('mode') or 'heat').replace('_', '/') + ' ' + str(a.get('temp') or '') + '°')}",
            "lock": f"lock {lst}", "close": f"close {lst}",
            "notify": f"send phones \"{a.get('message', '')}\"", "say": f"say on the wall \"{a.get('message', '')}\""}.get(t, t or "")


def summary(spec: dict, names: dict | None = None) -> str:
    names = names or {}
    s = _when_text(spec.get("when") or {}, names)
    days = spec.get("days") or []
    if days and len(days) < 7:
        s += (" on weekdays" if days == DAYS[:5] else " on weekends" if days == DAYS[5:] else " on " + ", ".join(_DAYNAME.get(d, d) for d in days))
    if spec.get("between"):
        b = spec["between"]
        s += f", only between {_nice_time(b.get('after') or '')} and {_nice_time(b.get('before') or '')}"
    if spec.get("dates"):
        dr = spec["dates"]
        s += f", {'except' if spec.get('dates_except') else 'only'} {_nice_md(dr.get('from'))} to {_nice_md(dr.get('to'))}"
    if spec.get("dark"):
        s += ", only after dark"
    if spec.get("home"):
        s += ", only if someone's home"
    if spec.get("ifoff"):
        s += ", only if those lights are off"
    acts = [_do_text(a, names) for a in (spec.get("do") or [])]
    return s + ": " + ("; ".join(acts) if acts else "nothing yet") + "."


def _nice_md(md) -> str:
    try:
        return datetime.date(2000, int(str(md)[:2]), int(str(md)[3:5])).strftime("%b %-d")
    except (ValueError, TypeError):
        return str(md)


def _md(v) -> str:
    v = str(v or "")
    if not re.fullmatch(r"\d{2}-\d{2}", v):
        raise ValueError("Pick both dates")
    datetime.date(2000, int(v[:2]), int(v[3:]))          # raises on Feb 31 etc.
    return v


def _hm(v, what) -> str:
    v = str(v or "")
    if not re.fullmatch(r"\d{1,2}:\d{2}", v) or int(v.split(":")[0]) > 23 or int(v.split(":")[1]) > 59:
        raise ValueError(f"Pick the {what} time")
    return v.zfill(5) + ":00"


def _notify_services() -> list:
    try:
        for dom in ha_svc._request("/api/services") or []:
            if dom.get("domain") == "notify":
                return sorted(s for s in (dom.get("services") or {}) if s.startswith("mobile_app_"))
    except Exception:
        pass
    return []


def build(spec: dict) -> dict:
    """Builder spec -> Home Assistant automation config. Raises ValueError with a plain message."""
    w = spec.get("when") or {}
    t = w.get("type")
    if t == "time":
        at = str(w.get("at") or "")
        if not re.fullmatch(r"\d{1,2}:\d{2}", at) or int(at.split(":")[0]) > 23 or int(at.split(":")[1]) > 59:
            raise ValueError("Pick a time")
        trig = {"trigger": "time", "at": at + ":00"}
    elif t == "sun":
        off = max(-180, min(180, int(w.get("offset") or 0)))
        trig = {"trigger": "sun", "event": "sunset" if w.get("event") == "sunset" else "sunrise"}
        if off:
            trig["offset"] = f"{'-' if off < 0 else ''}00:{abs(off):02d}:00" if abs(off) < 60 else f"{'-' if off < 0 else ''}{abs(off) // 60:02d}:{abs(off) % 60:02d}:00"
    elif t == "device":
        e = str(w.get("entity") or "")
        if not _ID.match(e) or e.split(".")[0] not in ("binary_sensor", "cover", "lock", "light", "switch", "media_player"):
            raise ValueError("Pick the door, sensor or device")
        trig = {"trigger": "state", "entity_id": e, "to": str(w.get("to") or "on")}
        mins = max(0, min(240, int(w.get("for") or 0)))
        if mins and trig["to"] in ("off", "closed"):
            trig["for"] = {"minutes": mins}
    elif t in ("arrive", "leave"):
        p = str(w.get("person") or "")
        if p:
            if not p.startswith("person."):
                raise ValueError("Pick a person")
            trig = {"trigger": "state", "entity_id": p, "to": "home"} if t == "arrive" else {"trigger": "state", "entity_id": p, "from": "home"}
        else:
            trig = {"trigger": "numeric_state", "entity_id": "zone.home", "above": 0} if t == "arrive" \
                else {"trigger": "numeric_state", "entity_id": "zone.home", "below": 1}
    elif t == "alarm":
        to = str(w.get("to") or "")
        if to not in ("armed_home", "armed_away", "armed_night", "disarmed", "triggered"):
            raise ValueError("Pick what the alarm does")
        e = str(w.get("entity") or "")
        trig = {"trigger": "state", "entity_id": e, "to": to} if _ID.match(e) and e.startswith("alarm_control_panel.") \
            else {"trigger": "state", "entity_id": [s["entity_id"] for s in _states() if s["entity_id"].startswith("alarm_control_panel.")] or "alarm_control_panel.none", "to": to}
    else:
        raise ValueError("Pick when it should happen")

    conds = []
    days = [d for d in (spec.get("days") or []) if d in DAYS]
    if days and len(days) < 7:
        conds.append({"condition": "time", "weekday": days})
    if spec.get("between"):
        b = spec["between"]
        conds.append({"condition": "time", "after": _hm(b.get("after"), "start"), "before": _hm(b.get("before"), "end")})
    if spec.get("dates"):
        a, b = _md(spec["dates"].get("from")), _md(spec["dates"].get("to"))
        expr = f"(('{a}' <= md <= '{b}') if '{a}' <= '{b}' else (md >= '{a}' or md <= '{b}'))"   # wraps past New Year
        conds.append({"condition": "template", "value_template":
                      "{% set md = now().strftime('%m-%d') %}{{ " + ("not " if spec.get("dates_except") else "") + expr + " }}"})
    if spec.get("dark"):
        conds.append({"condition": "state", "entity_id": "sun.sun", "state": "below_horizon"})
    if spec.get("home"):
        conds.append({"condition": "numeric_state", "entity_id": "zone.home", "above": 0})

    acts = []
    for a in spec.get("do") or []:
        k = a.get("type")
        if k in ("on", "off"):
            ids = _ids(a.get("entities"), "light", "switch", "fan", "media_player")     # garage doors: "close" only
            if ids:
                acts.append({"action": f"homeassistant.turn_{k}", "target": {"entity_id": ids}})
        elif k == "dim":
            ids = _ids(a.get("entities"), "light")
            if ids:
                data = {"brightness_pct": max(1, min(100, int(float(a.get("pct") or 50))))}
                if a.get("white") in ("warm", "cool"):
                    data["color_temp_kelvin"] = 2700 if a["white"] == "warm" else 5000
                acts.append({"action": "light.turn_on", "target": {"entity_id": ids}, "data": data})
        elif k == "thermostat":
            ids = _ids(a.get("entities"), "climate")
            mode = a.get("mode") or "heat"
            if ids and mode in ("off", "heat", "cool", "heat_cool", "auto"):
                acts.append({"action": "climate.set_hvac_mode", "target": {"entity_id": ids}, "data": {"hvac_mode": mode}})
                if mode in ("heat", "cool") and a.get("temp"):
                    acts.append({"delay": {"seconds": 5}})
                    acts.append({"action": "climate.set_temperature", "target": {"entity_id": ids},
                                 "data": {"temperature": max(45, min(95, int(float(a.get("temp")))))}})
        elif k == "lock":                                    # lock only — never unlock from a routine
            ids = _ids(a.get("entities"), "lock")
            if ids:
                acts.append({"action": "lock.lock", "target": {"entity_id": ids}})
        elif k == "close":                                   # garage doors: close only
            ids = _ids(a.get("entities"), "cover")
            if ids:
                acts.append({"action": "cover.close_cover", "target": {"entity_id": ids}})
        elif k == "notify":
            msg = str(a.get("message") or "").strip()[:200]
            if msg:
                for svc in _notify_services():
                    acts.append({"action": f"notify.{svc}", "data": {"title": spec.get("name") or "FamilyHub", "message": msg},
                                 "continue_on_error": True})
        elif k == "say":
            msg = str(a.get("message") or "").strip()[:200]
            if msg:
                acts.append({"event": "familyhub", "event_data": {"kind": "say", "message": msg}})
    if not acts:
        raise ValueError("Add at least one thing for it to do")
    if spec.get("ifoff"):           # "only if those lights are off" — the lights the routine turns on / dims
        offs = []
        for a in spec.get("do") or []:
            if a.get("type") in ("on", "dim"):
                offs += _ids(a.get("entities"), "light", "switch")
        if offs:
            conds.append({"condition": "state", "entity_id": list(dict.fromkeys(offs)), "state": "off"})
    name = str(spec.get("name") or "").strip()[:80] or summary(spec).split(":")[0]
    return {"alias": name, "description": _TAG + json.dumps(spec, separators=(",", ":")),
            "mode": "single", "triggers": [trig], "conditions": conds, "actions": acts}


_MINE: dict[str, dict] = {}      # demo mode store


def _converted() -> list:
    from ..db import get_db
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='routines_converted'").fetchone()
            return json.loads(row["value"]) if row else []
    except Exception:
        return []


def convert_to_routines(keys=("outdoor", "kitchen")) -> dict:
    """Rebuild the packaged outdoor + kitchen schedules as ordinary FamilyHub routines (same times, the lights
    the cards hold — stale names swapped for the device they meant), then switch the packaged versions off and
    hide their cards. Thermostats stay packaged (peak hours need save/restore)."""
    states = _states()
    names = {s["entity_id"]: (s.get("attributes") or {}).get("friendly_name") or s["entity_id"] for s in states}
    st = {s["entity_id"]: s.get("state") for s in states}

    def lst(helper, guess_re=None):
        ids = [x.strip() for x in str(st.get(helper) or "").split(",") if x.strip() and x.strip() not in ("unknown", "unavailable")]
        ids = [i if i in names else (_guess(i, names) or i) for i in ids]
        ids = [i for i in ids if i in names]
        if not ids and guess_re:
            ids = [e for e in names if e.split(".")[0] in ("light", "switch") and re.search(guess_re, names[e], re.I)]
        return list(dict.fromkeys(ids))

    def hm(helper, default):
        v = str(st.get(helper) or "")[:5]
        return v if re.fullmatch(r"\d{2}:\d{2}", v) else default

    def num(helper, default):
        try:
            return int(float(st.get(helper)))
        except (TypeError, ValueError):
            return default

    every = [d for d in DAYS]
    R = []
    if "outdoor" in keys:
        night = lst("input_text.fh_outdoor_night_lights", r"front porch|driveway|side door")
        plug = lst("input_text.fh_outdoor_holiday_lights", r"exterior lights")
        windows = lst("input_text.fh_outdoor_window_lights")
        xs = str(st.get("input_datetime.fh_outdoor_xmas_start") or "")
        xmas_from = xs[5:10] if re.fullmatch(r"\d{4}-(11|12)-\d{2}.*", xs) else "11-27"
        last = f"01-{num('input_number.fh_outdoor_xmas_last_day', 6):02d}"
        hol_from = "10-01" if st.get("input_boolean.fh_outdoor_halloween") != "off" else xmas_from
        switch_at, win_off = hm("input_datetime.fh_outdoor_switchover", "23:50"), hm("input_datetime.fh_outdoor_windows_off", "22:30")
        hol = {"from": hol_from, "to": last}
        R += [
            {"name": "Holiday lights on at sunset", "when": {"type": "sun", "event": "sunset", "offset": 0}, "dates": hol,
             "do": [{"type": "on", "entities": plug}]},
            {"name": "Holiday lights off, front lights on", "when": {"type": "time", "at": switch_at}, "dates": hol,
             "do": [{"type": "off", "entities": plug}, {"type": "on", "entities": night}]},
            {"name": "Front lights on at sunset", "when": {"type": "sun", "event": "sunset", "offset": 0}, "dates": hol, "dates_except": True,
             "do": [{"type": "on", "entities": night}]},
            {"name": "Outside lights off at sunrise", "when": {"type": "sun", "event": "sunrise", "offset": 0},
             "do": [{"type": "off", "entities": list(dict.fromkeys(night + plug))}]},
            {"name": "Christmas window lights on at sunset", "when": {"type": "sun", "event": "sunset", "offset": 0},
             "dates": {"from": xmas_from, "to": last}, "do": [{"type": "on", "entities": windows}]},
            {"name": "Christmas window lights off", "when": {"type": "time", "at": win_off},
             "dates": {"from": xmas_from, "to": last}, "do": [{"type": "off", "entities": windows}]},
        ]
    if "kitchen" in keys:
        up, low = lst("input_text.fh_kitchen_upper_lights", r"upper"), lst("input_text.fh_kitchen_lower_lights", r"lower")
        patio = lst("input_text.fh_kitchen_patio_lights", r"patio")
        motion = "binary_sensor.kitchen_motion" if "binary_sensor.kitchen_motion" in names else \
            next((e for e in names if e.startswith("binary_sensor.") and re.search(r"motion", e) and re.search(r"kitchen|motion_sensor", e)), "binary_sensor.kitchen_motion")
        quiet = num("input_number.fh_kitchen_quiet_minutes", 10)
        mb = num("input_number.fh_kitchen_motion_bright", 20)
        until = hm("input_datetime.fh_kitchen_motion_until", "08:00")
        low_from, up_from = hm("input_datetime.fh_kitchen_lower_motion_from", "20:00"), hm("input_datetime.fh_kitchen_upper_motion_from", "00:00")
        R += [
            {"name": "Kitchen evening lights", "when": {"type": "time", "at": hm("input_datetime.fh_kitchen_evening_on", "20:00")},
             "do": [{"type": "dim", "entities": up, "pct": num("input_number.fh_kitchen_evening_bright", 10), "white": "warm"},
                    {"type": "dim", "entities": patio, "pct": 100, "white": "cool"}]},
            {"name": "Patio off", "when": {"type": "time", "at": hm("input_datetime.fh_kitchen_patio_off", "21:45")},
             "do": [{"type": "off", "entities": patio}]},
            {"name": "Kitchen uppers off", "when": {"type": "time", "at": hm("input_datetime.fh_kitchen_uppers_off", "00:00")},
             "do": [{"type": "off", "entities": up}]},
            {"name": "Kitchen lights off in the morning", "when": {"type": "time", "at": hm("input_datetime.fh_kitchen_morning_off", "08:10")},
             "do": [{"type": "off", "entities": list(dict.fromkeys(up + low))}]},
            {"name": "Kitchen night-light (lowers) on motion", "when": {"type": "device", "entity": motion, "to": "on"},
             "between": {"after": low_from, "before": until}, "ifoff": True,
             "do": [{"type": "dim", "entities": low, "pct": mb, "white": "warm"}]},
            {"name": "Kitchen night-light (lowers) off when quiet", "when": {"type": "device", "entity": motion, "to": "off", "for": quiet},
             "between": {"after": low_from, "before": until}, "do": [{"type": "off", "entities": low}]},
            {"name": "Kitchen night-light (uppers) on motion", "when": {"type": "device", "entity": motion, "to": "on"},
             "between": {"after": up_from, "before": until}, "ifoff": True,
             "do": [{"type": "dim", "entities": up, "pct": mb, "white": "warm"}]},
            {"name": "Kitchen night-light (uppers) off when quiet", "when": {"type": "device", "entity": motion, "to": "off", "for": quiet},
             "between": {"after": up_from, "before": until}, "do": [{"type": "off", "entities": up}]},
        ]
    made, skipped = [], []
    for i, spec in enumerate(R):
        spec.setdefault("days", every)
        spec["do"] = [a for a in spec["do"] if a.get("entities")]
        if not spec["do"]:
            skipped.append(spec["name"])
            continue
        rid = f"fhu_{int(time.time() * 1000):x}{i:02d}"
        r = save_routine(spec, rid)
        (made if r.get("ok") else skipped).append(spec["name"] if r.get("ok") else f"{spec['name']} ({r.get('reason')})")
        if not r.get("ok") and "admin" in str(r.get("reason", "")):
            return {"ok": False, "reason": r["reason"], "made": made}
    # packaged versions off (they'd double up) and their cards hidden
    pats = [g["auto"] for g in GROUPS if g["key"] in keys]
    for s in states:
        yid = str((s.get("attributes") or {}).get("id") or "")
        if s["entity_id"].startswith("automation.") and any(re.search(p, yid) for p in pats) and not yid.endswith("_defaults"):
            set_automation(s["entity_id"], False)
    from ..db import get_db
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('routines_converted', ?)",
                     (json.dumps(sorted(set(_converted()) | set(keys))),))
    return {"ok": True, "made": made, "skipped": skipped}


def get_routine(rid: str) -> dict:
    if not rid.startswith("fhu_"):
        return {"ok": False, "reason": "not a FamilyHub routine"}
    if ha_svc.demo_mode():
        spec = _MINE.get(rid)
        return {"ok": bool(spec), "id": rid, "spec": spec}
    try:
        cfg = ha_svc._request(f"/api/config/automation/config/{rid}") or {}
    except Exception:
        return {"ok": False, "reason": "couldn't read it from Home Assistant"}
    desc = cfg.get("description") or ""
    try:
        spec = json.loads(desc[len(_TAG):]) if desc.startswith(_TAG) else None
    except ValueError:
        spec = None
    return {"ok": bool(spec), "id": rid, "spec": spec, "reason": None if spec else "this one was changed in Home Assistant; edit it there"}


def save_routine(spec: dict, rid: str | None = None) -> dict:
    if not isinstance(spec, dict) or not isinstance(spec.get("when") or {}, dict) or not isinstance(spec.get("do") or [], list) \
            or not all(isinstance(a, dict) for a in spec.get("do") or []):
        return {"ok": False, "reason": "That routine didn't come through right. Try again."}
    try:
        cfg = build(spec)
    except (ValueError, TypeError, AttributeError) as e:
        return {"ok": False, "reason": str(e) if isinstance(e, ValueError) and "invalid literal" not in str(e) else "Check the numbers in the routine"}
    rid = rid if (rid and re.fullmatch(r"fhu_[a-z0-9]+", rid)) else f"fhu_{int(time.time() * 1000):x}"
    if ha_svc.demo_mode():
        _MINE[rid] = spec
        _DEMO[f"automation.{rid}"] = {"state": "on", "attributes": {"id": rid, "friendly_name": cfg["alias"], "last_triggered": None}}
        return {"ok": True, "id": rid, "demo": True}
    try:
        ha_svc._request(f"/api/config/automation/config/{rid}", method="POST", payload=cfg, timeout=15)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("message")
        except Exception:
            msg = None
        return {"ok": False, "reason": msg or f"Home Assistant said no (error {e.code}). The FamilyHub token needs an admin user."}
    except Exception:
        return {"ok": False, "reason": "couldn't reach Home Assistant"}
    return {"ok": True, "id": rid}


def delete_routine(rid: str) -> dict:
    if not re.fullmatch(r"fhu_[a-z0-9]+", rid or ""):
        return {"ok": False, "reason": "only routines made in FamilyHub can be deleted here"}
    if ha_svc.demo_mode():
        _MINE.pop(rid, None)
        _DEMO.pop(f"automation.{rid}", None)
        return {"ok": True, "demo": True}
    try:
        ha_svc._request(f"/api/config/automation/config/{rid}", method="DELETE", timeout=15)
    except Exception:
        return {"ok": False, "reason": "couldn't delete it in Home Assistant"}
    return {"ok": True}


# ---- demo data so the page can be seen without Home Assistant -------------------------------------
def _demo_seed() -> dict:
    d = {}
    def auto(yid, name, on=True, last="2026-11-11T06:00:00+00:00"):
        d[f"automation.{yid}"] = {"state": "on" if on else "off", "attributes": {"id": yid, "friendly_name": name, "last_triggered": last}}
    for yid, name in [("fh_peak_precondition", "Peak: pre-heat / pre-cool an hour before"), ("fh_peak_start", "Peak: HVAC off"),
                      ("fh_peak_end", "Peak: HVAC back on"), ("fh_peak_safety", "Peak: safety limit reached"), ("fh_peak_defaults", "Peak: defaults")]:
        auto(yid, name)
    for yid, name in [("fh_outdoor_sunset", "Outdoor: sunset"), ("fh_outdoor_1150", "Outdoor: holiday lights off, nightly lights on"),
                      ("fh_outdoor_sunrise", "Outdoor: everything off at sunrise"), ("fh_christmas_upstairs_on", "Christmas: window lights on at sunset"),
                      ("fh_christmas_upstairs_off", "Christmas: window lights off")]:
        auto(yid, name)
    auto("fh_kitchen_evening", "Kitchen: uppers + patio on in the evening")
    def helper(eid, name, state, **a):
        d[eid] = {"state": state, "attributes": {"friendly_name": name, **a}}
    helper("input_datetime.peak_winter_start", "Peak winter start", "06:00:00")
    helper("input_datetime.peak_winter_end", "Peak winter end", "09:00:00")
    helper("input_datetime.peak_summer_start", "Peak summer start", "15:00:00")
    helper("input_datetime.peak_summer_end", "Peak summer end", "18:00:00")
    helper("input_number.peak_preheat", "Pre-heat before winter peak", "70", min=60, max=76, step=1, unit_of_measurement="°F")
    helper("input_number.peak_precool", "Pre-cool before summer peak", "68", min=64, max=78, step=1, unit_of_measurement="°F")
    helper("input_number.peak_safe_low", "Peak safety floor", "50", min=40, max=60, step=1, unit_of_measurement="°F")
    helper("input_number.peak_safe_high", "Peak safety ceiling", "88", min=80, max=95, step=1, unit_of_measurement="°F")
    helper("input_boolean.peak_enabled", "Peak hours - HVAC off", "on")
    helper("input_boolean.peak_ready", "Peak starting values filled in (automatic)", "on")
    helper("input_boolean.sched_enabled", "FamilyHub runs the daily schedule", "on")
    helper("input_datetime.sched_day_start", "Day starts at", "09:00:00")
    helper("input_datetime.sched_night_start", "Night starts at", "18:00:00")
    for k, v in (("day_heat", "60"), ("day_cool", "70"), ("night_heat", "67"), ("night_cool", "70")):
        helper(f"input_number.sched_{k}", k.replace("_", " ").title(), v, min=50, max=90, step=1, unit_of_measurement="°F")
    auto("fh_sched_apply", "Schedule: day / night temperatures")
    for e, n, v in (("fh_kitchen_upper_lights", "Kitchen upper lights", "light.kitchen"), ("fh_kitchen_lower_lights", "Kitchen lower lights", ""),
                    ("fh_kitchen_patio_lights", "Back patio lights", "")):
        helper(f"input_text.{e}", n, v)
    for e, n, v in (("evening_on", "Uppers + patio on at", "20:00:00"), ("patio_off", "Patio off at", "21:45:00"), ("uppers_off", "Uppers off at", "00:00:00"),
                    ("morning_off", "Everything off in the morning at", "08:10:00"), ("upper_motion_from", "Uppers come on with motion from", "00:00:00"),
                    ("lower_motion_from", "Lowers come on with motion from", "20:00:00"), ("motion_until", "Motion night-light until", "08:00:00")):
        helper(f"input_datetime.fh_kitchen_{e}", n, v)
    helper("input_number.fh_kitchen_evening_bright", "Evening uppers brightness", "10", min=1, max=100, step=1, unit_of_measurement="%")
    helper("input_number.fh_kitchen_motion_bright", "Night-light brightness", "20", min=1, max=100, step=1, unit_of_measurement="%")
    helper("input_number.fh_kitchen_quiet_minutes", "Off after this many quiet minutes", "10", min=1, max=60, step=1, unit_of_measurement="min")
    helper("input_text.fh_outdoor_night_lights", "Nightly lights", "light.porch,light.driveway")
    helper("input_text.fh_outdoor_holiday_lights", "Holiday lights", "")
    helper("input_text.fh_outdoor_window_lights", "Christmas window lights", "")
    helper("input_datetime.fh_outdoor_switchover", "Holiday lights off / nightly lights on at", "23:50:00")
    helper("input_datetime.fh_outdoor_windows_off", "Christmas window lights off at", "22:30:00")
    helper("input_datetime.fh_outdoor_xmas_start", "Christmas lights start on", "1970-01-01", has_date=True, has_time=False)
    helper("input_boolean.fh_outdoor_halloween", "Halloween lights in October", "on")
    helper("input_boolean.fh_outdoor_christmas", "Christmas lights (Thanksgiving to January)", "on")
    helper("input_number.fh_outdoor_xmas_last_day", "Christmas lights last day in January", "6", min=1, max=31, step=1)
    helper("input_boolean.holiday_lights_force", "Holiday lights tonight (outside the season)", "off")
    helper("binary_sensor.santee_cooper_peak_now", "Santee Cooper peak now", "off")
    helper("binary_sensor.peak_summer_season", "Peak summer season", "off")
    helper("binary_sensor.christmas_season", "Christmas season", "off")
    helper("binary_sensor.halloween_season", "Halloween season", "off")
    return d


_DEMO = _demo_seed()
