"""To-do list with category/color, recurrence, and edit/delete."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from ..db import get_db
from ..services.recurrence import next_occurrence
from ..services.assign import norm, expand
from ..services import undo

router = APIRouter()


class Todo(BaseModel):
    title: str
    person_id: int | None = None
    category_id: int | None = None
    color: str | None = None
    due_date: str | None = None
    recurrence: str | None = None
    person_ids: list[int] | None = None   # several people; person_id becomes the first
    list_name: str | None = None     # which list ("This weekend", "Work"…); None = the main To-do list


def _ln(v):
    v = (v or "").strip()[:40]
    return None if not v or v.lower() in ("to-do", "to do", "todo") else v


@router.post("/sync")
def sync_now():
    """Pull iCloud Reminders right now (the background loop does it every 5 min)."""
    from ..services import reminders_sync
    return reminders_sync.sync_once()


@router.get("/")
def list_todos():
    with get_db() as conn:
        return [undo.mark(expand(dict(r))) for r in conn.execute(
            "SELECT * FROM todos ORDER BY done, created_at DESC")]


@router.post("/")
def add_todo(t: Todo):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO todos (title, person_id, person_ids, category_id, color, due_date, recurrence, list_name) VALUES (?,?,?,?,?,?,?,?)",
            (t.title, *norm(t.person_id, t.person_ids), t.category_id, t.color, t.due_date, t.recurrence, _ln(t.list_name)))
        return {"id": cur.lastrowid}


@router.put("/{todo_id}")
def update_todo(todo_id: int, t: Todo):
    with get_db() as conn:
        conn.execute(
            "UPDATE todos SET title=?, person_id=?, person_ids=?, category_id=?, color=?, due_date=?, recurrence=?, list_name=COALESCE(?, list_name) WHERE id=?",
            (t.title, *norm(t.person_id, t.person_ids), t.category_id, t.color, t.due_date, t.recurrence, _ln(t.list_name), todo_id))
        return {"id": todo_id}


@router.post("/{todo_id}/toggle")
def toggle(todo_id: int, skip: bool = False, complete: bool = False):
    """Tick a to-do (a repeating one rolls to its next date). Tapping it again within settings.undoMinutes puts it back.
    skip = "skip this one" (roll a repeating item on, never an undo). complete = voice: make it done, never un-do it."""
    with get_db() as conn:
        row = conn.execute("SELECT done, recurrence, due_date, done_at, undo_due FROM todos WHERE id=?",
                           (todo_id,)).fetchone()
        if not row:
            raise HTTPException(404, "no such to-do")
        if undo.recent(row) and complete:
            return {"id": todo_id, "done": 1, "already": True}
        if undo.recent(row) and not skip:           # oops: bring it back exactly as it was
            if row["undo_due"] is not None:
                conn.execute("UPDATE todos SET due_date=?, done=0, done_at=NULL, undo_due=NULL WHERE id=?",
                             (row["undo_due"] or None, todo_id))
            else:
                conn.execute("UPDATE todos SET done=0, done_at=NULL WHERE id=?", (todo_id,))
            reopen = True
        else:
            reopen = False
    if reopen:
        import threading
        from ..services import reminders_sync
        threading.Thread(target=reminders_sync.push_reopen, args=(todo_id,), daemon=True).start()
        return {"id": todo_id, "done": 0, "undone": True}
    with get_db() as conn:
        rec = row["recurrence"]
        if rec and not row["done"]:
            base = date.fromisoformat(row["due_date"]) if row["due_date"] else date.today()
            nxt = next_occurrence(rec, base)
            if skip:                                # skipped, not done: no crossed-out row, nothing to undo
                conn.execute("UPDATE todos SET due_date=?, done=0, done_at=NULL, undo_due=NULL WHERE id=?",
                             (nxt.isoformat() if nxt else None, todo_id))
                return {"id": todo_id, "recurred": True, "skipped": True, "next": nxt.isoformat() if nxt else None}
            conn.execute("UPDATE todos SET due_date=?, done=0, done_at=?, undo_due=? WHERE id=?",
                         (nxt.isoformat() if nxt else None, undo.now(), row["due_date"] or "", todo_id))
            return {"id": todo_id, "recurred": True, "next": nxt.isoformat() if nxt else None}
        new = 1 if complete else (0 if row["done"] else 1)
        conn.execute("UPDATE todos SET done=?, done_at=?, undo_due=NULL WHERE id=?", (new, undo.now() if new else None, todo_id))
    if new:
        # synced from iCloud Reminders? complete it there too (best effort, off the request path)
        import threading
        from ..services import reminders_sync
        threading.Thread(target=reminders_sync.push_complete, args=(todo_id,), daemon=True).start()
    return {"id": todo_id, "done": new}


@router.post("/{todo_id}/list")
def move_to_list(todo_id: int, payload: dict):
    with get_db() as conn:
        conn.execute("UPDATE todos SET list_name=? WHERE id=?", (_ln((payload or {}).get("list_name")), todo_id))
    return {"id": todo_id}


@router.delete("/{todo_id}")
def delete(todo_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM todos WHERE id=?", (todo_id,))
        return {"deleted": todo_id}
