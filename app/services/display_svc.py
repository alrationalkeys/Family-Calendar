"""
Display power control — the software side of the "screen off overnight, wake on
motion" trick (their PIR + Zigbee smart-plug idea, done without extra hardware).

On a Raspberry Pi the wall's own backlight is cut with `vcgencmd display_power 0`
and brought back with `... 1`, so the panel genuinely powers down at night instead
of just showing a black slideshow. A `/api/display/wake` webhook lets a cheap PIR
sensor (or Home Assistant) wake it when someone walks up.

Everything degrades gracefully: off a Pi the OS command just no-ops and the wall
falls back to a black overlay (set dim_only to force that everywhere).

Config lives in the settings table under key 'display':
    enabled        schedule on/off
    off_start      "HH:MM" local — night window start
    off_end        "HH:MM" local — night window end (may cross midnight)
    wake_grace_min stay awake this many minutes after a wake ping
    dim_only       just black-overlay the UI, never touch the OS backlight
"""
import os
import json
import time
import shlex
import subprocess
from datetime import datetime

from ..db import get_db

KEY = "display"
DEFAULTS = {
    "enabled": True,          # screen off overnight by default (10 pm – 6:30 am)
    "off_start": "22:00",
    "off_end": "06:30",
    "wake_grace_min": 3,
    "dim_only": False,
}

# OS backlight commands — override for Wayland/labwc or non-Pi setups.
ON_CMD = os.getenv("FAMILYHUB_SCREEN_ON_CMD", "vcgencmd display_power 1")
OFF_CMD = os.getenv("FAMILYHUB_SCREEN_OFF_CMD", "vcgencmd display_power 0")

# in-memory runtime state
_state = {"on": True, "last_wake": 0.0, "force_off": False, "applied": None,
          "sleep_mode": False, "sleep_since": None, "alarm": None, "alarm_checked": 0.0}

# ---- sleep mode: the alarm decides ------------------------------------------
# When the IQ Panel is armed for the night (Alarm.com "Night" -> armed_night) the wall goes dark
# straight away: backlight off, no photo screensaver. A tap shows the wall for SLEEP_PEEK seconds,
# then it goes dark again. Sleep ends with the morning routine: disarming the alarm, saying
# "good morning", or POST /api/display/morning (an HA automation can call it). FamilyHub's own
# "Good night" also starts it (and arms Night, falling back to Stay on panels without Night).
SLEEP_PEEK = 60


def _sleep_settings():
    try:
        from ..routers.settings import get_settings
        s = get_settings() or {}
    except Exception:
        s = {}
    states = s.get("sleepArmStates") or ["armed_night"]
    return s.get("sleepOnNightArm", True) is not False, set(states)


def enter_sleep(reason="alarm"):
    if not _state["sleep_mode"]:
        _state["sleep_mode"] = True
        _state["sleep_since"] = time.time()
        _state["last_wake"] = 0.0
    return tick()


def exit_sleep(reason="morning"):
    was = _state["sleep_mode"]
    _state["sleep_mode"] = False
    _state["sleep_since"] = None
    _state["force_off"] = False
    if was:
        _state["last_wake"] = time.time()      # light up now; the normal schedule takes over after the grace
    return tick()


def on_alarm(new_state: str | None, old_state: str | None = None):
    """Called on every alarm panel change (live from ha_live, or by the fallback poll)."""
    on, arm_states = _sleep_settings()
    if not on or not new_state or new_state == _state["alarm"]:
        _state["alarm"] = new_state or _state["alarm"]
        return
    prev = _state["alarm"] if old_state is None else old_state
    _state["alarm"] = new_state
    if new_state in arm_states:
        enter_sleep()
    elif _state["sleep_mode"] and new_state == "disarmed":
        exit_sleep()          # only disarming ends the night: a Stay fallback or leaving (Away) keeps it dark


def _poll_alarm():
    """Fallback when the live link isn't running: read the panel at most every 30 s."""
    if time.time() - _state["alarm_checked"] < 30:
        return
    _state["alarm_checked"] = time.time()
    try:
        from . import ha_svc
        for g in ha_svc.get_home().get("groups", []):
            for t in g.get("tiles", []):
                if t.get("domain") == "alarm_control_panel":
                    on_alarm(t.get("state"))
                    return
    except Exception:
        pass


def get_config():
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (KEY,)).fetchone()
    if not row:
        return dict(DEFAULTS)
    try:
        return {**DEFAULTS, **json.loads(row["value"])}
    except json.JSONDecodeError:
        return dict(DEFAULTS)


def set_config(patch):
    cfg = {**get_config(), **(patch or {})}
    clean = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (KEY, json.dumps(clean)))
    return clean


def _hm(s, default):
    try:
        h, m = s.split(":")
        return int(h), int(m)
    except Exception:
        return default


def _in_night_window(now, cfg):
    sh, sm = _hm(cfg["off_start"], (22, 0))
    eh, em = _hm(cfg["off_end"], (6, 30))
    cur = now.hour * 60 + now.minute
    start = sh * 60 + sm
    end = eh * 60 + em
    if start == end:
        return False
    if start < end:            # same-day window, e.g. 13:00–15:00
        return start <= cur < end
    return cur >= start or cur < end   # crosses midnight, e.g. 22:00–06:30


def desired_on(now=None):
    cfg = get_config()
    now = now or datetime.now()
    if _state["sleep_mode"]:
        return (time.time() - _state["last_wake"]) < SLEEP_PEEK, cfg
    if not cfg.get("enabled"):
        return True, cfg
    night = _in_night_window(now, cfg)
    if not night:
        _state["force_off"] = False     # a new day clears a manual off
        return True, cfg
    # in the night window: off, unless a recent wake ping is still within grace
    grace = max(0, int(cfg.get("wake_grace_min", 3))) * 60
    if _state["force_off"]:
        return False, cfg
    if grace and (time.time() - _state["last_wake"]) < grace:
        return True, cfg
    return False, cfg


def _run(cmd):
    try:
        subprocess.run(shlex.split(cmd), timeout=5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False   # not a Pi / command missing -> overlay handles it


def tick():
    """Recompute desired power and apply it if it changed. Safe to call often."""
    _poll_alarm()
    on, cfg = desired_on()
    _state["on"] = on
    if _state["applied"] != on:
        if not cfg.get("dim_only"):
            _run(ON_CMD if on else OFF_CMD)
        _state["applied"] = on
    return state(cfg)


def wake():
    _state["last_wake"] = time.time()
    _state["force_off"] = False
    return tick()


def sleep_now():
    _state["force_off"] = True
    _state["last_wake"] = 0.0
    return tick()


def state(cfg=None):
    cfg = cfg or get_config()
    now = datetime.now()
    return {
        "on": _state["on"],
        "night": _in_night_window(now, cfg) if cfg.get("enabled") else False,
        "dim_only": bool(cfg.get("dim_only")),
        "sleep_mode": _state["sleep_mode"],
        "config": cfg,
    }
