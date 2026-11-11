"""
House modes — the one-tap sequences a family actually uses, built from whatever
Home Assistant exposes (now: Alarm.com panel + locks + garage, Deako lights,
Rokus, thermostat). No HA automations to write; FamilyHub figures out the
device list live.

  goodnight  interior lights + fans off, TVs off, lock every lock, arm the alarm
             (night, falling back to stay), darken the wall, report a garage left open (close only if asked),
             optional thermostat setback (settings.nightTemp)
  away       everything in goodnight but arm AWAY, outdoor lights off too,
             thermostat eco (settings.awayTemp)
  welcome    after dark: porch/driveway/entry + kitchen lights on; say hello.
             (Never disarms — that stays behind the PIN pad.)

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


def run(mode: str, who: str | None = None, close_garage: bool = False, arm: bool = True, source: str = "wall") -> dict:
    mode = (mode or "").lower()
    tiles = _tiles()
    s = _settings()
    done, warnings, notes = [], [], []
    by = lambda dom: [t for t in tiles if t["domain"] == dom]

    if mode in ("goodnight", "away"):
        # lights + fans + switches that are lights
        lights = [t for t in by("light") if t["on"]] + [t for t in by("fan") if t["on"]]
        lights += [t for t in by("switch") if t["on"] and re.search(r"light|lamp|led|strip", t["name"], re.I)]
        if mode == "goodnight":
            lights = [t for t in lights if not _OUTDOOR.search(t["name"] + " " + str(t.get("area") or ""))]
        for t in lights:
            ha_svc.call_service(t["domain"], "turn_off", t["entity_id"])
        if lights:
            done.append(f"turned off {_plural(len(lights), 'light')}")
        # TVs / players
        tvs = [t for t in by("media_player") if t["state"] not in ("off", "unavailable", "standby") and not re.search(r"spotify|familyhub", t["entity_id"] + t["name"], re.I)]
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
                svc = "alarm_arm_night" if mode == "goodnight" else "alarm_arm_away"
                r = ha_svc.call_service("alarm_control_panel", svc, t["entity_id"])
                if mode == "goodnight" and not r.get("ok"):          # panel without a Night mode: fall back to Stay
                    r = ha_svc.call_service("alarm_control_panel", "alarm_arm_home", t["entity_id"])
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
        if _after_dark():
            entry = [t for t in by("light") if not t["on"] and _ENTRY.search(t["name"] + " " + str(t.get("area") or ""))]
            for t in entry:
                ha_svc.call_service("light", "turn_on", t["entity_id"])
            if entry:
                done.append(f"turned on {', '.join(t['name'] for t in entry)}")
        for t in by("alarm_control_panel"):
            if t["state"].startswith("armed"):
                warnings.append("the alarm is still armed, disarm it on the screen")
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
            a = st.get("attributes") or {}
            out.append({"name": a.get("friendly_name") or eid.split(".", 1)[1].title(), "home": st.get("state") == "home",
                        "state": st.get("state"), "since": st.get("last_changed")})
        return out
    except Exception:
        return []
