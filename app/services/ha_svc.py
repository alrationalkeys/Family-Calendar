"""
Home Assistant bridge for the FamilyHub "Home" tab.

FamilyHub never talks to the lights/alarm/TVs directly — Home Assistant (running
headless on a *separate* Pi, see docs/home-assistant-setup.md) is the brain that
does that. This module is a thin, defensive REST client against HA's API:

    GET  {HA_URL}/api/states                  -> every entity + its state
    POST {HA_URL}/api/services/<domain>/<svc>  -> turn things on/off, etc.

Config comes from the environment (server-side only — the long-lived token must
never reach the browser):
    HA_URL    e.g. http://homeassistant.local:8123   (or a Tailscale IP)
    HA_TOKEN  a Home Assistant "long-lived access token"

Demo mode (default when HA_URL/HA_TOKEN aren't set, or HA_DEMO=1) serves a fixed
set of fake devices so the Home tab is fully explorable on the Surface / wall
before the real HA Pi exists. Toggles against the demo flip in-memory state so
the UI feels live.

Design rule: this module NEVER raises to the caller. HA being down, slow, or
misconfigured returns a clean {"connected": False, ...} payload so the wall
degrades gracefully instead of showing a stack trace.
"""
from __future__ import annotations

import os
import time
import copy
import json
import urllib.request
import urllib.error

# ---- config -----------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()

def ha_url() -> str:
    return _env("HA_URL").rstrip("/")

def ha_token() -> str:
    return _env("HA_TOKEN")

def demo_mode() -> bool:
    """Demo unless we have a real URL+token and HA_DEMO isn't forcing it on."""
    if _env("HA_DEMO") in ("1", "true", "yes", "on"):
        return True
    return not (ha_url() and ha_token())

# Which HA domains FamilyHub surfaces, and how we group them into tabs/sections.
# Everything else from HA is ignored so the wall stays glanceable.
DOMAIN_GROUP = {
    "light": "Lights",
    "switch": "Switches & Plugs",
    "fan": "Switches & Plugs",
    "cover": "Doors & Covers",
    "lock": "Doors & Covers",
    "climate": "Climate",
    "media_player": "Media & TVs",
    "scene": "Scenes",
    "script": "Scenes",
    "binary_sensor": "Sensors",
    "sensor": "Sensors",
    "alarm_control_panel": "Security",
}
# Order sections appear in on the Home tab.
GROUP_ORDER = ["Security", "Lights", "Switches & Plugs", "Climate",
               "Doors & Covers", "Media & TVs", "Scenes", "Sensors"]

# "on-ish" states that mean a tile should look active.
_ON_STATES = {"on", "open", "unlocked", "home", "playing", "heat", "cool",
              "heat_cool", "auto", "armed_home", "armed_away", "armed_night"}


# ---- demo data ---------------------------------------------------------------

def _demo_seed():
    return {
        "alarm_control_panel.iq_panel": {"state": "disarmed",
            "attributes": {"friendly_name": "IQ Panel", "icon": "shield"}},
        "light.living_room": {"state": "on",
            "attributes": {"friendly_name": "Living Room", "brightness": 200}},
        "light.kitchen": {"state": "off", "attributes": {"friendly_name": "Kitchen"}},
        "light.master_bed": {"state": "off", "attributes": {"friendly_name": "Master Bedroom"}},
        "light.porch": {"state": "on", "attributes": {"friendly_name": "Front Porch"}},
        "switch.coffee": {"state": "off", "attributes": {"friendly_name": "Coffee Maker"}},
        "switch.fireplace": {"state": "off", "attributes": {"friendly_name": "Fireplace"}},
        "fan.bedroom": {"state": "on", "attributes": {"friendly_name": "Bedroom Fan"}},
        "cover.garage": {"state": "closed", "attributes": {"friendly_name": "Garage Door"}},
        "lock.front_door": {"state": "locked", "attributes": {"friendly_name": "Front Door"}},
        "climate.thermostat": {"state": "heat",
            "attributes": {"friendly_name": "Thermostat", "current_temperature": 71,
                           "temperature": 72}},
        "media_player.living_room_tv": {"state": "off",
            "attributes": {"friendly_name": "Living Room Roku"}},
        "media_player.bedroom_tv": {"state": "off",
            "attributes": {"friendly_name": "Bedroom Roku"}},
        "scene.movie_time": {"state": "scening", "attributes": {"friendly_name": "Movie Time"}},
        "scene.good_night": {"state": "scening", "attributes": {"friendly_name": "Good Night"}},
        "scene.leaving": {"state": "scening", "attributes": {"friendly_name": "Leaving Home"}},
        "binary_sensor.front_door_contact": {"state": "off",
            "attributes": {"friendly_name": "Front Door", "device_class": "door"}},
        "binary_sensor.back_door_contact": {"state": "off",
            "attributes": {"friendly_name": "Back Door", "device_class": "door"}},
        "binary_sensor.garage_motion": {"state": "off",
            "attributes": {"friendly_name": "Garage Motion", "device_class": "motion"}},
        "sensor.living_room_temp": {"state": "71",
            "attributes": {"friendly_name": "Living Room Temp", "unit_of_measurement": "°F",
                           "device_class": "temperature"}},
        "sensor.outdoor_temp": {"state": "63",
            "attributes": {"friendly_name": "Outdoor Temp", "unit_of_measurement": "°F",
                           "device_class": "temperature"}},
    }

# Mutable in-memory demo state, so demo toggles feel live within a server run.
_DEMO = _demo_seed()


# ---- HTTP (real HA) ----------------------------------------------------------

def _request(path: str, method: str = "GET", payload=None, timeout: float = 5.0):
    url = ha_url() + path
    data = None
    headers = {"Authorization": f"Bearer {ha_token()}", "Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8")
        return json.loads(body) if body else None


# ---- tile shaping ------------------------------------------------------------

def _tile(entity_id: str, state: str, attrs: dict) -> dict:
    domain = entity_id.split(".", 1)[0]
    name = attrs.get("friendly_name") or entity_id.split(".", 1)[-1].replace("_", " ").title()
    on = state in _ON_STATES
    tile = {
        "entity_id": entity_id,
        "domain": domain,
        "name": name,
        "state": state,
        "on": on,
        "group": DOMAIN_GROUP.get(domain, "Other"),
        # what a tap should do; the frontend decides whether a tile is tappable
        "toggleable": domain in ("light", "switch", "fan", "cover", "lock",
                                 "media_player"),
        "activatable": domain in ("scene", "script"),
    }
    # a few helpful extras for display
    if domain == "climate":
        tile["current_temperature"] = attrs.get("current_temperature")
        tile["target_temperature"] = attrs.get("temperature")
    if domain in ("sensor",):
        tile["unit"] = attrs.get("unit_of_measurement", "")
        tile["device_class"] = attrs.get("device_class", "")
    if domain in ("binary_sensor",):
        tile["device_class"] = attrs.get("device_class", "")
    if domain == "alarm_control_panel":
        tile["armed"] = state.startswith("armed")
    return tile


def _states_to_tiles(states) -> list:
    tiles = []
    for s in states:
        eid = s.get("entity_id", "")
        domain = eid.split(".", 1)[0]
        if domain not in DOMAIN_GROUP:
            continue
        tiles.append(_tile(eid, s.get("state", ""), s.get("attributes", {}) or {}))
    return tiles


def _grouped(tiles: list) -> list:
    """Return [{group, tiles:[...]}] in GROUP_ORDER, skipping empty groups."""
    buckets = {}
    for t in tiles:
        buckets.setdefault(t["group"], []).append(t)
    for g in buckets.values():
        g.sort(key=lambda t: t["name"].lower())
    out = []
    seen = set()
    for name in GROUP_ORDER:
        if buckets.get(name):
            out.append({"group": name, "tiles": buckets[name]})
            seen.add(name)
    # any leftover groups (e.g. "Other") after the known order
    for name, g in buckets.items():
        if name not in seen:
            out.append({"group": name, "tiles": g})
    return out


# ---- public API --------------------------------------------------------------

def get_home() -> dict:
    """The whole Home tab in one call: connection status + grouped tiles.

    Never raises — a failure comes back as connected:False with a reason so the
    wall can show a friendly 'Home Assistant offline' card.
    """
    demo = demo_mode()
    if demo:
        states = [{"entity_id": eid, "state": v["state"],
                   "attributes": v.get("attributes", {})}
                  for eid, v in _DEMO.items()]
        tiles = _states_to_tiles(states)
        return {"connected": True, "demo": True,
                "groups": _grouped(tiles), "count": len(tiles)}
    try:
        states = _request("/api/states")
        tiles = _states_to_tiles(states or [])
        return {"connected": True, "demo": False,
                "groups": _grouped(tiles), "count": len(tiles)}
    except urllib.error.HTTPError as e:
        reason = "bad token (401)" if e.code == 401 else f"HA error {e.code}"
        return {"connected": False, "demo": False, "groups": [], "reason": reason}
    except Exception as e:
        return {"connected": False, "demo": False, "groups": [],
                "reason": "can't reach Home Assistant"}


def _demo_toggle(entity_id: str, service: str):
    """Apply a service call to the in-memory demo so the UI reacts."""
    cur = _DEMO.get(entity_id)
    domain = entity_id.split(".", 1)[0]
    if domain == "scene" or domain == "script":
        return  # activating a scene doesn't change its own tile
    if cur is None:
        return
    if domain == "alarm_control_panel":
        cur["state"] = {"alarm_disarm": "disarmed", "alarm_arm_home": "armed_home",
                        "alarm_arm_away": "armed_away", "alarm_arm_night": "armed_night"
                        }.get(service, cur["state"])
        return
    s = cur["state"]
    if service == "toggle":
        pairs = {"on": "off", "off": "on", "open": "closed", "closed": "open",
                 "locked": "unlocked", "unlocked": "locked",
                 "playing": "off", "idle": "off"}
        cur["state"] = pairs.get(s, "on" if s in ("off", "closed", "locked") else "off")
    elif service in ("turn_on", "open_cover", "unlock"):
        cur["state"] = {"open_cover": "open", "unlock": "unlocked"}.get(service, "on")
    elif service in ("turn_off", "close_cover", "lock"):
        cur["state"] = {"close_cover": "closed", "lock": "locked"}.get(service, "off")


def call_service(domain: str, service: str, entity_id: str = "", extra: dict = None) -> dict:
    """Call an HA service (or mutate demo state). Returns {ok, ...}."""
    if demo_mode():
        if entity_id:
            _demo_toggle(entity_id, service)
        return {"ok": True, "demo": True}
    payload = dict(extra or {})
    if entity_id:
        payload["entity_id"] = entity_id
    try:
        _request(f"/api/services/{domain}/{service}", method="POST", payload=payload)
        return {"ok": True, "demo": False}
    except urllib.error.HTTPError as e:
        return {"ok": False, "reason": f"HA error {e.code}"}
    except Exception:
        return {"ok": False, "reason": "can't reach Home Assistant"}


def toggle(entity_id: str) -> dict:
    """Smart toggle for the common domains, picking the right service per domain."""
    domain = entity_id.split(".", 1)[0]
    if domain in ("light", "switch", "fan", "media_player"):
        return call_service(domain, "toggle", entity_id)
    if domain == "cover":
        # covers have no 'toggle'; decide from current state
        cur = _current_state(entity_id)
        svc = "close_cover" if cur in ("open", "opening") else "open_cover"
        return call_service("cover", svc, entity_id)
    if domain == "lock":
        cur = _current_state(entity_id)
        svc = "unlock" if cur == "locked" else "lock"
        return call_service("lock", svc, entity_id)
    if domain in ("scene", "script"):
        return call_service(domain, "turn_on", entity_id)
    return {"ok": False, "reason": f"{domain} isn't toggleable"}


def _current_state(entity_id: str) -> str:
    if demo_mode():
        cur = _DEMO.get(entity_id)
        return cur["state"] if cur else ""
    try:
        s = _request(f"/api/states/{entity_id}")
        return (s or {}).get("state", "")
    except Exception:
        return ""


def status() -> dict:
    """Light-weight status for a top bar: connected? alarm state? open doors?"""
    home = get_home()
    alarm, open_doors, temps = None, [], []
    for grp in home.get("groups", []):
        for t in grp["tiles"]:
            if t["domain"] == "alarm_control_panel":
                alarm = t["state"]
            if t["domain"] == "binary_sensor" and t.get("device_class") in ("door", "garage_door", "window") and t["on"]:
                open_doors.append(t["name"])
            if t["domain"] == "cover" and t["state"] in ("open", "opening"):
                open_doors.append(t["name"])
    return {"connected": home.get("connected"), "demo": home.get("demo"),
            "alarm": alarm, "open_doors": open_doors,
            "reason": home.get("reason")}
