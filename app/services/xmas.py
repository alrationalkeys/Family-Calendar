"""
Outside Christmas display (the smart plug the C9 strings, sleigh and nutcrackers hang off). In season only
(Nov 10 - Jan 15) and only once a plug is known (settings.xmasPlug, else a switch named christmas/xmas/holiday/c9/
outdoor decor — never the village).

  walk-up     after dark, the display is off (schedule ended), motion on a front/porch/driveway/yard sensor or
              camera -> lights on for settings.xmasMotionMin (5) min; more motion keeps them on. Only turns off
              what it turned on. Until settings.xmasMotionUntil ("01:00").
  doorbell    a ring after dark -> the display blinks twice, then goes back to how it was.
  wind        gusts >= settings.windGust (30 mph) in the next 12 h -> one push a day to stake the nutcrackers.
  offline     the plug unavailable for 3+ min (outdoor GFCI tripped, usually rain) -> one push; another when it's back.

Settings: xmasMotion, xmasFlash, xmasWind, xmasOffline (bools), xmasMotionMin, xmasMotionUntil, windGust, xmasPlug.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
from datetime import date, datetime

_NAME = re.compile(r"christmas|xmas|holiday|c9|outdoor decor|outside decor|yard decor", re.I)
_MOTION_AT = re.compile(r"front|porch|door|driveway|yard|walk|entry|garage|outside|outdoor", re.I)
_RING = re.compile(r"doorbell|door_bell|door bell|(?<![a-z])(ring|chime)(?![a-z])", re.I)
_S: dict = {"ours_until": 0.0, "ours_at": 0.0, "offline_since": 0.0, "offline_told": False,
            "wind_day": None, "wind_checked": 0.0, "flash_at": 0.0}


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def in_season(d: date | None = None) -> bool:
    d = d or date.today()
    return (d.month == 11 and d.day >= 10) or d.month == 12 or (d.month == 1 and d.day <= 15)


def _states() -> dict:
    try:
        from . import ha_live
        s = ha_live.states()
        if s is None:
            from . import ha_svc
            s = ha_svc._request("/api/states") or []
        return {x["entity_id"]: x for x in s}
    except Exception:
        return {}


def plug(states: dict | None = None) -> str | None:
    s = _settings()
    if s.get("xmasPlug"):
        return s["xmasPlug"]
    states = states if states is not None else _states()
    for eid, st in states.items():
        name = str((st.get("attributes") or {}).get("friendly_name", ""))
        if eid.split(".")[0] == "switch" and _NAME.search(eid + " " + name) and not re.search(r"village", eid + " " + name, re.I) \
                and not eid.startswith("switch.fh"):
            return eid
    return None


def _dark(states: dict) -> bool:
    sun = states.get("sun.sun")
    if sun:
        return sun.get("state") == "below_horizon"
    h = datetime.now().hour
    return h >= 17 or h < 7


def _late_ok(s: dict) -> bool:
    """Between dark and settings.xmasMotionUntil (01:00): not every 3 AM cat."""
    until = str(s.get("xmasMotionUntil") or "01:00")
    now = datetime.now().strftime("%H:%M")
    return now >= "12:00" or now < until


def _set(eid: str, on: bool):
    from . import ha_svc
    ha_svc.call_service(eid.split(".")[0], "turn_on" if on else "turn_off", eid)


def _push(text: str, tag: str):
    try:
        from .watch import _push as push
        push(text, tag)
    except Exception:
        pass


def on_state(eid: str, old: dict | None, new: dict | None, states: dict):
    """From ha_live: motion -> walk-up lights, doorbell -> blink. Never raises."""
    try:
        if not new or not in_season():
            return
        dom = eid.split(".")[0]
        a = new.get("attributes") or {}
        name = str(a.get("friendly_name", ""))
        ns, os_ = str(new.get("state")), str((old or {}).get("state"))
        if dom not in ("binary_sensor", "event") or ns == os_:
            return
        p = plug(states)
        if not p or p not in states:
            return
        s = _settings()
        ring = _RING.search(eid + " " + name) and "motion" not in (eid + name).lower() and (dom == "event" or ns == "on")
        if ring:
            if s.get("xmasFlash", True) is not False and _dark(states) and time.time() - _S["flash_at"] > 20:
                _S["flash_at"] = time.time()
                threading.Thread(target=_flash, args=(p, states[p].get("state") == "on"), daemon=True).start()
            return
        txt = eid + " " + name
        moving = a.get("device_class") in ("motion", "occupancy") or re.search(r"(person|people|vehicle|motion)[ _]detected", txt, re.I)
        if re.search(r"animal|pet|package", txt, re.I):       # Alarm.com camera AI: cats and parcels don't count
            moving = False
        if moving and ns == "on" and _MOTION_AT.search(txt) \
                and not re.search(r"kitchen|living|bed|bath|stair|hall|office|loft|laundry|dining|pantry|closet", eid + " " + name, re.I):
            if s.get("xmasMotion", True) is False or not _dark(states) or not _late_ok(s):
                return
            mins = max(1, min(30, int(s.get("xmasMotionMin") or 5)))
            cur = states[p].get("state")
            if cur == "off":
                _set(p, True)
                _S["ours_at"] = time.time()
                _S["ours_until"] = time.time() + mins * 60
            elif cur == "on" and _S["ours_until"]:
                _S["ours_until"] = time.time() + mins * 60      # still people out there: keep it on
    except Exception:
        pass


def _flash(p: str, was_on: bool):
    try:
        for _ in range(2):
            _set(p, not was_on)
            time.sleep(0.9)
            _set(p, was_on)
            time.sleep(0.9)
    except Exception:
        pass


def tick():
    """Every minute from the house-watch loop."""
    if not in_season():
        _S["ours_until"] = 0
        return
    s, states = _settings(), _states()
    p = plug(states)
    if not p:
        return
    st = (states.get(p) or {}).get("state")
    now = time.time()
    # walk-up lights: switch back off when the time's up (only if we were the ones who turned it on)
    if _S["ours_until"]:
        if st != "on":
            _S["ours_until"] = 0                               # someone turned it off already
        elif now >= _S["ours_until"]:
            _S["ours_until"] = 0
            try:
                _set(p, False)
            except Exception:
                pass
    # offline = GFCI tripped / unplugged
    if s.get("xmasOffline", True) is not False:
        if st in ("unavailable", None):
            _S["offline_since"] = _S["offline_since"] or now
            if not _S["offline_told"] and now - _S["offline_since"] >= 180:
                _S["offline_told"] = True
                _push("🎄 The outside Christmas lights plug went offline. Usually that's the outdoor GFCI outlet "
                      "tripping (rain or wet connections): press Reset on the outlet once things dry out.", "familyhub-xmas")
        else:
            if _S["offline_told"]:
                _push("🎄 The outside Christmas lights plug is back online.", "familyhub-xmas")
            _S["offline_since"], _S["offline_told"] = 0.0, False
    # wind: check hourly, push once a day
    if s.get("xmasWind", True) is not False and now - _S["wind_checked"] > 3600 and _S["wind_day"] != date.today():
        _S["wind_checked"] = now
        try:
            w = gusts()
        except Exception:
            w = None
        lim = float(s.get("windGust") or 30)
        if w and w["mph"] >= lim:
            _S["wind_day"] = date.today()
            _push(f"💨 Gusts up to {w['mph']:.0f} mph around {w['at']}. Stake or lay down the nutcrackers and check the sleigh "
                  "and reindeer.", "familyhub-wind")


def gusts(hours: int = 12) -> dict | None:
    """Strongest forecast gust in the next `hours` -> {'mph', 'at'}."""
    from . import weather_svc
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={weather_svc.DEFAULT_LAT}&longitude={weather_svc.DEFAULT_LON}"
           f"&hourly=wind_gusts_10m&wind_speed_unit=mph&forecast_hours={hours}&timezone=auto")
    with urllib.request.urlopen(url, timeout=6) as r:
        j = json.loads(r.read())
    h = j.get("hourly") or {}
    best = None
    for t, g in zip(h.get("time", []), h.get("wind_gusts_10m") or []):
        if g is not None and (best is None or g > best[1]):
            best = (t, g)
    if not best:
        return None
    hr = int(best[0][11:13])
    return {"mph": best[1], "at": f"{(hr % 12) or 12} {'AM' if hr < 12 else 'PM'}"}


def status() -> dict:
    states = _states()
    p = plug(states)
    return {"season": in_season(), "plug": p, "name": ((states.get(p) or {}).get("attributes") or {}).get("friendly_name") if p else None,
            "state": (states.get(p) or {}).get("state") if p else None, "walkup_on": bool(_S["ours_until"]),
            "offline_since": _S["offline_since"] or None}
