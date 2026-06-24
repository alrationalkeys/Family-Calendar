"""
External ICS calendar feeds. Subscribe to any public .ics URL — sports team
schedules, golf league tee times, school calendars, trash pickup, etc. Many sites
and apps publish an ICS/webcal link; paste it in as a source and it shows on the wall.

Pure stdlib parse (no heavy deps) covering the common VEVENT fields. Add a feed via
/api/sources/ics with {label, url, color}.
"""
import urllib.request
import datetime as dt


def _parse_dt(val):
    val = val.split(":")[-1].strip()
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%d"):
        try:
            return dt.datetime.strptime(val, fmt)
        except ValueError:
            continue
    return None


def fetch_ics_events(url, days_ahead=30, label="feed", color=None):
    req = urllib.request.Request(url.replace("webcal://", "https://"),
                                 headers={"User-Agent": "FamilyHub/1.0"})
    with urllib.request.urlopen(req, timeout=8) as r:
        text = r.read().decode("utf-8", "ignore")

    now = dt.datetime.now()
    end = now + dt.timedelta(days=days_ahead)
    events, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
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
            if line.startswith("SUMMARY"):
                cur["summary"] = line.split(":", 1)[-1]
            elif line.startswith("DTSTART"):
                cur["start"] = _parse_dt(line)
                cur["all_day"] = "VALUE=DATE" in line and "T" not in line
            elif line.startswith("DTEND"):
                cur["end"] = _parse_dt(line)
    return events
