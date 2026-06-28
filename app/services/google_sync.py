"""
Google Calendar sync via the official API.

Setup:
  1. console.cloud.google.com -> new project -> enable "Google Calendar API".
  2. Create OAuth client (Desktop). Download credentials.json.
  3. First run does the OAuth dance and caches token.json. On a headless Pi,
     run the auth step once on your desktop and copy token.json over.

Requires:
  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
"""
from datetime import datetime, timedelta, timezone
from typing import List, Dict

SCOPES = ["https://www.googleapis.com/auth/calendar"]  # read+write for two-way sync


def _service(token_path: str = "token.json", creds_path: str = "credentials.json"):
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    import os

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)


def fetch_google_events(days_ahead: int = 30, days_back: int = 0, **kw) -> List[Dict]:
    svc = _service(**kw)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days_back)
    end = now + timedelta(days=days_ahead)
    result = svc.events().list(
        calendarId="primary",
        timeMin=start.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events: List[Dict] = []
    for item in result.get("items", []):
        start = item["start"].get("dateTime", item["start"].get("date"))
        endt = item["end"].get("dateTime", item["end"].get("date"))
        ev = {
            "id": item.get("id"),
            "title": item.get("summary", "(no title)"),
            "start": start,
            "end": endt,
            "source": "google",
            "all_day": "date" in item["start"],
        }
        cid = item.get("colorId")
        if cid in GOOGLE_COLORS:
            ev["color"] = GOOGLE_COLORS[cid]
        events.append(ev)
    return events


def _gtime(iso: str) -> Dict:
    """Build a Google start/end object from an ISO string.
    Date-only ('2026-06-29') -> all-day {date}. A datetime without a timezone
    is assumed local and given the machine's UTC offset, which Google requires
    (a bare dateTime with no offset/timeZone is rejected with a 400)."""
    s = (iso or "").strip()
    if len(s) == 10 and s.count("-") == 2:
        return {"date": s}
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.astimezone()        # attach local offset, e.g. 14:00 -> 14:00-04:00
    return {"dateTime": dt.isoformat()}


# Google Calendar's fixed event palette (colorId -> hex). FamilyHub colors are
# arbitrary, so we snap to the nearest of these on write and read the hex back.
GOOGLE_COLORS = {
    "1": "#7986cb", "2": "#33b679", "3": "#8e24aa", "4": "#e67c73",
    "5": "#f6bf26", "6": "#f4511e", "7": "#039be5", "8": "#616161",
    "9": "#3f51b5", "10": "#0b8043", "11": "#d50000",
}


def _hex_rgb(h):
    h = (h or "").lstrip("#")
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _color_to_id(hex_color):
    """Snap an arbitrary hex color to the nearest Google colorId."""
    rgb = _hex_rgb(hex_color)
    if not rgb:
        return None
    def dist(c):
        cr = _hex_rgb(c)
        return sum((a - b) ** 2 for a, b in zip(rgb, cr))
    return min(GOOGLE_COLORS, key=lambda cid: dist(GOOGLE_COLORS[cid]))


def _rrule(recurrence: str, all_day: bool):
    """Translate FamilyHub's recurrence string into a Google RRULE list.
    'weekly;count=3' -> ['RRULE:FREQ=WEEKLY;COUNT=3'];  'monthly;exmonths=7,8'
    becomes BYMONTH of the *included* months (RRULE has no exclude)."""
    from .recurrence import _parse_rec
    if not recurrence:
        return None
    base, mods = _parse_rec(recurrence)
    freq = {"daily": "DAILY", "weekly": "WEEKLY", "monthly": "MONTHLY"}.get(base)
    if not freq:
        return None
    parts = [f"FREQ={freq}"]
    if mods.get("count", "").isdigit():
        parts.append(f"COUNT={int(mods['count'])}")
    if mods.get("until"):
        u = mods["until"].replace("-", "")
        parts.append(f"UNTIL={u}" if all_day else f"UNTIL={u}T235959Z")
    if mods.get("exmonths"):
        ex = {int(x) for x in mods["exmonths"].split(",") if x.strip().isdigit()}
        inc = [m for m in range(1, 13) if m not in ex]
        if inc:
            parts.append("BYMONTH=" + ",".join(map(str, inc)))
    return ["RRULE:" + ";".join(parts)]


def create_google_event(title: str, start_iso: str, end_iso: str,
                        recurrence=None, color=None, **kw) -> Dict:
    """Two-way sync: write an event back to Google. Skylight can't do this cleanly.
    Carries recurrence (as an RRULE) and color (snapped to Google's palette)."""
    svc = _service(**kw)
    all_day = len(start_iso.strip()) == 10
    body = {
        "summary": title,
        "start": _gtime(start_iso),
        "end": _gtime(end_iso),
    }
    rr = _rrule(recurrence, all_day)
    if rr:
        body["recurrence"] = rr
    cid = _color_to_id(color)
    if cid:
        body["colorId"] = cid
    return svc.events().insert(calendarId="primary", body=body).execute()


def update_google_event(event_id: str, title=None, start_iso=None, end_iso=None,
                        recurrence=None, color=None, **kw):
    """Patch an existing Google event (two-way edit)."""
    svc = _service(**kw)
    body = {}
    if title is not None:
        body["summary"] = title
    if start_iso:
        body["start"] = _gtime(start_iso)
    if end_iso:
        body["end"] = _gtime(end_iso)
    if recurrence is not None:
        rr = _rrule(recurrence, bool(start_iso) and len(start_iso.strip()) == 10)
        body["recurrence"] = rr or []      # [] clears recurrence
    cid = _color_to_id(color)
    if cid:
        body["colorId"] = cid
    return svc.events().patch(calendarId="primary", eventId=event_id, body=body).execute()


def delete_google_event(event_id: str, **kw):
    svc = _service(**kw)
    svc.events().delete(calendarId="primary", eventId=event_id).execute()
    return {"deleted": event_id}
