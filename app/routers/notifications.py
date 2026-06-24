"""Notifications — reminders before events + a morning 'today' digest.

Design: notifications are queued in the DB with a fire time. The frontend polls
/api/notifications/due, shows anything ready (browser Notification API on the wall,
in-app toast on phone), and marks it seen. No external push service needed — works
entirely on your LAN. A morning digest is generated on demand for 'today'."""
from datetime import date, datetime, timedelta
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import get_db

router = APIRouter()


@router.get("/due")
def due_notifications():
    """Return unfired notifications whose time has passed; caller marks them seen."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM notifications WHERE fired=0 AND at<=? ORDER BY at", (now,))]
    return {"notifications": rows}


@router.post("/{notif_id}/seen")
def mark_seen(notif_id: int):
    with get_db() as conn:
        conn.execute("UPDATE notifications SET fired=1 WHERE id=?", (notif_id,))
        return {"id": notif_id, "seen": True}


@router.post("/digest")
def make_digest():
    """Build a 'here's today' summary: today's events, chores due, meals planned."""
    today = date.today().isoformat()
    with get_db() as conn:
        chores = [dict(r) for r in conn.execute(
            "SELECT title FROM chores WHERE done=0 AND (due_date IS NULL OR due_date<=?)", (today,))]
        meals = [dict(r) for r in conn.execute(
            "SELECT slot,title FROM meals WHERE date=? ORDER BY slot", (today,))]
        local = [dict(r) for r in conn.execute(
            "SELECT title,start FROM local_events WHERE start LIKE ? ORDER BY start", (today+"%",))]
    parts = []
    if local:
        parts.append(f"{len(local)} event{'s' if len(local)!=1 else ''}")
    if chores:
        parts.append(f"{len(chores)} chore{'s' if len(chores)!=1 else ''}")
    if meals:
        parts.append("meals planned")
    summary = "Today: " + (", ".join(parts) if parts else "nothing scheduled — enjoy!")
    body_lines = []
    for e in local:
        t = e["start"][11:16] if len(e["start"]) >= 16 else ""
        body_lines.append(f"{t} {e['title']}".strip())
    for c in chores:
        body_lines.append(f"☐ {c['title']}")
    for m in meals:
        body_lines.append(f"{m['slot']}: {m['title']}")
    with get_db() as conn:
        conn.execute("INSERT INTO notifications (title, body, kind, at, fired) VALUES (?,?,?,?,0)",
                     (summary, "\n".join(body_lines), "digest", datetime.now().isoformat()))
    return {"summary": summary, "details": body_lines}
