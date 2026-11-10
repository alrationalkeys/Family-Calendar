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
        "media_player.spotify_family": {"state": "playing",
            "attributes": {"friendly_name": "Spotify", "media_title": "Here Comes the Sun",
                           "media_artist": "The Beatles", "media_album_name": "Abbey Road",
                           "volume_level": 0.45, "shuffle": False, "source": "Kitchen Wall",
                           "source_list": ["Kitchen Wall", "Living Room TV", "Bedroom TV", "Alex's iPhone"],
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
        attrs = s.get("attributes", {}) or {}
        if _is_spotify(eid, attrs):
            continue          # Spotify gets its own now-playing card, not a TV tile
        if eid.startswith("sensor.backup_"):
            continue          # HA's own backup bookkeeping isn't a household sensor
        tiles.append(_tile(eid, s.get("state", ""), attrs))
    return tiles


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
        return _spotify_from_states(_request("/api/states") or [])
    except Exception:
        return None


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


def spotify_cmd(action: str, value: str = "", kind: str = "") -> dict:
    sp = spotify_state()
    if not sp:
        return {"ok": False, "reason": "no Spotify player in Home Assistant"}
    eid = sp["entity_id"]
    a = (action or "").lower()
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
        tiles = _states_to_tiles(states or [])
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


def status() -> dict:
    """Light-weight status for the calendar's top bar: connected? alarm state?
    open doors/garage? a couple of temperatures?"""
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
            if t["domain"] == "sensor" and t.get("device_class") == "temperature":
                try:
                    temps.append({"name": t["name"], "value": round(float(t["state"])),
                                  "unit": t.get("unit") or "°"})
                except (ValueError, TypeError):
                    pass
    return {"connected": home.get("connected"), "demo": home.get("demo"),
            "alarm": alarm, "open_doors": open_doors, "temps": temps[:3],
            "reason": home.get("reason")}
