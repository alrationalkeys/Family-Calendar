"""Drive times for the leave-by countdown.

For each upcoming timed event with a location, work out how long the drive is from home and
when to leave. Two sources, best first:

  1. Home Assistant's Waze Travel Time integration (free, live traffic). Needs the integration
     added once in HA (Settings -> Devices & services -> Add -> Waze Travel Time, any route);
     we then call its `waze_travel_time.get_travel_times` action with our own origin/destination.
  1b. TomTom Routing (live traffic, free tier 2,500 requests/day) when TOMTOM_API_KEY is in .env.
     Used when Waze isn't set up or fails (Waze's integration broke in early Nov 2026).
  2. Fallback with no traffic: OpenStreetMap's Nominatim to find the place + the public OSRM
     router for the drive. Both free, no key. A generic User-Agent, nothing personal sent.

Origin = settings.homeAddress, else Home Assistant's home coordinates, else the weather default.
Results are cached 10 minutes per destination (traffic changes slowly; keeps us polite to the
free services).
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from . import ha_svc

UA = "FamilyHub/1.0 (self-hosted family calendar)"
_cache: dict[str, tuple[float, dict]] = {}
_geo: dict[str, tuple[float, float] | None] = {}
TTL = 600


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def _home_coords() -> tuple[float, float]:
    if not ha_svc.demo_mode():
        try:
            cfg = ha_svc._request("/api/config") or {}
            if cfg.get("latitude") is not None:
                return float(cfg["latitude"]), float(cfg["longitude"])
        except Exception:
            pass
    from .weather_svc import DEFAULT_LAT, DEFAULT_LON
    return DEFAULT_LAT, DEFAULT_LON


def origin() -> str:
    addr = (_settings().get("homeAddress") or "").strip()
    if addr:
        return addr
    lat, lon = _home_coords()
    return f"{lat},{lon}"


def _get_json(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _coords(place: str) -> tuple[float, float] | None:
    """lat,lon string -> coords; anything else -> Nominatim (cached for the process)."""
    p = place.strip()
    try:
        a, b = [float(x) for x in p.split(",")]
        return a, b
    except ValueError:
        pass
    if p in _geo:
        return _geo[p]
    try:
        res = _get_json("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": p, "format": "json", "limit": 1}))
        _geo[p] = (float(res[0]["lat"]), float(res[0]["lon"])) if res else None
    except Exception:
        return None                                    # network hiccup: don't cache the miss
    return _geo[p]


def _waze(orig: str, dest: str) -> float | None:
    if ha_svc.demo_mode():
        return None
    try:
        res = ha_svc._request("/api/services/waze_travel_time/get_travel_times?return_response", method="POST",
                              payload={"origin": orig, "destination": dest, "region": "us", "units": "imperial",
                                       "vehicle_type": "car", "realtime": True}, timeout=12)
        routes = ((res or {}).get("service_response") or {}).get("routes") or []
        mins = [float(r["duration"]) for r in routes if r.get("duration") is not None]
        return min(mins) if mins else None
    except Exception:
        return None


def _tomtom(orig: str, dest: str) -> float | None:
    import os
    key = os.getenv("TOMTOM_API_KEY", "").strip()
    if not key:
        return None
    a, b = _coords(orig), _coords(dest)
    if not a or not b:
        return None
    try:
        url = (f"https://api.tomtom.com/routing/1/calculateRoute/{a[0]},{a[1]}:{b[0]},{b[1]}/json?"
               + urllib.parse.urlencode({"key": key, "traffic": "true", "travelMode": "car", "routeType": "fastest"}))
        res = _get_json(url)
        return float(res["routes"][0]["summary"]["travelTimeInSeconds"]) / 60.0
    except Exception:
        return None


def _osrm(orig: str, dest: str) -> float | None:
    a, b = _coords(orig), _coords(dest)
    if not a or not b:
        return None
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}?overview=false"
        res = _get_json(url)
        return float(res["routes"][0]["duration"]) / 60.0
    except Exception:
        return None


def drive(dest: str) -> dict | None:
    """{minutes, traffic: bool, source} for a drive from home to `dest`, or None if unknown."""
    key = dest.strip().lower()
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    orig = origin()
    m = _waze(orig, dest)
    out = {"minutes": round(m), "traffic": True, "source": "waze"} if m is not None else None
    if out is None:
        m = _tomtom(orig, dest)
        out = {"minutes": round(m), "traffic": True, "source": "tomtom"} if m is not None else None
    if out is None:
        m = _osrm(orig, dest)
        out = {"minutes": round(m * 1.1), "traffic": False, "source": "osrm"} if m is not None else None   # +10%: no live traffic
    if out is not None:
        _cache[key] = (time.time(), out)
    else:
        _cache[key] = (time.time() - TTL + 180, None)     # unknown place / services down: retry in 3 min, not every poll
    return out
