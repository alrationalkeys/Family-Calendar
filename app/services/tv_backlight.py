"""
TV backlights (a WLED strip behind a TV) that follow the TV. Hooked into ha_live state changes.

  settings.tvBacklights = [{light, tv, follow, dim, play, idle}]
    light   the backlight's light entity (WLED shows up in Home Assistant as a light)
    tv      the TV's media_player entity (Roku)
    follow  on when the TV comes on, off when it goes off (for strips that are NOT powered from the TV's USB port)
    dim     movie dimming: brightness `play` % while something is playing, `idle` % when paused / on the home screen
Only brightness and on/off are touched, so whatever colour or effect was picked stays. A strip powered from the TV's
USB port is simply unavailable while the TV is off: nothing is sent to it then. While Game day is flashing the same
light, changes wait until it is done.
"""
from __future__ import annotations

import threading
import time

from . import ha_svc

_OFF = {"off", "standby", "unavailable", "unknown", ""}
_PLAYING = {"playing", "buffering"}
_S: dict = {"last": {}}


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def pairs(s: dict | None = None) -> list:
    s = s if s is not None else _settings()
    out = []
    for p in (s.get("tvBacklights") or []):
        if isinstance(p, dict) and str(p.get("light", "")).startswith("light.") and str(p.get("tv", "")).startswith("media_player."):
            out.append({"light": p["light"], "tv": p["tv"], "follow": p.get("follow", True) is not False,
                        "dim": p.get("dim", True) is not False,
                        "play": max(1, min(100, int(p.get("play") or 30))), "idle": max(1, min(100, int(p.get("idle") or 70)))})
    return out


def _mode(tv_state: str) -> str:
    st = str(tv_state or "").lower()
    return "off" if st in _OFF else "play" if st in _PLAYING else "idle"


def want(pair: dict, tv_state: str, light_on: bool) -> tuple | None:
    """What to send for this TV state: ("turn_off", None) / ("turn_on", {brightness_pct}) / None for nothing."""
    m = _mode(tv_state)
    if m == "off":
        return ("turn_off", None) if pair["follow"] and light_on else None
    if not light_on and not pair["follow"]:
        return None                                    # they keep it off by hand: don't turn it on for them
    if pair["dim"]:
        return ("turn_on", {"brightness_pct": pair[m]})
    return ("turn_on", {}) if not light_on else None


def _apply(pair: dict, tv_state: str):
    time.sleep(1.2)                                    # a Roku flips through states when an app starts: take the last one
    if _S["last"].get(pair["tv"]) != tv_state:
        return
    try:
        from . import gameday
        for _ in range(20):                            # Game day is flashing this light: wait for it to put it back
            if pair["light"] not in (gameday._S.get("flashing") or ()):
                break
            time.sleep(1)
    except Exception:
        pass
    try:
        st = None if ha_svc.demo_mode() else ha_svc._request(f"/api/states/{pair['light']}")
    except Exception:
        return
    if st is not None and st.get("state") in ("unavailable", "unknown"):
        return
    act = want(pair, tv_state, bool(st and st.get("state") == "on"))
    if act:
        ha_svc.call_service("light", act[0], pair["light"], act[1])


def on_state(eid: str, old: dict | None, new: dict | None):
    if not eid.startswith("media_player.") or not new:
        return
    state = str(new.get("state") or "")
    if old and _mode(old.get("state")) == _mode(state) and _S["last"].get(eid) is not None:
        _S["last"][eid] = state
        return                                         # same kind of state (e.g. idle -> home): nothing to change
    _S["last"][eid] = state
    for p in pairs():
        if p["tv"] == eid:
            threading.Thread(target=_apply, args=(p, state), daemon=True, name="tv-backlight").start()
