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


# ---- customizable steps (phone Settings > House buttons > Edit steps) --------------------------------------------
# settings row 'house_modes' = {goodnight: [step], away: [step], welcome: [step]}; a mode with no list runs the built-in
# sequence below. Step = {type, entities?, ...} with the routine builder's shapes plus arm / open_garage /
# schedule / village. "Group" entities: *lights *indoor *outdoor *tvs *locks *garage *entry.
# Locked in whatever the steps say: I'm home disarms only with the typed code and opens the garage only after a
# successful disarm; nothing else ever disarms or unlocks; Leaving won't arm with a door open.
GROUPS = {"*lights": "all the lights", "*indoor": "the indoor lights", "*outdoor": "the outside lights", "*tvs": "the TVs",
          "*locks": "all the locks", "*garage": "the garage door", "*entry": "the entry lights"}


STEP_TYPES = {"off", "on", "dim", "lock", "close", "arm", "open_garage", "thermostat", "schedule", "village", "scene", "say"}


def save_steps(mode: str, steps) -> dict:
    """Validate + store a button's steps (None / [] = back to the built-in sequence)."""
    import json
    from ..db import get_db
    if mode not in ("goodnight", "away", "welcome"):
        return {"ok": False, "reason": "unknown button"}
    clean = []
    for st in steps or []:
        if not isinstance(st, dict) or st.get("type") not in STEP_TYPES:
            continue
        if st["type"] == "open_garage" and mode != "welcome":
            continue                                   # only I'm home opens the garage
        ents = [str(e) for e in (st.get("entities") or []) if re.fullmatch(r"\*[a-z]+|[a-z_]+\.[a-z0-9_]+", str(e))]
        x = {k: v for k, v in st.items() if k in ("type", "arm", "mode", "temp", "cool", "pct", "white", "rgb", "dark", "village", "message")}
        x["entities"] = ents
        if st["type"] in ("off", "on", "dim", "lock", "close", "scene") and not ents:
            return {"ok": False, "reason": "Pick what each step is for"}
        clean.append(x)
    hm = _custom()          # its own settings row, so a phone saving the 'ui' settings can't wipe it
    if clean:
        hm[mode] = clean
    else:
        hm.pop(mode, None)
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('house_modes', ?)", (json.dumps(hm),))
    return {"ok": True, "steps": steps_for(mode)[0], "custom": bool(clean)}


def default_steps(mode: str) -> list:
    """What each button does when it hasn't been customized (from the older checkbox settings)."""
    s = _settings()
    garage = s.get("closeGarageOnModes", True) is not False
    vil = s.get("villageWithHouse", True) is not False
    if mode == "goodnight":
        st = ([{"type": "off", "entities": ["*indoor", "*tvs"]}] if s.get("goodnightLightsOff") is True else []) + \
             [{"type": "lock", "entities": ["*locks"]}] + ([{"type": "close", "entities": ["*garage"]}] if garage else []) + \
             [{"type": "arm", "arm": "stay"}]
        if s.get("nightTemp"):
            st.append({"type": "thermostat", "entities": ["*all"], "mode": "keep", "temp": s["nightTemp"]})
    elif mode == "away":
        st = [{"type": "off", "entities": ["*lights", "*tvs"]}, {"type": "lock", "entities": ["*locks"]}] + \
             ([{"type": "close", "entities": ["*garage"]}] if garage else []) + \
             [{"type": "arm", "arm": "away" if s.get("awayArm") == "away" else "stay"}]
        if s.get("awayTemp"):
            st.append({"type": "thermostat", "entities": ["*all"], "mode": "keep", "temp": s["awayTemp"]})
    elif mode == "welcome":
        st = ([{"type": "open_garage"}] if s.get("openGarageOnHome", True) is not False else []) + \
             [{"type": "on", "entities": ["*entry"], "dark": True}]
        st.append({"type": "thermostat", "entities": ["*all"], "mode": "keep", "temp": s["homeTemp"]} if s.get("homeTemp") else {"type": "schedule"})
    else:
        return []
    if vil:
        st.append({"type": "village", "village": "wake" if mode == "welcome" else "sleep"})
    return st


def _custom() -> dict:
    import json
    from ..db import get_db
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='house_modes'").fetchone()
            return json.loads(row["value"]) if row else {}
    except Exception:
        return {}


def steps_for(mode: str) -> tuple[list, bool]:
    custom = _custom().get(mode)
    return (custom, True) if isinstance(custom, list) and custom else (default_steps(mode), False)


def _expand(ids, tiles) -> list:
    out = []
    for e in ids or []:
        if e == "*lights" or e == "*indoor" or e == "*outdoor":
            lt = [t for t in tiles if t["domain"] == "light" or (t["domain"] == "switch" and re.search(r"light|lamp|led|strip|plug", t["name"], re.I))]
            if e != "*lights":
                outside = lambda t: bool(_OUTDOOR.search(t["name"] + " " + str(t.get("area") or "")))
                lt = [t for t in lt if outside(t) == (e == "*outdoor")]
            out += lt
        elif e == "*tvs":
            out += [t for t in tiles if t["domain"] == "media_player" and not re.search(r"spotify|familyhub", t["entity_id"] + t["name"], re.I)]
        elif e == "*locks":
            out += [t for t in tiles if t["domain"] == "lock"]
        elif e == "*garage":
            out += [t for t in tiles if t["domain"] == "cover"]
        elif e == "*entry":
            out += [t for t in tiles if t["domain"] == "light" and _ENTRY.search(t["name"] + " " + str(t.get("area") or ""))]
        elif e == "*all":
            out += [t for t in tiles if t["domain"] == "climate"]
        else:
            out += [t for t in tiles if t["entity_id"] == e]
    seen, uniq = set(), []
    for t in out:
        if t["entity_id"] not in seen:
            seen.add(t["entity_id"]); uniq.append(t)
    return uniq


def _run_steps(mode, steps, tiles, s, code, open_garage, done, warnings, notes, tapped=False):
    by = lambda dom: [t for t in tiles if t["domain"] == dom]
    peak = next((t for t in tiles if t["entity_id"] == "binary_sensor.santee_cooper_peak_now"), None)
    in_peak = bool(peak and peak.get("on"))
    still_armed = False
    if mode == "welcome":                              # locked in: disarm with the typed code, first
        for t in by("alarm_control_panel"):
            if not t["state"].startswith("armed") and t["state"] not in ("arming", "pending", "triggered"):
                continue
            if code or (tapped and s.get("welcomeNoCode") is True):
                r = ha_svc.call_service("alarm_control_panel", "alarm_disarm", t["entity_id"], {"code": str(code)} if code else None)
                if r.get("ok"):
                    done.append("disarmed the alarm")
                else:
                    still_armed = True
                    warnings.append("the alarm didn't disarm, check the code" if code else "the alarm wants a code to disarm, turn the no-code option off")
            else:
                still_armed = True; warnings.append("the alarm is still armed, disarm it on the keypad")
    gcover = ha_svc.has_garage_cover(by("cover"))
    open_now = [ha_svc.opening_label(t, gcover) for t in by("binary_sensor")
                if t.get("device_class") in ("door", "window", "garage_door", "opening") and t["on"]]
    open_now = [x for x in open_now if x]
    for st in steps:
        k = st.get("type")
        try:
            if k in ("off", "on", "dim"):
                ts = _expand(st.get("entities"), tiles)
                if k == "on" and st.get("dark") and not _after_dark():
                    continue
                if k == "off":
                    ts = [t for t in ts if t["on"] or t["domain"] == "media_player" and t["state"] not in ("off", "unavailable", "standby")]
                if k == "on":
                    ts = [t for t in ts if not t["on"]]
                for t in ts:
                    if t["domain"] == "lock" or t["domain"] == "cover":
                        continue                      # locks/garage have their own steps
                    data = {}
                    if k == "dim" and t["domain"] == "light":
                        data["brightness_pct"] = max(1, min(100, int(st.get("pct") or 50)))
                        if st.get("white") in ("warm", "daylight", "cool"):
                            data["color_temp_kelvin"] = {"warm": 2700, "daylight": 4000, "cool": 5000}[st["white"]]
                        elif st.get("white") == "color" and len(st.get("rgb") or []) == 3:
                            data["rgb_color"] = [int(x) for x in st["rgb"]]
                    ha_svc.call_service(t["domain"], "turn_off" if k == "off" else "turn_on", t["entity_id"], data or None)
                if ts:
                    n_tv = sum(1 for t in ts if t["domain"] == "media_player")
                    n_l = len(ts) - n_tv
                    bits = ([_plural(n_l, "light")] if n_l else []) + ([_plural(n_tv, "TV")] if n_tv else [])
                    done.append(("turned off " if k == "off" else "turned on " if k == "on" else "set ") + " and ".join(bits))
            elif k == "lock":                         # lock only, never unlock
                ts = [t for t in _expand(st.get("entities") or ["*locks"], tiles) if t["domain"] == "lock"]
                unl = [t for t in ts if t["state"] != "locked"]
                for t in unl:
                    ha_svc.call_service("lock", "lock", t["entity_id"])
                if unl:
                    done.append(f"locked the {', '.join(t['name'] for t in unl)}")
                elif ts:
                    notes.append("The doors are locked.")
            elif k == "close":                        # close only
                for t in [t for t in _expand(st.get("entities") or ["*garage"], tiles) if t["domain"] == "cover"]:
                    if t["state"] in ("open", "opening"):
                        ha_svc.call_service("cover", "close_cover", t["entity_id"])
                        done.append(f"closed the {t['name']}")
            elif k == "arm":
                if mode == "away" and open_now:
                    warnings.append("I didn't arm the alarm because " + ", ".join(open_now) + (" is" if len(open_now) == 1 else " are") + " open")
                    continue
                svc = {"away": "alarm_arm_away", "night": "alarm_arm_night"}.get(st.get("arm"), "alarm_arm_home")
                for t in by("alarm_control_panel"):
                    r = ha_svc.call_service("alarm_control_panel", svc, t["entity_id"])
                    done.append(("armed the alarm" + {"alarm_arm_away": " (Away)", "alarm_arm_night": " for the night"}.get(svc, "")) if r.get("ok") else "couldn't arm the alarm")
            elif k == "open_garage" and mode == "welcome" and open_garage:
                for t in by("cover"):
                    if re.search(r"garage", t["name"] + " " + t["entity_id"], re.I) and t["state"] in ("closed", "closing"):
                        if still_armed:
                            warnings.append("I left the garage closed because the alarm is armed"); break
                        ha_svc.call_service("cover", "open_cover", t["entity_id"])
                        done.append(f"opened the {t['name']}")
            elif k == "thermostat":
                ts = [t for t in _expand(st.get("entities") or ["*all"], tiles) if t["domain"] == "climate"]
                m, temp = st.get("mode") or "keep", st.get("temp")
                if in_peak and m != "off":
                    notes.append("It's peak hours, so I left the heat and air alone."); continue
                for t in ts:
                    if m in ("heat", "cool", "heat_cool", "auto", "off"):
                        ha_svc.call_service("climate", "set_hvac_mode", t["entity_id"], {"hvac_mode": m})
                    if temp and m != "off":
                        now_mode = m if m != "keep" else t.get("state")
                        if now_mode in ("heat_cool", "auto"):     # Auto needs a range: heat to temp, cool to the cool setting
                            hi = float(st.get("cool") or (float(temp) + 4))
                            ha_svc.call_service("climate", "set_temperature", t["entity_id"],
                                                {"target_temp_low": float(temp), "target_temp_high": max(hi, float(temp) + 2)})
                        else:
                            ha_svc.call_service("climate", "set_temperature", t["entity_id"], {"temperature": float(temp)})
                if ts:
                    done.append("turned the thermostat off" if m == "off" else f"set the thermostat to {int(float(temp))}" if temp else "set the thermostat")
            elif k == "schedule":
                if in_peak:
                    continue
                ha_svc.call_service("script", "turn_on", "script.fhs_thermostat_now")
                done.append("put the thermostats back on their schedule")
            elif k == "village":
                from . import village
                if village.status().get("reachable"):
                    if st.get("village") == "wake":
                        village.resume(); village.command("wake"); done.append("woke the village")
                    else:
                        v = village.pause_for_night()
                        if v:
                            done.append(v)
            elif k == "scene":
                for e in st.get("entities") or []:
                    if str(e).startswith("scene."):
                        ha_svc.call_service("scene", "turn_on", e)
            elif k == "say":
                msg = str(st.get("message") or "").strip()[:200]
                if msg:
                    notes.append(msg if msg.endswith((".", "!", "?")) else msg + ".")
        except Exception:
            warnings.append(f"one step ({k}) didn't work")
    # anything left open that no step closed
    for lbl in open_now:
        if mode != "welcome" and f"{lbl} is open" not in " ".join(warnings):
            warnings.append(f"the {lbl.lower()} is open" if lbl == "Door to garage" else f"{lbl} is open")


def run(mode: str, who: str | None = None, close_garage: bool | None = None, arm: bool = True, source: str = "wall",
        code: str | None = None, open_garage: bool = False, tapped: bool = False) -> dict:
    """tapped = the I'm home BUTTON (wall or phone). Only a tap may disarm without a code (settings.welcomeNoCode);
    voice never disarms."""
    mode = (mode or "").lower()
    tiles = _tiles()
    s = _settings()
    steps, custom = steps_for(mode)
    if custom:
        done, warnings, notes = [], [], []
        if not arm:
            steps = [x for x in steps if x.get("type") != "arm"]
        _run_steps(mode, steps, tiles, s, code, open_garage, done, warnings, notes, tapped=tapped)
        if mode == "goodnight":
            try:
                from . import display_svc
                if display_svc._sleep_settings()[0]:
                    display_svc.enter_sleep("goodnight")
            except Exception:
                pass
        lead = "Good night." if mode == "goodnight" else "Bye for now." if mode == "away" else f"Welcome home{', ' + who if who else ''}."
        return _finish(mode, lead, done, warnings, notes, source)
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
        # the Christmas village: quiet for the night (FamilyHub puts it back on automatic in the morning)
        if s.get("villageWithHouse", True) is not False:
            try:
                from . import village
                if village.status().get("reachable"):
                    v = village.pause_for_night()
                    if v:
                        done.append(v)
            except Exception:
                pass
        lead = "Good night." if mode == "goodnight" else "Bye for now."
        if mode == "goodnight":
            try:
                from . import display_svc
                if display_svc._sleep_settings()[0]:
                    display_svc.enter_sleep("goodnight")       # wall goes dark now, even if the panel reports Stay
            except Exception:
                pass
    elif mode == "welcome":
        try:                                   # village back on automatic if Good night / Leaving paused it
            from . import village
            village.resume()
        except Exception:
            pass
        # 1) disarm with the code from the keypad
        still_armed = False
        for t in by("alarm_control_panel"):
            if not t["state"].startswith("armed") and t["state"] not in ("arming", "pending", "triggered"):
                continue
            if code or (tapped and s.get("welcomeNoCode") is True):
                r = ha_svc.call_service("alarm_control_panel", "alarm_disarm", t["entity_id"], {"code": str(code)} if code else None)
                if r.get("ok"):
                    done.append("disarmed the alarm")
                else:
                    still_armed = True
                    warnings.append("the alarm didn't disarm, check the code" if code else "the alarm wants a code to disarm, turn the no-code option off")
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
    return _finish(mode, lead, done, warnings, notes, source)


def _finish(mode, lead, done, warnings, notes, source):
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
