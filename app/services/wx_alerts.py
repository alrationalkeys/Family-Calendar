"""
Storm alerts + rain check.

  alerts()   National Weather Service warnings/watches/advisories for the house's point (api.weather.gov, free,
             no key). Cached 5 min. Severe/Extreme (and any hurricane / tropical storm / tornado / flood item)
             push once to the phones and put a banner on the wall; Moderate ones only show on the wall.
             Hurricane + tropical storm items carry a prep checklist.
  rain_tick  every 15 min: rain likely (>= 60%) in the next 2 hours and the garage / a window or door is open
             -> one push (at most every 6 h).

Settings: wxAlerts (bool), rainCheck (bool). Location = the weather default (Socastee area).
"""
from __future__ import annotations

import json
import time
import urllib.request

from . import weather_svc

_UA = {"User-Agent": "FamilyHub home display", "Accept": "application/geo+json"}
_CACHE = {"at": 0.0, "data": []}
_PUSHED: dict = {}          # alert id -> time pushed
_RAIN = {"at": 0.0, "pushed": 0.0}
_BIG = ("hurricane", "tropical storm", "tornado", "flood", "storm surge", "extreme wind", "severe thunderstorm")

CHECKLIST = {
    "hurricane": ["Bring in porch and patio furniture, cushions, decorations",
                  "Charge phones, power banks; check flashlights and batteries",
                  "Fill the cars with gas; get cash",
                  "Water (1 gal/person/day for 3+ days) and dog food + meds for the dogs",
                  "Prescriptions filled; important papers in a waterproof bag",
                  "Know your evacuation zone (Horry County: knowyourzone.sc.gov)",
                  "Freezer to coldest setting; fill spare containers with water",
                  "Close the garage; move the cars if flooding is expected"],
}
CHECKLIST["tropical storm"] = CHECKLIST["hurricane"][:4]


def _get(url: str, timeout: float = 8):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def alerts(force: bool = False) -> list:
    if not force and time.time() - _CACHE["at"] < 300:
        return _CACHE["data"]
    lat, lon = weather_svc.DEFAULT_LAT, weather_svc.DEFAULT_LON
    try:
        j = _get(f"https://api.weather.gov/alerts/active?point={lat},{lon}")
        out = []
        for f in j.get("features", []):
            p = f.get("properties") or {}
            ev = p.get("event") or "Weather alert"
            sev = p.get("severity") or "Unknown"
            if sev in ("Minor", "Unknown") and not any(b in ev.lower() for b in _BIG):
                continue
            big = sev in ("Severe", "Extreme") or any(b in ev.lower() for b in _BIG)
            kind = next((k for k in CHECKLIST if k in ev.lower()), None)
            out.append({"id": p.get("id") or f.get("id"), "event": ev, "severity": sev, "big": big,
                        "headline": p.get("headline") or ev, "expires": p.get("ends") or p.get("expires"),
                        "description": (p.get("description") or "")[:1500], "instruction": (p.get("instruction") or "")[:800],
                        "checklist": CHECKLIST.get(kind, [])})
        out.sort(key=lambda a: (not a["big"], a["event"]))
        _CACHE.update(at=time.time(), data=out)
    except Exception:
        _CACHE["at"] = time.time() - 240          # retry in a minute, keep the last list
    return _CACHE["data"]


def tick(push, settings: dict):
    """From the house-watch loop (every minute). push(text, tag)."""
    if settings.get("wxAlerts", True) is False:
        return
    for a in alerts():
        if not a["big"] or a["id"] in _PUSHED:
            continue
        _PUSHED[a["id"]] = time.time()
        extra = " Prep checklist is on the wall." if a["checklist"] else ""
        push(f"⚠️ {a['event']}: {a['headline']}.{extra}", "familyhub-weather")
        try:
            from datetime import datetime
            from ..db import get_db
            with get_db() as conn:
                conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                             (f"⚠️ {a['event']}", a["headline"], "weather", datetime.now().isoformat()))
        except Exception:
            pass
    for k, t in list(_PUSHED.items()):
        if time.time() - t > 4 * 86400:
            _PUSHED.pop(k, None)


def rain_soon(hours: int = 2) -> dict | None:
    """{'pct': 70, 'at': '3 PM'} when rain is likely in the next `hours`, else None."""
    lat, lon = weather_svc.DEFAULT_LAT, weather_svc.DEFAULT_LON
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&hourly=precipitation_probability&forecast_hours={hours + 1}&timezone=auto")
    with urllib.request.urlopen(url, timeout=6) as r:
        j = json.loads(r.read())
    h = j.get("hourly") or {}
    for t, p in zip(h.get("time", [])[1:], (h.get("precipitation_probability") or [])[1:]):
        if p is not None and p >= 60:
            hr = int(t[11:13])
            return {"pct": p, "at": f"{(hr % 12) or 12} {'AM' if hr < 12 else 'PM'}"}
    return None


def rain_tick(push, settings: dict, open_things):
    if settings.get("rainCheck", True) is False or time.time() - _RAIN["at"] < 900:
        return
    _RAIN["at"] = time.time()
    if time.time() - _RAIN["pushed"] < 6 * 3600:
        return
    opened = open_things()
    if not opened:
        return
    try:
        r = rain_soon()
    except Exception:
        return
    if r:
        _RAIN["pushed"] = time.time()
        push(f"🌧 Rain likely around {r['at']} ({r['pct']}%) and {', '.join(opened)} "
             f"{'is' if len(opened) == 1 else 'are'} open.", "familyhub-rain")
