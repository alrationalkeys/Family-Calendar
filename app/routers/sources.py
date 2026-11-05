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


import time as _time
_TARGET_CACHE = {"at": 0.0, "key": None, "items": []}


@router.get("/status")
def status():
    """Last sync per connection: when, how many, any error. Calendars refresh on
    every wall poll (~60 s); Reminders every 5 min."""
    from ..services import sync_status
    return {"status": sync_status.snapshot()}


@router.post("/sync")
def sync_now():
    """Force a calendar fetch + Reminders pull right now."""
    from .calendar import events as cal_events
    from ..services import reminders_sync, sync_status
    try:
        evs = cal_events(days=30, back=0).get("events", [])
    except Exception:
        evs = []
    rem = reminders_sync.sync_once()
    return {"events": len(evs), "reminders": rem, "status": sync_status.snapshot()}


@router.get("/targets")
def targets(refresh: bool = False):
    """Where a new event can be written: FamilyHub itself, each Google account, and
    each calendar inside each iCloud account. ICS feeds are read-only."""
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT id, kind, label, config FROM cal_sources ORDER BY id")]
    key = tuple(r["id"] for r in rows)
    if not refresh and _TARGET_CACHE["key"] == key and _time.time() - _TARGET_CACHE["at"] < 600:
        return {"targets": _TARGET_CACHE["items"]}
    items = [{"id": "local", "label": "FamilyHub only (this screen)"}]
    for r in rows:
        if r["kind"] == "google":
            items.append({"id": "google", "label": f"{r['label']} (Google)"})
        elif r["kind"] == "caldav":
            cfg = json.loads(r["config"])
            names = []
            try:
                from ..services import caldav_sync
                names = caldav_sync.list_event_calendars(cfg["url"], cfg["username"], cfg["password"])
            except Exception:
                pass
            if names:
                for n in names:
                    items.append({"id": f"caldav:{r['id']}:{n}", "label": f"{r['label']} › {n}"})
            else:
                items.append({"id": f"caldav:{r['id']}:", "label": f"{r['label']} (iCloud)"})
    _TARGET_CACHE.update({"at": _time.time(), "key": key, "items": items})
    return {"targets": items}


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
