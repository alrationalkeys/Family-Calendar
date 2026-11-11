"""Local events — events FamilyHub owns (not from Google/iCloud).
Supports recurrence and per-event reminders. These merge into the calendar feed
alongside synced events, and they're the source for recurring 'soccer every Saturday'
type entries plus reminder notifications."""
import json
from datetime import date, datetime, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..db import get_db
from ..services.recurrence import expand_events
from ..services.color import build_lookups, color_for

router = APIRouter()


class LocalEvent(BaseModel):
    title: str
    start: str
    end: str | None = None
    all_day: bool = False
    person_id: int | None = None
    category_id: int | None = None
    color: str | None = None
    description: str | None = None
    recurrence: str | None = None
    reminder_minutes: int | None = None
    location: str | None = None


@router.get("/")
def list_events(days: int = 60):
    start = date.today()
    end = start + timedelta(days=days)
    with get_db() as conn:
        cats, ppl = build_lookups(conn)
        rows = [dict(r) for r in conn.execute("SELECT * FROM local_events")]
    for r in rows:
        r["color"] = color_for(r, cats, ppl)
        r["source"] = "local"
        r["all_day"] = bool(r["all_day"])
    expanded = expand_events(rows, start, end)
    expanded.sort(key=lambda e: e.get("start") or "")
    return {"events": expanded}


@router.post("/")
def add_event(e: LocalEvent):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO local_events (title,start,end,all_day,person_id,category_id,color,description,recurrence,reminder_minutes,location) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (e.title, e.start, e.end, int(e.all_day), e.person_id, e.category_id,
             e.color, e.description, e.recurrence, e.reminder_minutes, e.location))
        eid = cur.lastrowid
        _schedule_reminder(conn, eid, e)
        return {"id": eid}


@router.put("/{event_id}")
def update_event(event_id: int, e: LocalEvent):
    with get_db() as conn:
        conn.execute(
            "UPDATE local_events SET title=?,start=?,end=?,all_day=?,person_id=?,category_id=?,"
            "color=?,description=?,recurrence=?,reminder_minutes=?,location=? WHERE id=?",
            (e.title, e.start, e.end, int(e.all_day), e.person_id, e.category_id,
             e.color, e.description, e.recurrence, e.reminder_minutes, e.location, event_id))
        conn.execute("DELETE FROM notifications WHERE kind='reminder' AND body=?", (str(event_id),))
        _schedule_reminder(conn, event_id, e)
        return {"id": event_id}


def _skips(conn, event_id: int) -> list:
    row = conn.execute("SELECT skip_dates FROM local_events WHERE id=?", (event_id,)).fetchone()
    if not row:
        raise HTTPException(404, "no such event")
    try:
        return json.loads(row["skip_dates"] or "[]") or []
    except ValueError:
        return []


@router.post("/{event_id}/skip")
def skip_occurrence(event_id: int, payload: dict):
    """Cancel ONE occurrence of a recurring local event: {date: "YYYY-MM-DD"}.
    The series carries on; that day simply disappears from the calendar."""
    d = str((payload or {}).get("date", ""))[:10]
    try:
        date.fromisoformat(d)
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")
    with get_db() as conn:
        skips = _skips(conn, event_id)
        if d not in skips:
            skips.append(d)
        conn.execute("UPDATE local_events SET skip_dates=? WHERE id=?", (json.dumps(sorted(skips)), event_id))
        # a reminder queued for that day is no longer wanted
        conn.execute("DELETE FROM notifications WHERE kind='reminder' AND body=? AND at LIKE ?", (str(event_id), d + "%"))
    return {"id": event_id, "skip_dates": sorted(skips)}


@router.delete("/{event_id}/skip/{d}")
def unskip_occurrence(event_id: int, d: str):
    """Put a skipped occurrence back."""
    with get_db() as conn:
        skips = [s for s in _skips(conn, event_id) if s != d[:10]]
        conn.execute("UPDATE local_events SET skip_dates=? WHERE id=?", (json.dumps(skips), event_id))
    return {"id": event_id, "skip_dates": skips}


@router.delete("/{event_id}")
def delete_event(event_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM local_events WHERE id=?", (event_id,))
        conn.execute("DELETE FROM notifications WHERE kind='reminder' AND body=?", (str(event_id),))
        return {"deleted": event_id}


def _schedule_reminder(conn, event_id, e):
    """Queue a reminder notification N minutes before the (first) event start."""
    if e.reminder_minutes is None:
        return
    try:
        start_dt = datetime.fromisoformat(e.start)
    except ValueError:
        return
    fire_at = start_dt - timedelta(minutes=e.reminder_minutes)
    conn.execute(
        "INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
        (f"Upcoming: {e.title}", str(event_id), "reminder", fire_at.isoformat()))
