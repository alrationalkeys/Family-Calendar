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
import re
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
    "camera": "Cameras",
}
# Order sections appear in on the Home tab.
GROUP_ORDER = ["Security", "Cameras", "Lights", "Switches & Plugs", "Climate",
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
        "media_player.spotify_family": {"state": "playing",
            "attributes": {"friendly_name": "Spotify", "media_title": "Here Comes the Sun",
                           "media_artist": "The Beatles", "media_album_name": "Abbey Road",
                           "volume_level": 0.45, "shuffle": False, "source": "FamilyHub",
                           "source_list": ["FamilyHub", "Living Room TV", "Bedroom TV", "Alex's iPhone"],
                           "media_playlist": "Dinner Vibes"}},
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
        "sensor.power_now": {"state": "741",
            "attributes": {"friendly_name": "Power Now", "unit_of_measurement": "W",
                           "device_class": "power"}},
        "sensor.energy_today": {"state": "12.5",
            "attributes": {"friendly_name": "Energy Today", "unit_of_measurement": "kWh",
                           "device_class": "energy"}},
    }

# Mutable in-memory demo state, so demo toggles feel live within a server run.
_DEMO = _demo_seed()
_DEMO.setdefault("light.driveway", {"state": "off", "attributes": {"friendly_name": "Driveway Light"}})
_DEMO.setdefault("camera.front_door", {"state": "idle", "attributes": {"friendly_name": "Front Door Doorbell"}})
_DEMO.setdefault("camera.backyard", {"state": "idle", "attributes": {"friendly_name": "Backyard"}})
_DEMO.setdefault("binary_sensor.front_door_doorbell", {"state": "off", "attributes": {"friendly_name": "Front Door Doorbell Button", "device_class": "occupancy"}})
# demo Areas (the real ones come from HA's registries, see entity_areas())
_DEMO_AREAS = {"light.driveway": "Driveway", "camera.front_door": "Front Walkway", "camera.backyard": "Patio", "binary_sensor.front_door_doorbell": "Front Walkway", "light.porch": "Porch", "light.kitchen": "Kitchen",
               "light.living_room": "Living", "light.master_bed": "Master Bedroom",
               "media_player.living_room_tv": "Living", "media_player.bedroom_tv": "Master Bedroom",
               "cover.garage": "Garage", "binary_sensor.garage_motion": "Garage"}


_AREA_CACHE = {"at": 0.0, "map": {}}


def entity_areas(max_age: float = 300.0) -> dict:
    """entity_id -> Area name, from HA's area/device/entity registries over the WebSocket
    API (the REST API doesn't expose areas). Cached for 5 min; never raises."""
    import time as _t
    if demo_mode():
        return dict(_DEMO_AREAS)
    if _AREA_CACHE["map"] and _t.time() - _AREA_CACHE["at"] < max_age:
        return _AREA_CACHE["map"]
    if not ha_url() or not ha_token():
        return {}
    import asyncio

    async def _go():
        import websockets
        ws_url = ha_url().replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + "/api/websocket"
        async with websockets.connect(ws_url, max_size=32 * 1024 * 1024, open_timeout=10) as ws:
            await ws.recv()
            await ws.send(json.dumps({"type": "auth", "access_token": ha_token()}))
            if json.loads(await ws.recv()).get("type") != "auth_ok":
                return None
            results = {}
            for i, t in enumerate(("config/area_registry/list", "config/device_registry/list", "config/entity_registry/list"), start=1):
                await ws.send(json.dumps({"id": i, "type": t}))
            while len(results) < 3:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
                if msg.get("id") in (1, 2, 3) and msg.get("type") == "result":
                    results[msg["id"]] = msg.get("result") or []
            areas = {a["area_id"]: a.get("name") or a["area_id"] for a in results[1]}
            dev_area = {d["id"]: d.get("area_id") for d in results[2]}
            out = {}
            for e in results[3]:
                aid = e.get("area_id") or dev_area.get(e.get("device_id"))
                if aid and aid in areas:
                    out[e["entity_id"]] = areas[aid]
            return out

    try:
        m = asyncio.run(_go())
        if m is not None:
            _AREA_CACHE["map"] = m
    except Exception:
        pass
    _AREA_CACHE["at"] = _t.time()      # on failure keep the old map and don't retry for a while
    return _AREA_CACHE["map"]


def _attach_areas(tiles: list) -> list:
    areas = entity_areas()
    for t in tiles:
        a = areas.get(t["entity_id"])
        if a:
            t["area"] = a
    return tiles


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
    if domain == "camera":
        # the browser loads snapshots through FamilyHub (token stays server-side)
        tile["snapshot"] = f"/api/ha/camera/{entity_id}"
        tile["toggleable"] = False
        tile["on"] = False
    return tile


def _states_to_tiles(states) -> list:
    tiles = []
    for s in states:
        eid = s.get("entity_id", "")
        domain = eid.split(".", 1)[0]
        if domain not in DOMAIN_GROUP:
            continue
        attrs = s.get("attributes", {}) or {}
        if _is_spotify(eid, attrs):
            continue          # Spotify gets its own now-playing card, not a TV tile
        if _boring(eid, domain, attrs, s.get("state", "")):
            continue
        tiles.append(_tile(eid, s.get("state", ""), attrs))
    return tiles


# Sensors worth a kitchen-wall tile. Everything else HA exposes (Roku diagnostics,
# sun times, backup bookkeeping, "supports AirPlay", app IDs…) is noise here.
_SENSOR_CLASSES_OK = {"temperature", "humidity", "power", "energy", "pm25", "co2",
                      "carbon_dioxide", "aqi", "illuminance", "moisture", "precipitation"}
_BINARY_CLASSES_OK = {"door", "window", "garage_door", "opening", "motion", "occupancy",
                      "presence", "moisture", "smoke", "gas", "carbon_monoxide", "lock",
                      "safety", "vibration"}
# Alarm.com (and friends) hang a Malfunction / Trouble / Tamper / Low battery / AC failure /
# "Camera not reachable" / Animal-Vehicle-Package-Person detector on EVERY device, plus a
# dozen account-health sensors ("My Surety System …"). Diagnostics, not kitchen-wall material.
# They stay in Home Assistant; the wall only shows them while they're actually firing (see _boring).
_DIAG_WORDS = ("malfunction", "trouble", "tamper", "low battery", "battery count", "ac failure",
               "not reachable", "auto-off", "auto_off", "alarm in memory", "battery charging",
               "critical battery", "animal detected", "vehicle detected", "package detected",
               "person detected", "my surety system", "system (")
_BORING_PREFIX = ("sensor.backup_", "sensor.sun_", "binary_sensor.backup_")
_BORING_WORDS = ("active_app", "supports_", "headphones_connected", "_app_id", "find_remote",
                 "next_dawn", "next_dusk", "next_midnight", "next_noon", "next_rising", "next_setting",
                 "_rssi", "_signal_strength", "_uptime", "_ip_address", "_mac_address", "_ssid", "_bssid",
                 "_last_boot", "_firmware", "_version", "_last_seen", "_linkquality")


def _boring(eid: str, domain: str, attrs: dict, state: str = "") -> bool:
    if domain not in ("sensor", "binary_sensor"):
        return False
    if eid.startswith(_BORING_PREFIX) or any(w in eid for w in _BORING_WORDS):
        return True
    name = str(attrs.get("friendly_name", "") or "").lower()
    if any(w in name for w in _DIAG_WORDS):
        # diagnostics: hidden unless something is wrong right now (then it earns a tile)
        return state in ("off", "unavailable", "unknown", "", "0", "0devices", None)
    dc = str(attrs.get("device_class", "") or "")
    if dc in ("problem", "tamper", "battery", "connectivity", "update", "running") and domain == "binary_sensor":
        return state != "on"
    if domain == "binary_sensor":
        return dc not in _BINARY_CLASSES_OK
    if dc in _SENSOR_CLASSES_OK:
        return False
    if dc == "battery":                                     # only shout when it matters
        try:
            return float(state) > 20
        except (TypeError, ValueError):
            return True
    # unclassified sensor: keep only if it has a measurement unit (a number), drop text/timestamps
    return not attrs.get("unit_of_measurement") or dc in ("timestamp", "date", "enum", "duration")


# ---- Spotify ------------------------------------------------------------------
# HA's Spotify integration exposes media_player.spotify_<account>. We surface it
# as a now-playing card with transport, volume, Spotify Connect device picker and
# the family's pinned playlists (settings.spotifyPlaylists).

def _is_spotify(eid: str, attrs: dict | None = None) -> bool:
    """HA names it media_player.spotify_<account>, but accept any media_player that
    says it's Spotify (name / attribution / picture host) — users rename entities."""
    if not eid.startswith("media_player."):
        return False
    if eid.startswith("media_player.spotify") or "spotify" in eid:
        return True
    a = attrs or {}
    return ("spotify" in str(a.get("attribution", "")).lower()
            or "spotify" in str(a.get("entity_picture", "")).lower()
            or "spotify" in str(a.get("friendly_name", "")).lower())


def _spotify_from_states(states) -> dict | None:
    for st in states:
        eid = st.get("entity_id", "")
        a = st.get("attributes", {}) or {}
        if not _is_spotify(eid, a):
            continue
        return {
            "entity_id": eid, "state": st.get("state", ""),
            "title": a.get("media_title"), "artist": a.get("media_artist"),
            "album": a.get("media_album_name"), "playlist": a.get("media_playlist"),
            "art": f"/api/ha/art?entity_id={eid}" if a.get("entity_picture") else None,
            "volume": a.get("volume_level"), "shuffle": bool(a.get("shuffle")),
            "source": a.get("source"), "sources": a.get("source_list") or [],
        }
    return None


def spotify_state() -> dict | None:
    if demo_mode():
        states = [{"entity_id": eid, "state": v["state"], "attributes": v.get("attributes", {})}
                  for eid, v in _DEMO.items()]
        sp = _spotify_from_states(states)
        if sp:
            sp["demo"] = True
        return sp
    try:
        sp = _spotify_from_states(_request("/api/states") or [])
    except Exception:
        sp = None
    return _merge_own_link(sp)


_last_devs: list = []
_last_devs_at: float = 0.0


def _merge_own_link(sp: dict | None) -> dict | None:
    """If FamilyHub has its own Spotify link, use its live device list (it sees the wall's
    Web Playback speaker, which HA's source_list often lags on) and its now-playing."""
    try:
        from . import spotify_web as sw
        if not sw.linked():
            return sp
        devs = sw.devices()
        # Spotify's device list flickers (empty / partial when nothing is active). Keep the
        # last good list for a couple of minutes so chips don't blink in and out.
        global _last_devs, _last_devs_at
        now = time.time()
        if devs:
            _last_devs, _last_devs_at = devs, now
        elif _last_devs and now - _last_devs_at < 180:
            devs = _last_devs
        if sp is None:
            pb = sw.playback() or {}
            sp = {"entity_id": None, "state": "playing" if pb.get("playing") else ("paused" if pb.get("title") else "idle"),
                  "title": pb.get("title"), "artist": pb.get("artist"), "album": pb.get("album"),
                  "playlist": None, "art": pb.get("art"), "volume": (pb.get("volume") or 50) / 100,
                  "shuffle": bool(pb.get("shuffle")), "source": pb.get("device"), "sources": []}
        names, _seen = [], set()
        for d in devs:                                   # dedupe: a renamed player can be listed twice briefly
            n = d.get("name")
            if n and n.lower() not in _seen:
                _seen.add(n.lower()); names.append(n)
        # the wall's own speaker always first — even if Spotify's device list is momentarily
        # stale (it lags a re-registration by up to a minute)
        wall_name = (sw._load().get("wall_device_name") or "FamilyHub")
        names = [n for n in names if n.lower() != wall_name.lower()]
        names.insert(0, wall_name)
        sp["sources"] = names
        if devs:
            active = next((d for d in devs if d.get("is_active")), None)
            if active:
                sp["source"] = active.get("name")
        sp["own_link"] = True
    except Exception:
        pass
    return sp


_DEMO_BROWSE = {
    None: [("Your playlists", "playlists", False, True), ("Recently played", "recent", False, True),
           ("New releases", "new", False, True)],
    "playlists": [("Dinner Vibes", "spotify:playlist:1", True, False), ("Kids Dance Party", "spotify:playlist:2", True, False),
                  ("Sunday Morning", "spotify:playlist:3", True, False), ("Road Trip", "spotify:playlist:4", True, False)],
    "recent": [("Abbey Road", "spotify:album:1", True, False), ("Come Together", "spotify:track:1", True, False)],
    "new": [("Something New", "spotify:album:2", True, False)],
}


def spotify_browse(content_id: str | None = None, content_type: str | None = None) -> dict:
    """Walk HA's media browser for the Spotify player (its WebSocket API; the REST
    API has no browse). Root = Spotify's top level (Your playlists, Recently played,
    Top tracks, New releases, Categories…)."""
    if demo_mode():
        kids = _DEMO_BROWSE.get(content_id if content_id in _DEMO_BROWSE else None, [])
        return {"title": content_id or "Spotify", "children": [
            {"title": t, "id": i, "type": "playlist" if ":playlist:" in i else "album" if ":album:" in i else "track" if ":track:" in i else "library",
             "can_play": p, "can_expand": e, "thumb": None} for t, i, p, e in kids]}
    sp = spotify_state()
    if not sp:
        return {"title": "Spotify", "children": [], "reason": "no Spotify player in Home Assistant"}
    import asyncio, json

    async def _go():
        import websockets
        ws_url = ha_url().replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + "/api/websocket"
        async with websockets.connect(ws_url, max_size=16 * 1024 * 1024, open_timeout=10) as ws:
            await ws.recv()                                   # auth_required
            await ws.send(json.dumps({"type": "auth", "access_token": ha_token()}))
            if json.loads(await ws.recv()).get("type") != "auth_ok":
                return {"title": "Spotify", "children": [], "reason": "HA token rejected"}
            req = {"id": 1, "type": "media_player/browse_media", "entity_id": sp["entity_id"]}
            if content_id:
                req["media_content_id"] = content_id
                req["media_content_type"] = content_type or "playlist"
            await ws.send(json.dumps(req))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=20))
                if msg.get("id") == 1:
                    if not msg.get("success"):
                        return {"title": "Spotify", "children": [], "reason": (msg.get("error") or {}).get("message", "browse failed")}
                    r = msg.get("result") or {}
                    return {"title": r.get("title") or "Spotify",
                            "children": [{"title": c.get("title"), "id": c.get("media_content_id"),
                                          "type": c.get("media_content_type"), "can_play": bool(c.get("can_play")),
                                          "can_expand": bool(c.get("can_expand")), "thumb": c.get("thumbnail")}
                                         for c in (r.get("children") or [])]}

    try:
        return asyncio.run(_go())
    except Exception as e:
        return {"title": "Spotify", "children": [], "reason": str(e)}


def _own_link_cmd(a: str, value: str, sp: dict):
    """Run a card command through FamilyHub's own Spotify link. Returns a result dict,
    or None to fall through to Home Assistant."""
    try:
        from . import spotify_web as sw
        if not sw.linked():
            return None
        devs = sw.devices()
        by_name = {d.get("name"): d for d in devs}
        active = next((d for d in devs if d.get("is_active")), None)
        if a == "source" and value in by_name:
            sw.transfer(by_name[value]["id"], play_now=sp.get("state") == "playing")
            return {"ok": True}
        if a == "play" and value:
            target = (active or sw.wall_device() or (devs[0] if devs else None))
            did = target.get("id") if target else None
            if value.startswith("spotify:track:"):
                sw.play(did, uris=[value])
            else:
                sw.play(did, context_uri=value)
            return {"ok": True}
        if a == "play_pause":
            if sp.get("state") == "playing":
                sw.pause()
            else:
                target = active or sw.wall_device()
                sw.play(target.get("id") if target else None)
            return {"ok": True}
        if a == "next":
            sw.next_track(); return {"ok": True}
        if a == "prev":
            sw.prev_track(); return {"ok": True}
        if a == "volume":
            sw.set_volume(int(float(value) * 100), active.get("id") if active else None); return {"ok": True}
    except Exception as e:
        return {"ok": False, "reason": str(e)}
    return None


def spotify_cmd(action: str, value: str = "", kind: str = "") -> dict:
    sp = spotify_state()
    if not sp:
        return {"ok": False, "reason": "no Spotify player in Home Assistant"}
    a = (action or "").lower()
    if not demo_mode():
        r = _own_link_cmd(a, value, sp)
        if r is not None:
            return r
    eid = sp.get("entity_id")
    if not eid:
        return {"ok": False, "reason": "no Spotify player in Home Assistant"}
    if demo_mode():
        cur = _DEMO[eid]
        if a == "play_pause":
            cur["state"] = "paused" if cur["state"] == "playing" else "playing"
        elif a in ("next", "prev"):
            cur["attributes"]["media_title"] = {"next": "Something", "prev": "Come Together"}[a]
            cur["state"] = "playing"
        elif a == "volume":
            cur["attributes"]["volume_level"] = max(0.0, min(1.0, float(value or 0.5)))
        elif a == "source":
            cur["attributes"]["source"] = value
        elif a == "play":
            cur["state"] = "playing"
            cur["attributes"]["media_playlist"] = value.split(":")[-1]
        elif a == "shuffle":
            cur["attributes"]["shuffle"] = not cur["attributes"].get("shuffle")
        return {"ok": True, "demo": True}
    if a == "play_pause":
        return call_service("media_player", "media_play_pause", eid)
    if a == "next":
        return call_service("media_player", "media_next_track", eid)
    if a == "prev":
        return call_service("media_player", "media_previous_track", eid)
    if a == "volume":
        try:
            return call_service("media_player", "volume_set", eid, {"volume_level": max(0.0, min(1.0, float(value)))})
        except ValueError:
            return {"ok": False, "reason": "bad volume"}
    if a == "source" and value:
        return call_service("media_player", "select_source", eid, {"source": value})
    if a == "shuffle":
        return call_service("media_player", "shuffle_set", eid, {"shuffle": not sp.get("shuffle")})
    if a == "play" and value:
        if not kind:
            kind = "playlist"
            if ":album:" in value: kind = "album"
            elif ":track:" in value: kind = "track"
            elif ":artist:" in value: kind = "artist"
            elif ":show:" in value: kind = "show"
            elif ":episode:" in value: kind = "episode"
        return call_service("media_player", "play_media", eid,
                            {"media_content_type": kind, "media_content_id": value})
    return {"ok": False, "reason": f"unknown spotify action {action}"}


def entity_picture(entity_id: str):
    """Fetch an entity's picture (album art) through HA with the server-side
    token, so the browser never needs it. Returns (bytes, content_type) or None."""
    if demo_mode() or not entity_id:
        return None
    try:
        st = _request(f"/api/states/{entity_id}") or {}
        pic = (st.get("attributes") or {}).get("entity_picture")
        if not pic:
            return None
        url = pic if pic.startswith("http") else ha_url() + pic
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {ha_token()}"})
        with urllib.request.urlopen(req, timeout=6) as r:
            return r.read(), r.headers.get("Content-Type", "image/jpeg")
    except Exception:
        return None


_SNAP_CACHE: dict = {}


def camera_snapshot(entity_id: str, max_age: float = 4.0):
    """Current still from a camera via HA's camera_proxy, cached a few seconds so a
    phone + wall + 3D pin all refreshing don't hammer a cloud camera. (bytes, ctype) | None.
    Demo mode draws a placeholder SVG."""
    if demo_mode():
        name = (_DEMO.get(entity_id) or {}).get("attributes", {}).get("friendly_name", "Camera")
        hr = time.strftime("%H:%M:%S")
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">'
               f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2b3b55"/><stop offset="1" stop-color="#0f1620"/></linearGradient></defs>'
               f'<rect width="640" height="360" fill="url(#g)"/><circle cx="520" cy="80" r="26" fill="#f1e6c8" opacity=".8"/>'
               f'<rect x="0" y="260" width="640" height="100" fill="#1a2330"/><rect x="200" y="150" width="240" height="110" rx="6" fill="#39485f"/>'
               f'<text x="20" y="340" font-family="sans-serif" font-size="20" fill="#dfe3ea">{name} · demo · {hr}</text></svg>')
        return svg.encode(), "image/svg+xml"
    if not entity_id:
        return None
    c = _SNAP_CACHE.get(entity_id)
    if c and time.time() - c[0] < max_age:
        return c[1], c[2]
    try:
        req = urllib.request.Request(ha_url().rstrip("/") + f"/api/camera_proxy/{entity_id}",
                                     headers={"Authorization": f"Bearer {ha_token()}"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data, ctype = r.read(), r.headers.get("Content-Type", "image/jpeg")
        _SNAP_CACHE[entity_id] = (time.time(), data, ctype)
        return data, ctype
    except Exception:
        return (c[1], c[2]) if c else None


def camera_webrtc_config(entity_id: str):
    """Short-lived WebRTC credentials for an Alarm.com camera, via the ibasebcast
    ha-alarmdotcom integration's websocket command. The browser then talks to
    Alarm.com's streaming servers directly (no video flows through FamilyHub).
    Returns the config dict, or None when the camera/integration can't stream."""
    if demo_mode() or not entity_id or not entity_id.startswith("camera."):
        return None
    import asyncio

    async def _go():
        import websockets
        ws_url = ha_url().replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + "/api/websocket"
        async with websockets.connect(ws_url, max_size=4 * 1024 * 1024, open_timeout=10) as ws:
            await ws.recv()
            await ws.send(json.dumps({"type": "auth", "access_token": ha_token()}))
            if json.loads(await ws.recv()).get("type") != "auth_ok":
                return None
            await ws.send(json.dumps({"id": 1, "type": "alarmdotcom/webrtc_config", "entity_id": entity_id}))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=25))
                if msg.get("id") == 1:
                    return msg.get("result") if msg.get("success") else None

    try:
        return asyncio.run(_go())
    except Exception:
        return None


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
        tiles = _name_garage(_attach_areas(_states_to_tiles(states)))
        sp = _spotify_from_states(states)
        if sp: sp["demo"] = True
        return {"connected": True, "demo": True,
                "groups": _grouped(tiles), "count": len(tiles), "spotify": sp}
    try:
        from . import ha_live
        states = ha_live.states()          # instant, from the WebSocket mirror
        live = states is not None
        if states is None:
            states = _request("/api/states")
        tiles = _name_garage(_attach_areas(_states_to_tiles(states or [])))
        return {"connected": True, "demo": False, "live": live,
                "groups": _grouped(tiles), "count": len(tiles),
                "spotify": _spotify_from_states(states or [])}
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
        try:
            from . import ha_live
            ha_live.bump()                 # so the wall's live stream refreshes in demo too
        except Exception:
            pass
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


def media(entity_id: str, action: str, value: str = "") -> dict:
    """TV / media control for the on-screen Roku remote. `entity_id` is the
    media_player entity shown on the tile. Power/volume/app route through
    media_player services; navigation keys (dpad/back/home) go through the Roku
    integration's matching `remote.<name>` entity (HA names it the same)."""
    if "." not in entity_id:
        return {"ok": False, "reason": "bad entity"}
    name = entity_id.split(".", 1)[1]
    remote_eid = "remote." + name
    a = (action or "").lower()
    if a == "power":
        return call_service("media_player", "toggle", entity_id)
    if a == "vol_up":
        return call_service("media_player", "volume_up", entity_id)
    if a == "vol_down":
        return call_service("media_player", "volume_down", entity_id)
    if a == "mute":
        return call_service("media_player", "volume_mute", entity_id, {"is_volume_muted": True})
    if a == "play_pause":
        return call_service("media_player", "media_play_pause", entity_id)
    if a == "app" and value:
        return call_service("media_player", "select_source", entity_id, {"source": value})
    navmap = {"up": "up", "down": "down", "left": "left", "right": "right",
              "ok": "select", "back": "back", "home": "home",
              "info": "info", "replay": "instantreplay",
              "rewind": "reverse", "forward": "forward"}
    if a in navmap:
        return call_service("remote", "send_command", remote_eid, {"command": navmap[a]})
    return {"ok": False, "reason": f"unknown media action {action}"}


# A believable set of installed channels for the demo TV.
_DEMO_APPS = ["Live TV", "Netflix", "YouTube", "Hulu", "Disney+", "Prime Video",
              "Max", "Spotify", "Plex", "YouTube TV", "Peacock", "Apple TV"]


def media_info(entity_id: str) -> dict:
    """What's installed / playing on a TV, for the on-screen remote:
    the real channel (app) list, the current source, power + mute state."""
    if demo_mode():
        cur = _DEMO.get(entity_id) or {}
        return {"state": cur.get("state", "off"), "source": None,
                "sources": _DEMO_APPS, "volume": None, "muted": False, "demo": True}
    try:
        s = _request(f"/api/states/{entity_id}") or {}
        attrs = s.get("attributes", {}) or {}
        return {"state": s.get("state", ""), "source": attrs.get("source"),
                "sources": attrs.get("source_list") or [],
                "volume": attrs.get("volume_level"),
                "muted": bool(attrs.get("is_volume_muted")), "demo": False}
    except Exception:
        return {"state": "", "source": None, "sources": [], "volume": None,
                "muted": False, "reason": "can't reach Home Assistant"}


_GARAGE = re.compile(r"garage", re.I)


def has_garage_cover(tiles) -> bool:
    return any(t["domain"] == "cover" and _GARAGE.search(t["name"] or "") for t in tiles)


def opening_label(t, garage_cover: bool) -> str | None:
    """What to call an open door/window sensor, or None to leave it out.
    Alarm.com often names the contact on the house->garage door "Garage Door". When the real
    garage door is a cover (MyQ), that cover is the garage door; the contact is the door INTO
    the garage. A garage_door-class contact that just mirrors the cover is dropped as a duplicate."""
    name = t["name"] or ""
    dc = t.get("device_class")
    if garage_cover and _GARAGE.search(name):
        if dc == "garage_door":
            return None
        return "Door to garage"
    return name


def _name_garage(tiles: list) -> list:
    """Home-tab tiles: once a garage cover exists, the contact Alarm.com calls "Garage Door" is
    shown as "Door to garage", and a garage_door-class contact that duplicates the cover is hidden."""
    if not has_garage_cover(tiles):
        return tiles
    out = []
    for t in tiles:
        if t["domain"] == "binary_sensor" and _GARAGE.search(t["name"] or "") and t.get("device_class") in ("door", "garage_door", "window", "opening"):
            lbl = opening_label(t, True)
            if not lbl:
                continue
            t = {**t, "name": lbl, "ha_name": t["name"]}
        out.append(t)
    return out


def status() -> dict:
    """Light-weight status for the calendar's top bar: connected? alarm state?
    open doors/garage? a couple of temperatures?"""
    home = get_home()
    alarm, open_doors, temps = None, [], []
    tiles = [t for grp in home.get("groups", []) for t in grp["tiles"]]
    gcover = has_garage_cover(tiles)
    for grp in home.get("groups", []):
        for t in grp["tiles"]:
            if t["domain"] == "alarm_control_panel":
                alarm = t["state"]
            if t["domain"] == "binary_sensor" and t.get("device_class") in ("door", "garage_door", "window", "opening") and t["on"]:
                lbl = opening_label(t, gcover)
                if lbl and lbl not in open_doors:
                    open_doors.append(lbl)
            if t["domain"] == "cover" and t["state"] in ("open", "opening"):
                open_doors.append("Garage door" if _GARAGE.search(t["name"] or "") else t["name"])
            if t["domain"] == "sensor" and t.get("device_class") == "temperature":
                try:
                    temps.append({"name": t["name"], "value": round(float(t["state"])),
                                  "unit": t.get("unit") or "°"})
                except (ValueError, TypeError):
                    pass
    return {"connected": home.get("connected"), "demo": home.get("demo"),
            "alarm": alarm, "open_doors": open_doors, "temps": temps[:3],
            "reason": home.get("reason")}
