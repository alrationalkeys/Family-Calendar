"""Automations page: every Home Assistant routine in plain English, with on/off, last run, and the
times/temperatures that can be changed (HA helpers). Feeds the phone + wall "Automations" sections.

    list_all()             -> {connected, groups:[{key, title, blurb, status:[...], automations:[...], settings:[...]}]}
    set_automation(eid,on) -> automation.turn_on/off
    set_helper(eid,value)  -> input_number.set_value / input_datetime.set_datetime / input_boolean.turn_on|off

Only automation.*, input_number.*, input_datetime.* and input_boolean.* can be changed from here.
The FamilyHub packages (docs/ha/*.yaml) give every automation an id starting fh_; those are described
below. Anything else in Home Assistant shows under "Other automations" with its HA name.
"""
from __future__ import annotations

import re

from . import ha_svc

# yaml id -> plain-English description (what it does, when)
DESCRIBE = {
    # peak-thermostat.yaml
    "fh_peak_precondition": "An hour before peak, pre-heat to the pre-heat temp (winter) or pre-cool (summer).",
    "fh_peak_start": "When peak starts, turn both thermostats off.",
    "fh_peak_end": "When peak ends, turn them back on at the schedule's temperatures.",
    "fh_peak_safety": "Safety only: if a room hits the floor/ceiling during peak, that thermostat comes back on.",
    # outdoor-lights.yaml
    "fh_outdoor_sunset": "Sunset: holiday plug on in holiday season, otherwise porch, driveway and side lights on.",
    "fh_outdoor_1150": "Holiday season, 11:50 PM: holiday plug off, porch, driveway and side lights on.",
    "fh_outdoor_sunrise": "Sunrise: everything outside off.",
    "fh_christmas_upstairs_on": "Christmas season: upstairs window lights on at sunset.",
    "fh_christmas_upstairs_off": "Upstairs window lights off at 10:30 PM.",
    # kitchen-lights.yaml
    "fh_kitchen_evening": "8 PM: kitchen uppers on warm white 10%, back patio on.",
    "fh_patio_off": "9:45 PM: back patio off.",
    "fh_kitchen_uppers_midnight": "Midnight: kitchen uppers off.",
    "fh_kitchen_uppers_motion_on": "12–8 AM: motion turns the uppers on at 20%.",
    "fh_kitchen_uppers_motion_off": "12–8 AM: uppers off after 10 minutes with no motion.",
    "fh_kitchen_lowers_motion_on": "8 PM–8 AM: motion turns the lowers on at 20%.",
    "fh_kitchen_lowers_motion_off": "8 PM–8 AM: lowers off after 10 minutes with no motion.",
    "fh_kitchen_morning_off": "8:10 AM: all four kitchen lights off.",
    "fh_kitchen_button_single": "Kitchen button, single press: all kitchen lights on.",
    "fh_kitchen_button_double": "Kitchen button, double press: all kitchen lights off.",
}

GROUPS = [
    {"key": "peak", "title": "Peak hours (Santee Cooper)",
     "blurb": "Heat and AC are off during peak so nothing sets a demand charge. Winter 6–9 AM, summer 3–6 PM, every day.",
     "auto": r"^fh_peak_", "helpers": r"^(input_number|input_datetime|input_boolean)\.peak_",
     "status": ["binary_sensor.santee_cooper_peak_now", "binary_sensor.peak_summer_season"]},
    {"key": "outdoor", "title": "Outdoor & holiday lights",
     "blurb": "Porch, driveway and side lights every night; holiday lights switch on by date (October, and Thanksgiving to Jan 6).",
     "auto": r"^fh_(outdoor|christmas)_", "helpers": r"^input_boolean\.holiday_",
     "status": ["binary_sensor.halloween_season", "binary_sensor.christmas_season"]},
    {"key": "kitchen", "title": "Kitchen lights",
     "blurb": "Evening glow, night-light on motion, all off in the morning. Same as the old Alexa routines.",
     "auto": r"^fh_(kitchen|patio)_", "helpers": None, "status": []},
]

# helpers that are bookkeeping, not settings
_HIDDEN = re.compile(r"saved|\(automatic\)|_active$", re.I)
_WRITABLE = ("automation", "input_number", "input_datetime", "input_boolean")


def _states() -> list:
    if ha_svc.demo_mode():
        return [{"entity_id": e, "state": v["state"], "attributes": v.get("attributes", {})} for e, v in _DEMO.items()]
    try:
        from . import ha_live
        st = ha_live.states()
        if st is None or not any(x["entity_id"].startswith("automation.") for x in st):
            st = ha_svc._request("/api/states") or st or []       # mirror can be stale right after an HA restart
        return st
    except Exception:
        return []


def _setting(s: dict) -> dict:
    eid, a = s["entity_id"], s.get("attributes") or {}
    d = eid.split(".")[0]
    out = {"entity_id": eid, "name": a.get("friendly_name") or eid, "value": s.get("state")}
    if d == "input_number":
        out.update(kind="number", min=a.get("min"), max=a.get("max"), step=a.get("step"), unit=a.get("unit_of_measurement") or "")
    elif d == "input_datetime":
        out.update(kind="time", value=(s.get("state") or "")[:5])
    elif d == "input_boolean":
        out.update(kind="toggle")
    return out


def list_all() -> dict:
    states = _states()
    if not states and not ha_svc.demo_mode():
        return {"connected": False, "groups": []}
    by_id = {s["entity_id"]: s for s in states}
    autos = [s for s in states if s["entity_id"].startswith("automation.")]
    used = set()
    groups = []
    for g in GROUPS:
        items = []
        for s in autos:
            yid = str((s.get("attributes") or {}).get("id") or "")
            if re.search(g["auto"], yid):
                used.add(s["entity_id"])
                a = s.get("attributes") or {}
                items.append({"entity_id": s["entity_id"], "name": a.get("friendly_name") or s["entity_id"],
                              "on": s.get("state") == "on", "last": a.get("last_triggered"),
                              "about": DESCRIBE.get(yid, "")})
        settings = []
        if g["helpers"]:
            for s in states:
                if re.search(g["helpers"], s["entity_id"]) and not _HIDDEN.search(s["entity_id"] + " " + str((s.get("attributes") or {}).get("friendly_name", ""))):
                    settings.append(_setting(s))
        status = []
        for eid in g["status"]:
            s = by_id.get(eid)
            if s:
                status.append({"name": (s.get("attributes") or {}).get("friendly_name") or eid, "on": s.get("state") == "on"})
        groups.append({"key": g["key"], "title": g["title"], "blurb": g["blurb"], "installed": bool(items),
                       "status": status, "automations": items, "settings": settings})
    other = []
    for s in autos:
        if s["entity_id"] in used:
            continue
        a = s.get("attributes") or {}
        other.append({"entity_id": s["entity_id"], "name": a.get("friendly_name") or s["entity_id"],
                      "on": s.get("state") == "on", "last": a.get("last_triggered"), "about": ""})
    if other:
        groups.append({"key": "other", "title": "Other automations", "blurb": "Made in Home Assistant directly.",
                       "installed": True, "status": [], "automations": other, "settings": []})
    return {"connected": True, "demo": ha_svc.demo_mode(), "groups": groups, "ha_total": len(autos),
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
    d = entity_id.split(".")[0]
    if d not in _WRITABLE[1:]:
        return {"ok": False, "reason": "can't change that from here"}
    if ha_svc.demo_mode() and entity_id in _DEMO:
        _DEMO[entity_id]["state"] = ("on" if value in (True, "on", "true", 1) else "off") if d == "input_boolean" else (str(value)[:5] + ":00" if d == "input_datetime" else str(value))
        return {"ok": True, "demo": True}
    if d == "input_number":
        return ha_svc.call_service("input_number", "set_value", entity_id, {"value": float(value)})
    if d == "input_datetime":
        v = str(value)
        if not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", v):
            return {"ok": False, "reason": "time must be HH:MM"}
        return ha_svc.call_service("input_datetime", "set_datetime", entity_id, {"time": v if v.count(":") == 2 else v + ":00"})
    on = value in (True, "on", "true", 1)
    return ha_svc.call_service("input_boolean", "turn_on" if on else "turn_off", entity_id)


# ---- demo data so the page can be seen without Home Assistant -------------------------------------
def _demo_seed() -> dict:
    d = {}
    def auto(yid, name, on=True, last="2026-11-11T06:00:00+00:00"):
        d[f"automation.{yid}"] = {"state": "on" if on else "off", "attributes": {"id": yid, "friendly_name": name, "last_triggered": last}}
    for yid, name in [("fh_peak_precondition", "Peak: pre-heat / pre-cool an hour before"), ("fh_peak_start", "Peak: HVAC off"),
                      ("fh_peak_end", "Peak: HVAC back on"), ("fh_peak_safety", "Peak: safety limit reached")]:
        auto(yid, name)
    for yid, name in [("fh_outdoor_sunset", "Outdoor: sunset"), ("fh_outdoor_1150", "Outdoor: holiday off, regular on at 11:50 PM"),
                      ("fh_outdoor_sunrise", "Outdoor: everything off at sunrise"), ("fh_christmas_upstairs_on", "Christmas: upstairs lights on at sunset"),
                      ("fh_christmas_upstairs_off", "Christmas: upstairs lights off at 10:30 PM")]:
        auto(yid, name)
    auto("fh_kitchen_evening", "Kitchen: uppers + patio on at 8 PM")
    auto("fh_kitchen_lowers_motion_on", "Kitchen: lowers on with motion at night")
    def helper(eid, name, state, **a):
        d[eid] = {"state": state, "attributes": {"friendly_name": name, **a}}
    helper("input_datetime.peak_winter_start", "Peak winter start", "06:00:00")
    helper("input_datetime.peak_winter_end", "Peak winter end", "09:00:00")
    helper("input_datetime.peak_summer_start", "Peak summer start", "15:00:00")
    helper("input_datetime.peak_summer_end", "Peak summer end", "18:00:00")
    helper("input_number.peak_preheat", "Pre-heat before winter peak", "70", min=60, max=76, step=1, unit_of_measurement="°F")
    helper("input_number.peak_precool", "Pre-cool before summer peak", "68", min=64, max=78, step=1, unit_of_measurement="°F")
    helper("input_number.peak_safe_low", "Peak safety floor", "50", min=40, max=60, step=1, unit_of_measurement="°F")
    helper("input_boolean.peak_enabled", "Peak hours - HVAC off", "on")
    helper("input_number.peak_saved_up_heat", "Saved upstairs heat", "67")
    helper("input_boolean.holiday_lights_force", "Holiday lights tonight (outside the season)", "off")
    helper("binary_sensor.santee_cooper_peak_now", "Santee Cooper peak now", "off")
    helper("binary_sensor.peak_summer_season", "Peak summer season", "off")
    helper("binary_sensor.christmas_season", "Christmas season", "off")
    helper("binary_sensor.halloween_season", "Halloween season", "off")
    return d


_DEMO = _demo_seed()
