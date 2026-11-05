"""
iCloud Reminders <-> FamilyHub To-Do (two-way).

Apple shows Reminders inside the Calendar app, so families that "live in
Reminders" see an empty FamilyHub calendar. Reminders are CalDAV VTODOs on the
same iCloud account as the calendars, so the iCloud connection we already have
can read them:

  pull  every 5 min: every open reminder in every list -> a FamilyHub to-do
        (matched by UID; title/due kept in sync; reminders completed or deleted
        on the phone are marked done here)
  push  ticking a synced to-do on the wall/phone -> completes it in Reminders

Only CalDAV sources with config.sync_reminders != False take part (iCloud default on).
Never raises into callers; a dead connection just skips a cycle.
"""
from __future__ import annotations

import json
from datetime import date, datetime

from ..db import get_db

try:
    import caldav
except ImportError:          # pragma: no cover
    caldav = None


def _client(cfg):
    return caldav.DAVClient(url=cfg["url"], username=cfg["username"], password=cfg["password"])


def _due_iso(comp) -> str | None:
    due = comp.get("due") or comp.get("dtstart")
    if not due:
        return None
    d = due.dt
    return (d.date() if isinstance(d, datetime) else d).isoformat()


def fetch_open(cfg) -> list[dict]:
    """[{uid, title, due, list}] for every incomplete reminder on the account."""
    out = []
    principal = _client(cfg).principal()
    for cal in principal.calendars():
        try:
            comps = cal.get_supported_components() or []
            if comps and "VTODO" not in comps:
                continue
            todos = cal.todos(include_completed=False)
        except Exception:
            continue
        for t in todos:
            try:
                comp = t.icalendar_component
                if str(comp.get("status", "")).upper() in ("COMPLETED", "CANCELLED"):
                    continue
                out.append({"uid": str(comp.get("uid", "")), "title": str(comp.get("summary") or "(untitled)")[:200],
                            "due": _due_iso(comp), "list": cal.name or "Reminders"})
            except Exception:
                continue
    return out


def complete(cfg, uid: str) -> bool:
    try:
        principal = _client(cfg).principal()
        for cal in principal.calendars():
            try:
                t = cal.todo_by_uid(uid)
            except Exception:
                t = None
            if t:
                t.complete()
                return True
    except Exception:
        pass
    return False


def _sources(conn):
    rows = conn.execute("SELECT id, label, config, person_id, category_id FROM cal_sources WHERE kind='caldav'").fetchall()
    out = []
    for r in rows:
        cfg = json.loads(r["config"])
        if cfg.get("sync_reminders", True):
            out.append((r, cfg))
    return out


def sync_once() -> dict:
    """Pull reminders from every iCloud source into the todos table."""
    if caldav is None:
        return {"ok": False, "reason": "caldav not installed"}
    pulled, done_upstream = 0, 0
    with get_db() as conn:
        for src, cfg in _sources(conn):
            try:
                open_items = fetch_open(cfg)
            except Exception as e:
                continue
            seen = set()
            for it in open_items:
                if not it["uid"]:
                    continue
                seen.add(it["uid"])
                row = conn.execute("SELECT id, done, title, due_date FROM todos WHERE ext_uid=? AND ext_source=?",
                                   (it["uid"], f"caldav:{src['id']}")).fetchone()
                if row is None:
                    conn.execute("INSERT INTO todos (title, due_date, ext_uid, ext_source, ext_list, category_id) VALUES (?,?,?,?,?,?)",
                                 (it["title"], it["due"], it["uid"], f"caldav:{src['id']}", it["list"], src["category_id"]))
                    pulled += 1
                elif row["title"] != it["title"] or row["due_date"] != it["due"] or row["done"]:
                    # reopened or edited on the phone -> mirror it (done=0 again)
                    conn.execute("UPDATE todos SET title=?, due_date=?, done=0, ext_list=? WHERE id=?",
                                 (it["title"], it["due"], it["list"], row["id"]))
            # anything we hold for this source that's no longer open upstream was completed/deleted there
            for row in conn.execute("SELECT id, ext_uid FROM todos WHERE ext_source=? AND done=0", (f"caldav:{src['id']}",)).fetchall():
                if row["ext_uid"] not in seen:
                    conn.execute("UPDATE todos SET done=1 WHERE id=?", (row["id"],))
                    done_upstream += 1
    return {"ok": True, "pulled": pulled, "completed_upstream": done_upstream}


def push_complete(todo_id: int) -> bool:
    """Called when a synced to-do is ticked locally: complete it in Reminders."""
    with get_db() as conn:
        row = conn.execute("SELECT ext_uid, ext_source FROM todos WHERE id=?", (todo_id,)).fetchone()
        if not row or not row["ext_uid"] or not (row["ext_source"] or "").startswith("caldav:"):
            return False
        sid = int(row["ext_source"].split(":", 1)[1])
        src = conn.execute("SELECT config FROM cal_sources WHERE id=?", (sid,)).fetchone()
    if not src or caldav is None:
        return False
    return complete(json.loads(src["config"]), row["ext_uid"])
