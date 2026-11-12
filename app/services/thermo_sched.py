"""
Thermostat schedule with as many time slots as you like, per thermostat.

  slot = {at:"HH:MM", days:[mon..sun], targets:[climate.*], heat:60, cool:70}

FamilyHub turns the list into two things inside Home Assistant (config API, like "Your routines"), so the
schedule keeps running even when the wall is off:

  script.fhs_thermostat_now        for each thermostat, finds the slot that should be in effect right now
                                   (the latest start time, looking back over the week) and sets it:
                                   auto/heat_cool -> heat..cool range, heat -> heat, cool -> cool, off -> nothing
  automation fhs_thermostat_slots  fires at every slot's start time (outside Santee Cooper peak) and runs it

peak_thermostat.yaml's own script (fh_thermostat_schedule) hands over to script.fhs_thermostat_now when it
exists, so "back on after peak" lands on the right slot. The slot list itself lives in the automation's
description, the same way routines keep their spec.
"""
from __future__ import annotations

import json
import re

from . import ha_svc

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
SCRIPT_ID, AUTO_ID = "fhs_thermostat_now", "fhs_thermostat_slots"
_TAG = "FamilyHub thermostat schedule — edit it in FamilyHub. "
_DEMO: dict = {"slots": None}


def _stats() -> list:
    try:
        return [t for g in ha_svc.get_home().get("groups", []) for t in g.get("tiles", []) if t["domain"] == "climate"]
    except Exception:
        return []


def _from_helpers() -> list:
    """First time: start from the old Day / Night settings (or 9 AM 60/70, 6 PM 67/70)."""
    def st(e, d):
        v = ha_svc._current_state(e) if not ha_svc.demo_mode() else ""
        return v if v not in ("", "unknown", "unavailable") else d
    ids = [t["entity_id"] for t in _stats()] or ["climate.upstairs_thermostat", "climate.downstairs_thermostat"]
    num = lambda e, d: int(float(st(e, d)))
    return [
        {"at": st("input_datetime.sched_day_start", "09:00")[:5], "days": DAYS, "targets": ids,
         "heat": num("input_number.sched_day_heat", 60), "cool": num("input_number.sched_day_cool", 70)},
        {"at": st("input_datetime.sched_night_start", "18:00")[:5], "days": DAYS, "targets": ids,
         "heat": num("input_number.sched_night_heat", 67), "cool": num("input_number.sched_night_cool", 70)},
    ]


def get() -> dict:
    stats = [{"id": t["entity_id"], "name": re.sub(r"\s*thermostat\s*", "", t["name"], flags=re.I).strip() or t["name"]} for t in _stats()]
    if ha_svc.demo_mode():
        return {"ok": True, "slots": _DEMO["slots"] or _from_helpers(), "saved": _DEMO["slots"] is not None, "thermostats": stats}
    try:
        cfg = ha_svc._request(f"/api/config/automation/config/{AUTO_ID}") or {}
        desc = cfg.get("description") or ""
        slots = json.loads(desc[len(_TAG):]) if desc.startswith(_TAG) else None
    except Exception:
        slots = None
    return {"ok": True, "slots": slots or _from_helpers(), "saved": slots is not None, "thermostats": stats,
            "package_ready": "v2" in str(_friendly("script.fh_thermostat_schedule"))}


def _friendly(eid):
    try:
        return ((ha_svc._request(f"/api/states/{eid}") or {}).get("attributes") or {}).get("friendly_name", "")
    except Exception:
        return ""


def _clean(slots) -> list:
    out = []
    if not isinstance(slots, list) or not slots:
        raise ValueError("Add at least one time")
    for s in slots[:24]:
        if not isinstance(s, dict):
            raise ValueError("That schedule didn't come through right. Try again.")
        at = str(s.get("at") or "")
        if not re.fullmatch(r"\d{1,2}:\d{2}", at) or int(at.split(":")[0]) > 23 or int(at.split(":")[1]) > 59:
            raise ValueError("Each time needs a start time")
        days = [d for d in DAYS if d in (s.get("days") or [])]
        if not days:
            raise ValueError("Each time needs at least one day")
        targets = [t for t in (s.get("targets") or []) if re.fullmatch(r"climate\.[a-z0-9_]+", str(t))]
        if not targets:
            raise ValueError("Pick upstairs, downstairs or both")
        try:
            heat, cool = int(float(s.get("heat"))), int(float(s.get("cool")))
        except (TypeError, ValueError, OverflowError):
            raise ValueError("Heat and cool need numbers")
        if not (45 <= heat <= 85 and 55 <= cool <= 95):
            raise ValueError("Heat 45-85°, cool 55-95°")
        if cool - heat < 2:
            raise ValueError("Cool has to be at least 2° above heat (thermostats need the gap on Auto)")
        out.append({"at": at.zfill(5), "days": days, "targets": list(dict.fromkeys(targets)), "heat": heat, "cool": cool})
    out.sort(key=lambda s: s["at"])
    return out


def _configs(slots: list):
    periods = [{"d": [DAYS.index(d) for d in s["days"]], "m": int(s["at"][:2]) * 60 + int(s["at"][3:]), "t": s["targets"],
                "h": s["heat"], "c": s["cool"]} for s in slots]
    ids = sorted({t for s in slots for t in s["targets"]})
    pick = ("{% set ns = namespace(best=none, dist=99999) %}"
            "{% set nowm = now().weekday() * 1440 + now().hour * 60 + now().minute %}"
            "{% for p in periods if repeat.item in p.t %}{% for d in p.d %}"
            "{% set dist = (nowm - (d * 1440 + p.m)) % 10080 %}"
            "{% if dist < ns.dist %}{% set ns.dist = dist %}{% set ns.best = p %}{% endif %}"
            "{% endfor %}{% endfor %}{{ ns.best }}")
    script = {
        "alias": "Thermostats - FamilyHub schedule (now)", "mode": "queued",
        "description": "Sets each thermostat to the FamilyHub schedule slot in effect right now. Edit the schedule in FamilyHub.",
        "fields": {"entities": {"description": "thermostats (default: all in the schedule)"}},
        "sequence": [
            {"variables": {"periods": periods,
                           "ids": "{{ entities if entities is defined and entities else " + json.dumps(ids) + " }}"}},
            {"repeat": {"for_each": "{{ ids if ids is list else [ids] }}", "sequence": [
                {"variables": {"p": pick, "mode": "{{ states(repeat.item) }}"}},
                {"if": [{"condition": "template", "value_template": "{{ p is mapping }}"}], "then": [{"choose": [
                    {"conditions": [{"condition": "template", "value_template": "{{ mode in ['heat_cool', 'auto'] }}"}],
                     "sequence": [{"action": "climate.set_temperature", "target": {"entity_id": "{{ repeat.item }}"},
                                   "data": {"target_temp_low": "{{ p.h }}", "target_temp_high": "{{ p.c }}"}}]},
                    {"conditions": [{"condition": "template", "value_template": "{{ mode == 'heat' }}"}],
                     "sequence": [{"action": "climate.set_temperature", "target": {"entity_id": "{{ repeat.item }}"},
                                   "data": {"temperature": "{{ p.h }}"}}]},
                    {"conditions": [{"condition": "template", "value_template": "{{ mode == 'cool' }}"}],
                     "sequence": [{"action": "climate.set_temperature", "target": {"entity_id": "{{ repeat.item }}"},
                                   "data": {"temperature": "{{ p.c }}"}}]},
                ]}]},
            ]}},
        ],
    }
    auto = {
        "alias": "Thermostats - FamilyHub schedule", "mode": "queued",
        "description": _TAG + json.dumps(slots, separators=(",", ":")),
        "triggers": [{"trigger": "time", "at": t + ":00"} for t in sorted({s["at"] for s in slots})],
        "conditions": [{"condition": "template", "value_template":
                        "{{ not is_state('input_boolean.peak_active', 'on') and not is_state('input_boolean.sched_enabled', 'off') }}"}],
        "actions": [{"action": f"script.{SCRIPT_ID}"}],
    }
    return script, auto


def save(slots) -> dict:
    try:
        slots = _clean(slots)
    except ValueError as e:
        return {"ok": False, "reason": str(e)}
    if ha_svc.demo_mode():
        _DEMO["slots"] = slots
        return {"ok": True, "demo": True, "slots": slots}
    script, auto = _configs(slots)
    try:
        ha_svc._request(f"/api/config/script/config/{SCRIPT_ID}", method="POST", payload=script, timeout=15)
        ha_svc._request(f"/api/config/automation/config/{AUTO_ID}", method="POST", payload=auto, timeout=15)
    except Exception as e:
        code = getattr(e, "code", None)
        return {"ok": False, "reason": f"Home Assistant said no (error {code}). FamilyHub's token needs an admin user." if code
                else "couldn't reach Home Assistant"}
    # the old Day / Night automation would fight this one: switch it off
    ha_svc.call_service("input_boolean", "turn_on", "input_boolean.sched_enabled")   # peak end follows the schedule
    from .automations import _states
    for st in _states():
        if (st.get("attributes") or {}).get("id") == "fh_sched_apply":
            ha_svc.call_service("automation", "turn_off", st["entity_id"])
    apply_now()
    return {"ok": True, "slots": slots}


def apply_now():
    """Put the slot for right now in place (not during peak)."""
    if ha_svc.demo_mode() or ha_svc._current_state("input_boolean.peak_active") == "on":
        return
    import threading
    import time

    def go():
        time.sleep(3)                         # let HA load the new script
        ha_svc.call_service("script", "turn_on", f"script.{SCRIPT_ID}")
    threading.Thread(target=go, daemon=True).start()
