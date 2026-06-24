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


def fetch_google_events(days_ahead: int = 30, **kw) -> List[Dict]:
    svc = _service(**kw)
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days_ahead)
    result = svc.events().list(
        calendarId="primary",
        timeMin=now.isoformat(),
        timeMax=end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
    ).execute()

    events: List[Dict] = []
    for item in result.get("items", []):
        start = item["start"].get("dateTime", item["start"].get("date"))
        endt = item["end"].get("dateTime", item["end"].get("date"))
        events.append({
            "id": item.get("id"),
            "title": item.get("summary", "(no title)"),
            "start": start,
            "end": endt,
            "source": "google",
            "all_day": "date" in item["start"],
        })
    return events


def create_google_event(title: str, start_iso: str, end_iso: str, **kw) -> Dict:
    """Two-way sync: write an event back to Google. Skylight can't do this cleanly."""
    svc = _service(**kw)
    body = {
        "summary": title,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    return svc.events().insert(calendarId="primary", body=body).execute()


def update_google_event(event_id: str, title=None, start_iso=None, end_iso=None, **kw):
    """Patch an existing Google event (two-way edit)."""
    svc = _service(**kw)
    body = {}
    if title is not None:
        body["summary"] = title
    if start_iso:
        body["start"] = {"dateTime": start_iso}
    if end_iso:
        body["end"] = {"dateTime": end_iso}
    return svc.events().patch(calendarId="primary", eventId=event_id, body=body).execute()


def delete_google_event(event_id: str, **kw):
    svc = _service(**kw)
    svc.events().delete(calendarId="primary", eventId=event_id).execute()
    return {"deleted": event_id}
