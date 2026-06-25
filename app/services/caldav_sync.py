"""
CalDAV sync — this is the iCloud path (also works for Fastmail, Nextcloud, etc).

iCloud setup:
  1. Go to appleid.apple.com -> Sign-In & Security -> App-Specific Passwords.
  2. Generate one for "FamilyHub". Use it (NOT your real Apple password) below.
  3. CalDAV URL for iCloud: https://caldav.icloud.com/

Requires: pip install caldav icalendar
"""
from datetime import datetime, timedelta
from typing import List, Dict

try:
    import caldav
except ImportError:
    caldav = None


def fetch_caldav_events(url: str, username: str, password: str,
                        days_ahead: int = 30, days_back: int = 0) -> List[Dict]:
    """Return normalized events from a CalDAV server."""
    if caldav is None:
        raise RuntimeError("pip install caldav icalendar")

    client = caldav.DAVClient(url=url, username=username, password=password)
    principal = client.principal()
    base = datetime.now()
    start = base - timedelta(days=days_back)
    end = base + timedelta(days=days_ahead)

    events: List[Dict] = []
    for cal in principal.calendars():
        try:
            results = cal.search(start=start, end=end, event=True, expand=True)
        except Exception:
            continue
        for ev in results:
            comp = ev.icalendar_component
            dtstart = comp.get("dtstart")
            dtend = comp.get("dtend")
            events.append({
                "id": str(comp.get("uid", "")),
                "title": str(comp.get("summary", "(no title)")),
                "start": dtstart.dt.isoformat() if dtstart else None,
                "end": dtend.dt.isoformat() if dtend else None,
                "source": "icloud",
                "all_day": _is_all_day(dtstart.dt) if dtstart else False,
            })
    return events


def _is_all_day(dt) -> bool:
    return not hasattr(dt, "hour")


def create_caldav_event(url, username, password, title, start_iso, end_iso,
                        calendar_name=None):
    """Create an event on a CalDAV calendar (iCloud write-back)."""
    if caldav is None:
        raise RuntimeError("pip install caldav icalendar")
    import uuid
    from datetime import datetime
    client = caldav.DAVClient(url=url, username=username, password=password)
    principal = client.principal()
    cals = principal.calendars()
    cal = cals[0]
    if calendar_name:
        for c in cals:
            if calendar_name.lower() in (c.name or "").lower():
                cal = c; break
    uid = str(uuid.uuid4())
    dt_start = datetime.fromisoformat(start_iso).strftime("%Y%m%dT%H%M%S")
    dt_end = datetime.fromisoformat(end_iso).strftime("%Y%m%dT%H%M%S")
    ical = (
        "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//FamilyHub//EN\n"
        f"BEGIN:VEVENT\nUID:{uid}\nDTSTART:{dt_start}\nDTEND:{dt_end}\n"
        f"SUMMARY:{title}\nEND:VEVENT\nEND:VCALENDAR"
    )
    cal.save_event(ical)
    return {"uid": uid}


def _find_event(principal, uid):
    """Locate a CalDAV event object by its UID across calendars."""
    for cal in principal.calendars():
        try:
            ev = cal.event_by_uid(uid)
            if ev:
                return ev
        except Exception:
            continue
    return None


def update_caldav_event(url, username, password, uid, title=None,
                        start_iso=None, end_iso=None):
    """Edit an existing iCloud/CalDAV event by UID."""
    if caldav is None:
        raise RuntimeError("pip install caldav icalendar")
    from datetime import datetime
    client = caldav.DAVClient(url=url, username=username, password=password)
    ev = _find_event(client.principal(), uid)
    if not ev:
        return {"error": "event not found", "uid": uid}
    comp = ev.icalendar_component
    if title is not None:
        comp["summary"] = title
    if start_iso:
        comp["dtstart"].dt = datetime.fromisoformat(start_iso)
    if end_iso:
        comp["dtend"].dt = datetime.fromisoformat(end_iso)
    ev.save()
    return {"uid": uid, "updated": True}


def delete_caldav_event(url, username, password, uid):
    """Delete an iCloud/CalDAV event by UID."""
    if caldav is None:
        raise RuntimeError("pip install caldav icalendar")
    client = caldav.DAVClient(url=url, username=username, password=password)
    ev = _find_event(client.principal(), uid)
    if not ev:
        return {"error": "event not found", "uid": uid}
    ev.delete()
    return {"uid": uid, "deleted": True}
