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
    from ..services import sync_status
    for s in sources:
        cfg = json.loads(s["config"])
        try:
            got = []
            if s["kind"] == "google":
                got = google_sync.fetch_google_events(days_ahead=days, days_back=back, **cfg)
            elif s["kind"] == "caldav":
                cfg = {k: v for k, v in cfg.items() if k in ("url", "username", "password")}
                got = caldav_sync.fetch_caldav_events(days_ahead=days, days_back=back, **cfg)
            elif s["kind"] == "ics":
                got = ics_feed.fetch_ics_events(days_ahead=days, days_back=back, label=s["label"], **cfg)
            merged += got
            sync_status.mark(f"cal:{s['id']}", True, len(got), label=s["label"])
        except Exception as e:
            sync_status.mark(f"cal:{s['id']}", False, 0, str(e), label=s["label"])
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
    # Demo fallback: if no real sources/local events and a demo file exists —
    # unless the family cleared the sample data on purpose.
    with get_db() as conn:
        cleared = conn.execute("SELECT 1 FROM settings WHERE key='demo_cleared'").fetchone()
    if not sources and not local_rows and not cleared and os.path.exists(DEMO_FILE):
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
    merged = _explode_multiday(merged, start, end)
    merged.sort(key=lambda e: e.get("start") or "")
    return {"events": merged}


def _explode_multiday(events: list, start: date, end: date) -> list:
    """A vacation that runs Sat→Sun+1 is ONE all-day event with an exclusive end date.
    The wall and phone place events by their start day, so split such events into a
    copy per day (same id, so editing/deleting still hits the real event) and tag each
    copy with day_of/days ("day 2 of 7")."""
    out = []
    for e in events:
        if not e.get("all_day") or not e.get("start") or not e.get("end"):
            out.append(e); continue
        try:
            s = date.fromisoformat(str(e["start"])[:10]); x = date.fromisoformat(str(e["end"])[:10])
        except ValueError:
            out.append(e); continue
        n = (x - s).days
        if n <= 1:
            out.append(e); continue
        for i in range(n):
            d = s + timedelta(days=i)
            if d < start or d > end:
                continue
            c = dict(e); c["start"] = d.isoformat(); c["end"] = (d + timedelta(days=1)).isoformat()
            c["day_of"] = i + 1; c["days"] = n; c["span_start"] = s.isoformat(); c["span_end"] = x.isoformat()
            out.append(c)
    return out


class NewEvent(BaseModel):
    title: str
    start: str
    end: str
    all_day: bool = False
    person_id: int | None = None
    category_id: int | None = None
    color: str | None = None
    description: str | None = None
    recurrence: str | None = None
    target: str = "auto"  # "auto" | "google" | "local"
    destination: str | None = None   # "local" | "google" | "caldav:<source id>:<calendar name>"


def _has_source(kind: str) -> bool:
    with get_db() as conn:
        return conn.execute("SELECT 1 FROM cal_sources WHERE kind=? LIMIT 1", (kind,)).fetchone() is not None


def _add_local_event(ev: "NewEvent") -> dict:
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO local_events (title,start,end,all_day,person_id,category_id,color,description,recurrence) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (ev.title, ev.start, ev.end, int(ev.all_day), ev.person_id, ev.category_id, ev.color, ev.description, ev.recurrence))
        return {"id": cur.lastrowid, "target": "local"}


@router.post("/events")
def add_event(ev: NewEvent):
    """Create an event. 'auto' writes to Google if connected, otherwise stores
    it locally so it always shows on the calendar. Errors are returned (not 500)
    so the phone can surface them."""
    dest = ev.destination or ""
    if dest.startswith("caldav:"):
        parts = dest.split(":", 2)
        sid = parts[1] if len(parts) > 1 else ""
        calname = parts[2] if len(parts) > 2 else ""
        with get_db() as conn:
            row = conn.execute("SELECT config FROM cal_sources WHERE id=? AND kind='caldav'", (sid,)).fetchone()
        if not row:
            return {**_add_local_event(ev), "warning": "that iCloud calendar is no longer connected; saved locally"}
        cfg = json.loads(row["config"])
        try:
            res = caldav_sync.create_caldav_event(cfg["url"], cfg["username"], cfg["password"], ev.title,
                                                  ev.start, ev.end, calendar_name=calname or None,
                                                  all_day=ev.all_day, description=ev.description)
            return {"id": res.get("uid"), "target": "icloud", "calendar": calname}
        except Exception as e:
            local = _add_local_event(ev)
            return {**local, "warning": f"saved locally (iCloud write failed: {e})"}
    if dest == "local":
        return _add_local_event(ev)
    want_google = dest == "google" or ev.target == "google" or (ev.target == "auto" and not dest and _has_source("google"))
    if want_google:
        try:
            res = google_sync.create_google_event(ev.title, ev.start, ev.end,
                                                   recurrence=ev.recurrence, color=ev.color,
                                                   description=ev.description)
            return {"id": res.get("id"), "target": "google"}
        except Exception as e:
            # don't lose the event — fall back to a local copy and report it
            local = _add_local_event(ev)
            return {**local, "warning": f"saved locally (Google write failed: {e})"}
    return _add_local_event(ev)


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
    color: str | None = None
    description: str | None = None
    recurrence: str | None = None
    target: str = "google"   # "google" | "icloud"


@router.put("/events")
def edit_event(ev: EditEvent):
    if ev.target == "google":
        return google_sync.update_google_event(ev.event_id, ev.title, ev.start, ev.end,
                                               recurrence=ev.recurrence, color=ev.color,
                                               description=ev.description)
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
