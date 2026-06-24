"""
Holiday presets. Four selectable sets, each toggled in settings:
  us_federal   — official US federal holidays (via `holidays` lib)
  christian    — Christmas, Easter, Good Friday, Ash Wednesday, etc.
  jewish       — Hanukkah, Passover, Rosh Hashanah, Yom Kippur (major ones)
  observances  — fun family days: Valentine's, Halloween, Mother's/Father's Day, etc.

Returns all-day events shaped like calendar events so they merge into the views.
Each set carries its own color so they're visually distinct.
"""
from datetime import date
import datetime as dt

try:
    import holidays as _holidays
except ImportError:
    _holidays = None

COLORS = {
    "us_federal": "#4f86c6",
    "christian": "#9a6fd0",
    "jewish": "#3db5c9",
    "observances": "#e0843d",
}


def _evt(name, d, source):
    return {"title": name, "start": d.isoformat(), "end": d.isoformat(),
            "all_day": True, "source": "holiday", "color": COLORS[source]}


def _nth_weekday(year, month, weekday, n):
    """nth (1-based) weekday in a month; n=-1 for last."""
    d = dt.date(year, month, 1)
    days = [d + dt.timedelta(i) for i in range(31) if (d + dt.timedelta(i)).month == month]
    matches = [x for x in days if x.weekday() == weekday]
    return matches[n-1] if n > 0 else matches[n]


def _easter(year):
    """Anonymous Gregorian algorithm."""
    a = year % 19; b = year // 100; c = year % 100
    d = b // 4; e = b % 4; f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19*a + b - d - g + 15) % 30; i = c // 4; k = c % 4
    l = (32 + 2*e + 2*i - h - k) % 7; m = (a + 11*h + 22*l) // 451
    month = (h + l - 7*m + 114) // 31; day = ((h + l - 7*m + 114) % 31) + 1
    return dt.date(year, month, day)


def get_holidays(sets, start: date, end: date):
    out = []
    years = range(start.year, end.year + 1)

    if sets.get("us_federal") and _holidays:
        for d, name in _holidays.US(years=list(years)).items():
            out.append(_evt(name, d, "us_federal"))

    if sets.get("christian"):
        for y in years:
            easter = _easter(y)
            items = {
                "Christmas": dt.date(y, 12, 25),
                "Christmas Eve": dt.date(y, 12, 24),
                "Easter": easter,
                "Good Friday": easter - dt.timedelta(2),
                "Ash Wednesday": easter - dt.timedelta(46),
                "Palm Sunday": easter - dt.timedelta(7),
            }
            for n, d in items.items():
                out.append(_evt(n, d, "christian"))

    if sets.get("jewish"):
        # Approximate fixed-ish anchors for major holidays (Gregorian drift exists;
        # for exact dates, wire a Hebrew-calendar lib later). Good enough for a
        # family wall display heads-up.
        approx = {
            2026: {"Passover (1st night)": (4, 1), "Rosh Hashanah": (9, 11),
                   "Yom Kippur": (9, 20), "Hanukkah (1st night)": (12, 4)},
            2027: {"Passover (1st night)": (4, 21), "Rosh Hashanah": (10, 1),
                   "Yom Kippur": (10, 10), "Hanukkah (1st night)": (12, 24)},
        }
        for y in years:
            for n, (mo, da) in approx.get(y, {}).items():
                out.append(_evt(n, dt.date(y, mo, da), "jewish"))

    if sets.get("observances"):
        for y in years:
            items = {
                "Valentine's Day": dt.date(y, 2, 14),
                "St. Patrick's Day": dt.date(y, 3, 17),
                "Mother's Day": _nth_weekday(y, 5, 6, 2),   # 2nd Sunday May
                "Father's Day": _nth_weekday(y, 6, 6, 3),   # 3rd Sunday June
                "Halloween": dt.date(y, 10, 31),
                "New Year's Eve": dt.date(y, 12, 31),
            }
            for n, d in items.items():
                out.append(_evt(n, d, "observances"))

    return [e for e in out if start <= dt.date.fromisoformat(e["start"]) <= end]
