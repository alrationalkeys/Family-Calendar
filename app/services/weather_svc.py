"""
Weather for the wall header. Uses Open-Meteo (free, no API key, no signup).
Defaults to Socastee, SC area; override lat/lon in settings later if desired.
"""
import urllib.request
import json

# Grand Strand / Socastee SC default
DEFAULT_LAT = 33.69
DEFAULT_LON = -79.01

CODE = {
    0: ("Clear", "\u2600\ufe0f"), 1: ("Mostly clear", "\U0001F324\ufe0f"),
    2: ("Partly cloudy", "\u26C5"), 3: ("Cloudy", "\u2601\ufe0f"),
    45: ("Fog", "\U0001F32B\ufe0f"), 48: ("Fog", "\U0001F32B\ufe0f"),
    51: ("Drizzle", "\U0001F327\ufe0f"), 61: ("Rain", "\U0001F327\ufe0f"),
    63: ("Rain", "\U0001F327\ufe0f"), 65: ("Heavy rain", "\U0001F327\ufe0f"),
    71: ("Snow", "\u2744\ufe0f"), 73: ("Snow", "\u2744\ufe0f"), 75: ("Snow", "\u2744\ufe0f"),
    80: ("Showers", "\U0001F326\ufe0f"), 81: ("Showers", "\U0001F326\ufe0f"),
    82: ("Heavy showers", "\u26C8\ufe0f"), 95: ("Thunderstorm", "\u26C8\ufe0f"),
    96: ("Thunderstorm", "\u26C8\ufe0f"), 99: ("Thunderstorm", "\u26C8\ufe0f"),
}


def get_weather(lat=DEFAULT_LAT, lon=DEFAULT_LON):
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&current=temperature_2m,weather_code"
           "&daily=temperature_2m_max,temperature_2m_min,weather_code,sunrise,sunset"
           "&temperature_unit=fahrenheit&timezone=auto&forecast_days=1")
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            data = json.loads(r.read())
        cur = data["current"]
        daily = data["daily"]
        code = cur["weather_code"]
        desc, icon = CODE.get(code, ("", "\U0001F321\ufe0f"))
        return {
            "temp": round(cur["temperature_2m"]),
            "code": code,                 # raw WMO weather code -> drives live weather effects
            "desc": desc, "icon": icon,
            "high": round(daily["temperature_2m_max"][0]),
            "low": round(daily["temperature_2m_min"][0]),
            # local ISO times, e.g. "2026-10-07T07:12" \u2014 used by the day/night hero banner
            "sunrise": (daily.get("sunrise") or [None])[0],
            "sunset": (daily.get("sunset") or [None])[0],
        }
    except Exception as e:
        return {"error": str(e)}


def get_forecast(lat=DEFAULT_LAT, lon=DEFAULT_LON, days=7):
    """Multi-day forecast keyed by date -> {high, low, desc, icon}.
    Used to show per-day weather on the week/day calendar views."""
    days = max(1, min(days, 16))
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           "&daily=temperature_2m_max,temperature_2m_min,weather_code"
           f"&temperature_unit=fahrenheit&timezone=auto&forecast_days={days}")
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            data = json.loads(r.read())
        daily = data["daily"]
        out = {}
        for i, day in enumerate(daily["time"]):
            code = daily["weather_code"][i]
            desc, icon = CODE.get(code, ("", "\U0001F321️"))
            out[day] = {
                "high": round(daily["temperature_2m_max"][i]),
                "low": round(daily["temperature_2m_min"][i]),
                "desc": desc, "icon": icon,
            }
        return {"days": out}
    except Exception as e:
        return {"error": str(e), "days": {}}
