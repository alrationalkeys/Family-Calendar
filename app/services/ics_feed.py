"""
External ICS calendar feeds. Subscribe to any public .ics URL — sports team
schedules, golf league tee times, school calendars, trash pickup, etc. Many sites
and apps publish an ICS/webcal link; paste it in as a source and it shows on the wall.

Pure stdlib parse (no heavy deps) covering the common VEVENT fields. Add a feed via
/api/sources/ics with {label, url, color}.
"""
import urllib.request
import datetime as dt


def _unfold(text):
    """RFC 5545 line unfolding: a line beginning with a space or tab is a
    continuation of the previous one. Publishers fold any line past ~75 chars,
    so without this long SUMMARYs (and other fields) get truncated."""
    lines = []
    for raw in text.splitlines():
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw.rstrip("\r"))
    return lines


def _split_prop(line):
    """Split an ICS content line into (NAME, params_str, value).
    e.g. 'DTSTART;TZID=America/New_York:20260701T190000' ->
         ('DTSTART', 'TZID=America/New_York', '20260701T190000')"""
    name_params, _, value = line.partition(":")
    name, _, params = name_params.partition(";")
    return name.upper(), params, value.strip()


def _unescape(text):
    """Decode RFC 5545 TEXT escapes: \\n \\, \\; \\\\ ."""
    return (text.replace("\\n", "\n").replace("\\N", "\n")
                .replace("\\,", ",").replace("\\;", ";")
                .replace("\\\\", "\\"))


def _parse_dt(value, params):
    """Parse a DTSTART/DTEND value. Returns (datetime, all_day).
    A trailing 'Z' means UTC -> converted to naive local so it lines up with
    the rest of the (naive, local) calendar. VALUE=DATE or an 8-digit value
    is an all-day date."""
    all_day = "VALUE=DATE" in params and "DATE-TIME" not in params
    if value.endswith("Z"):
        try:
            utc = dt.datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
            return utc.astimezone().replace(tzinfo=None), all_day
        except ValueError:
            pass
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            parsed = dt.datetime.strptime(value, fmt)
            return parsed, all_day or fmt == "%Y%m%d"
        except ValueError:
            continue
    return None, all_day


def fetch_ics_events(url, days_ahead=30, label="feed", color=None):
    req = urllib.request.Request(url.replace("webcal://", "https://"),
                                 headers={"User-Agent": "FamilyHub/1.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        text = r.read().decode("utf-8", "ignore")

    now = dt.datetime.now()
    end = now + dt.timedelta(days=days_ahead)
    events, cur = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT" and cur is not None:
            s = cur.get("start")
            if s and now - dt.timedelta(days=1) <= s <= end:
                events.append({
                    "title": cur.get("summary", label),
                    "start": s.isoformat(),
                    "end": cur["end"].isoformat() if cur.get("end") else s.isoformat(),
                    "all_day": cur.get("all_day", False),
                    "source": "ics",
                    "color": color or "#3db5c9",
                })
            cur = None
        elif cur is not None:
            name, params, value = _split_prop(line)
            if name == "SUMMARY":
                cur["summary"] = _unescape(value)
            elif name == "DTSTART":
                cur["start"], cur["all_day"] = _parse_dt(value, params)
            elif name == "DTEND":
                cur["end"], _ = _parse_dt(value, params)
    return events
