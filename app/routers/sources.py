"""Manage calendar connections (Google, iCloud/CalDAV).
The phone settings page calls these to connect accounts without touching the DB by hand."""
import json
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import get_db

router = APIRouter()


class CalDAVSource(BaseModel):
    label: str
    url: str = "https://caldav.icloud.com/"
    username: str
    password: str          # iCloud app-specific password
    person_id: int | None = None
    category_id: int | None = None
    sync_reminders: bool = True   # also pull iCloud Reminders into the to-do list


class GoogleSource(BaseModel):
    label: str
    person_id: int | None = None
    category_id: int | None = None
    # token.json / credentials.json live on disk; config just records which to use


@router.get("/")
def list_sources():
    """List connections WITHOUT exposing stored passwords/tokens."""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT id, kind, label, person_id, category_id FROM cal_sources")]
    return rows


@router.post("/caldav")
def add_caldav(s: CalDAVSource):
    cfg = {"url": s.url, "username": s.username, "password": s.password, "sync_reminders": s.sync_reminders}
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO cal_sources (kind, label, config, person_id, category_id) VALUES ('caldav',?,?,?,?)",
            (s.label, json.dumps(cfg), s.person_id, s.category_id))
        sid = cur.lastrowid
    if s.sync_reminders:
        import threading
        from ..services import reminders_sync
        threading.Thread(target=reminders_sync.sync_once, daemon=True).start()
    return {"id": sid, "kind": "caldav"}


@router.post("/google")
def add_google(s: GoogleSource):
    cfg = {"token_path": "token.json", "creds_path": "credentials.json"}
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO cal_sources (kind, label, config, person_id, category_id) VALUES ('google',?,?,?,?)",
            (s.label, json.dumps(cfg), s.person_id, s.category_id))
        return {"id": cur.lastrowid, "kind": "google"}


@router.delete("/{source_id}")
def delete_source(source_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM cal_sources WHERE id=?", (source_id,))
        return {"deleted": source_id}


class ICSSource(BaseModel):
    label: str
    url: str
    color: str | None = None
    person_id: int | None = None
    category_id: int | None = None


@router.post("/ics")
def add_ics(s: ICSSource):
    """Subscribe to an external ICS/webcal feed (sports, golf, school, trash, etc.)."""
    cfg = {"url": s.url, "color": s.color}
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO cal_sources (kind, label, config, person_id, category_id) VALUES ('ics',?,?,?,?)",
            (s.label, json.dumps(cfg), s.person_id, s.category_id))
        return {"id": cur.lastrowid, "kind": "ics"}
