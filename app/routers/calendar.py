"""Calendar endpoints — merges all configured sources into one event list."""
import json
import os
from datetime import date, timedelta
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import get_db
from ..services import caldav_sync, google_sync, holidays_svc, ics_feed
from ..services.recurrence import expand_events
from ..services.color import build_lookups, color_for

router = APIRouter()

DEMO_FILE = "demo_events.json"


def _settings():
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='ui'").fetchone()
    if not row:
        return {}
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return {}


@router.get("/events")
def events(days: int = 30, back: int = 0, person_id: int | None = None):
    """Merged feed: synced sources + local events + ICS feeds + holidays.
    Pass person_id to show only one person's events (theirs + unassigned).
    `back` extends the window into the past so old events stay visible."""
    merged = []
    with get_db() as conn:
        sources = [dict(r) for r in conn.execute("SELECT * FROM cal_sources")]
        cats, ppl = build_lookups(conn)
        local_rows = [dict(r) for r in conn.execute("SELECT * FROM local_events")]
    for s in sources:
        cfg = json.loads(s["config"])
        try:
            if s["kind"] == "google":
                merged += google_sync.fetch_google_events(days_ahead=days, days_back=back, **cfg)
            elif s["kind"] == "caldav":
                merged += caldav_sync.fetch_caldav_events(days_ahead=days, days_back=back, **cfg)
            elif s["kind"] == "ics":
                merged += ics_feed.fetch_ics_events(days_ahead=days, days_back=back, label=s["label"], **cfg)
        except Exception as e:
            merged.append({"title": f"[sync error: {s['label']}: {e}]",
                           "start": None, "source": s["kind"], "all_day": False})
    # Local events (with recurrence expansion + resolved color)
    start = date.today() - timedelta(days=back)
    end = date.today() + timedelta(days=days)
    for r in local_rows:
        r["color"] = color_for(r, cats, ppl)
        r["source"] = "local"
        r["all_day"] = bool(r["all_day"])
    merged += expand_events(local_rows, start, end)
    # Demo fallback: if no real sources/local events and a demo file exists.
    if not sources and not local_rows and os.path.exists(DEMO_FILE):
        try:
            with open(DEMO_FILE) as f:
                merged += json.load(f)
        except Exception:
            pass
    # Holidays — only the sets toggled on in settings.
    hol_sets = _settings().get("holidays", {})
    if any(hol_sets.values()):
        merged += holidays_svc.get_holidays(hol_sets, start, start + timedelta(days=max(days, 366)))
    # Per-person filter: show this person's events plus shared/unassigned ones.
    if person_id is not None:
        merged = [e for e in merged
                  if e.get("person_id") in (person_id, None) or e.get("source") in ("holiday", "google", "caldav", "ics")]
    merged.sort(key=lambda e: e.get("start") or "")
    return {"events": merged}


class NewEvent(BaseModel):
    title: str
    start: str
    end: str
    target: str = "google"  # write-back target


@router.post("/events")
def add_event(ev: NewEvent):
    if ev.target == "google":
        return google_sync.create_google_event(ev.title, ev.start, ev.end)
    return {"error": "only google write-back wired up in scaffold"}


def _caldav_cfg():
    """Return the first connected CalDAV source's credentials, or None."""
    with get_db() as conn:
        row = conn.execute("SELECT config FROM cal_sources WHERE kind='caldav' LIMIT 1").fetchone()
    return json.loads(row["config"]) if row else None


class EditEvent(BaseModel):
    event_id: str
    title: str | None = None
    start: str | None = None
    end: str | None = None
    target: str = "google"   # "google" | "icloud"


@router.put("/events")
def edit_event(ev: EditEvent):
    if ev.target == "google":
        return google_sync.update_google_event(ev.event_id, ev.title, ev.start, ev.end)
    if ev.target == "icloud":
        cfg = _caldav_cfg()
        if not cfg:
            return {"error": "no iCloud source connected"}
        return caldav_sync.update_caldav_event(cfg["url"], cfg["username"], cfg["password"],
                                               ev.event_id, ev.title, ev.start, ev.end)
    return {"error": "unknown target"}


@router.delete("/events/{event_id}")
def delete_event(event_id: str, target: str = "google"):
    if target == "google":
        return google_sync.delete_google_event(event_id)
    if target == "icloud":
        cfg = _caldav_cfg()
        if not cfg:
            return {"error": "no iCloud source connected"}
        return caldav_sync.delete_caldav_event(cfg["url"], cfg["username"], cfg["password"], event_id)
    return {"error": "unknown target"}
