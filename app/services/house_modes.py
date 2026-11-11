"""
House modes — the one-tap sequences a family actually uses, built from whatever
Home Assistant exposes (now: Alarm.com panel + locks + garage, Deako lights,
Rokus, thermostat). No HA automations to write; FamilyHub figures out the
device list live.

  goodnight  like the panel's Sleep scene: lock every lock, arm Stay, close the garage, darken the wall.
             Lights and TVs are left alone (holiday plugs run on their own schedule) unless
             settings.goodnightLightsOff is on. Optional thermostat setback (settings.nightTemp).
  away       everything in goodnight but arm AWAY, outdoor lights off too,
             thermostat eco (settings.awayTemp)
  welcome    like the Surety Home scene: disarm (only with the panel code typed on the keypad — passed
             to HA, never stored), then open the garage (button only, settings.openGarageOnHome; never
             while the alarm is still armed), after dark porch/driveway/entry + kitchen lights on,
             thermostat back to settings.homeTemp (skipped during Santee Cooper peak); say hello.
             Voice "I'm home" does lights + thermostat only.

Each run returns {done:[...], warnings:[...], say:"..."} and queues the sentence
as an announcement so the wall speaks it even when a phone triggered it.
HA's person.* entities (the companion app) give presence() for the who's-home strip.
"""
from __future__ import annotations

import re
from datetime import datetime

from . import ha_svc

_OUTDOOR = re.compile(r"porch|exterior|outside|outdoor|driveway|landscape|yard|patio|flood|garage light", re.I)
_ENTRY = re.compile(r"porch|driveway|entry|foyer|front|kitchen|hall", re.I)


def _tiles():
    try:
        h = ha_svc.get_home()
        return [t for g in (h.get("groups") or []) for t in (g.get("tiles") or [])]
    except Exception:
        return []


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def _after_dark() -> bool:
    try:
        from . import weather_svc
        wx = weather_svc.get_weather()
        now = datetime.now()
        sr, ss = wx.get("sunrise"), wx.get("sunset")
        if sr and ss:
            return not (datetime.fromisoformat(sr) <= now <= datetime.fromisoformat(ss))
    except Exception:
        pass
    h = datetime.now().hour
    return h >= 18 or h < 7


def _announce(sentence: str):
    try:
        from ..db import get_db
        with get_db() as conn:
            conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                         ("🏠 House", sentence, "announce", datetime.now().isoformat()))
    except Exception:
        pass


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def run(mode: str, who: str | None = None, close_garage: bool | None = None, arm: bool = True, source: str = "wall",
        code: str | None = None, open_garage: bool = False) -> dict:
    mode = (mode or "").lower()
    tiles = _tiles()
    s = _settings()
    if close_garage is None:                       # match the Alarm.com Sleep/Away scenes: close it (setting can turn this off)
        close_garage = s.get("closeGarageOnModes", True) is not False
    done, warnings, notes = [], [], []
    by = lambda dom: [t for t in tiles if t["domain"] == dom]

    if mode in ("goodnight", "away"):
        lights_too = mode == "away" or s.get("goodnightLightsOff", False) is True
        # lights + fans + switches that are lights
        lights = [t for t in by("light") if t["on"]] + [t for t in by("fan") if t["on"]] if lights_too else []
        lights += [t for t in by("switch") if t["on"] and re.search(r"light|lamp|led|strip", t["name"], re.I)] if lights_too else []
        if mode == "goodnight":
            # outdoor lights stay on for the night schedule, except floodlights (the Sleep scene turns BackyardFL off)
            lights = [t for t in lights if not _OUTDOOR.search(t["name"] + " " + str(t.get("area") or "")) or re.search(r"flood|\bfl\b|fl$", t["name"], re.I)]
        for t in lights:
            ha_svc.call_service(t["domain"], "turn_off", t["entity_id"])
        if lights:
            done.append(f"turned off {_plural(len(lights), 'light')}")
        # TVs / players
        tvs = [t for t in by("media_player") if t["state"] not in ("off", "unavailable", "standby") and not re.search(r"spotify|familyhub", t["entity_id"] + t["name"], re.I)] if lights_too else []
        for t in tvs:
            ha_svc.call_service("media_player", "turn_off", t["entity_id"])
        if tvs:
            done.append(f"turned off {_plural(len(tvs), 'TV')}")
        # locks
        unlocked = [t for t in by("lock") if t["state"] != "locked"]
        for t in unlocked:
            ha_svc.call_service("lock", "lock", t["entity_id"])
        if unlocked:
            done.append(f"locked the {', '.join(t['name'] for t in unlocked)}")
        elif by("lock"):
            notes.append("The doors are locked.")
        # garage
        for t in by("cover"):
            if t["state"] in ("open", "opening"):
                if close_garage:
                    ha_svc.call_service("cover", "close_cover", t["entity_id"])
                    done.append(f"closed the {t['name']}")
                else:
                    warnings.append("the garage door is still open" if re.search(r"garage", t["name"], re.I) else f"the {t['name']} is still open")
        # open doors/windows the sensors see
        gcover = ha_svc.has_garage_cover(by("cover"))
        for t in by("binary_sensor"):
            if t.get("device_class") in ("door", "window", "garage_door", "opening") and t["on"]:
                lbl = ha_svc.opening_label(t, gcover)          # the house->garage door is reported, the cover's own twin isn't
                if lbl:
                    warnings.append(f"the {lbl.lower()} is open" if lbl == "Door to garage" else f"{lbl} is open")
        # alarm
        if arm:
            for t in by("alarm_control_panel"):
                if warnings and mode == "away":
                    warnings.append("I didn't arm the alarm")
                    break
                # Stay for both, like the Surety Sleep and Away scenes (dogs set off motion sensors). settings.awayArm="away" opts in.
                svc = "alarm_arm_away" if (mode == "away" and s.get("awayArm") == "away") else "alarm_arm_home"
                r = ha_svc.call_service("alarm_control_panel", svc, t["entity_id"])
                done.append("armed the alarm" + (" for the night" if mode == "goodnight" else "") if r.get("ok") else "couldn't arm the alarm")
        # thermostat
        temp = s.get("nightTemp") if mode == "goodnight" else s.get("awayTemp")
        if temp:
            for t in by("climate"):
                ha_svc.call_service("climate", "set_temperature", t["entity_id"], {"temperature": float(temp)})
            if by("climate"):
                done.append(f"set the thermostat to {int(float(temp))}")
        lead = "Good night." if mode == "goodnight" else "Bye for now."
        if mode == "goodnight":
            try:
                from . import display_svc
                if display_svc._sleep_settings()[0]:
                    display_svc.enter_sleep("goodnight")       # wall goes dark now, even if the panel reports Stay
            except Exception:
                pass
    elif mode == "welcome":
        # 1) disarm with the code from the keypad
        still_armed = False
        for t in by("alarm_control_panel"):
            if not t["state"].startswith("armed") and t["state"] not in ("arming", "pending", "triggered"):
                continue
            if code:
                r = ha_svc.call_service("alarm_control_panel", "alarm_disarm", t["entity_id"], {"code": str(code)})
                if r.get("ok"):
                    done.append("disarmed the alarm")
                else:
                    still_armed = True
                    warnings.append("the alarm didn't disarm, check the code")
            else:
                still_armed = True
                warnings.append("the alarm is still armed, disarm it on the keypad")
        # 2) open the garage, only once the alarm is off (opening it while armed would set it off)
        if open_garage and s.get("openGarageOnHome", True) is not False:
            for t in by("cover"):
                if re.search(r"garage", t["name"] + " " + t["entity_id"], re.I) and t["state"] in ("closed", "closing"):
                    if still_armed:
                        warnings.append("I left the garage closed because the alarm is armed")
                        break
                    ha_svc.call_service("cover", "open_cover", t["entity_id"])
                    done.append(f"opened the {t['name']}")
        if _after_dark():
            entry = [t for t in by("light") if not t["on"] and _ENTRY.search(t["name"] + " " + str(t.get("area") or ""))]
            for t in entry:
                ha_svc.call_service("light", "turn_on", t["entity_id"])
            if entry:
                done.append(f"turned on {', '.join(t['name'] for t in entry)}")
        temp = s.get("homeTemp")
        if temp and by("climate"):
            peak = next((t for t in tiles if t["entity_id"] == "binary_sensor.santee_cooper_peak_now"), None)
            if peak and peak.get("on"):
                notes.append("It's peak hours, so I left the heat and air off until peak ends.")
            else:
                for t in by("climate"):
                    ha_svc.call_service("climate", "set_temperature", t["entity_id"], {"temperature": float(temp)})
                done.append(f"set the thermostat to {int(float(temp))}")
        lead = f"Welcome home{', ' + who if who else ''}."
    else:
        return {"ok": False, "reason": "mode must be goodnight | away | welcome"}

    def join_and(xs):
        return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
    say = lead
    if done:
        say += " I " + join_and(done) + "."
    say += (" " + " ".join(notes)) if notes else ""
    if warnings:
        say += " Heads up: " + join_and(warnings) + "."
    say = say.replace("..", ".")
    if source != "wall":
        _announce(say)
    try:
        from . import ha_live
        ha_live.bump()
    except Exception:
        pass
    return {"ok": True, "mode": mode, "done": done, "warnings": warnings, "say": say}


def presence() -> list:
    """Who's home, from HA's person.* entities (the companion app's location)."""
    if ha_svc.demo_mode():
        return [{"name": "Alex", "home": True, "since": None}, {"name": "Rachell", "home": False, "since": None}]
    try:
        from . import ha_live
        states = ha_live.states()
        if states is None:
            states = ha_svc._request("/api/states") or []
        out = []
        for st in states:
            eid = st.get("entity_id", "")
            if not eid.startswith("person."):
                continue
            if st.get("state") in ("unknown", "unavailable", None):
                continue                               # no phone linked / no fix yet: don't call them "away"
            a = st.get("attributes") or {}
            name = (a.get("friendly_name") or eid.split(".", 1)[1].replace("_", " ").title()).split()[0]   # first name
            out.append({"name": name, "home": st.get("state") == "home",
                        "state": st.get("state"), "since": st.get("last_changed")})
        return out
    except Exception:
        return []
