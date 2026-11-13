"""To-do list with category/color, recurrence, and edit/delete."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import date
from ..db import get_db
from ..services.recurrence import next_occurrence

router = APIRouter()


class Todo(BaseModel):
    title: str
    person_id: int | None = None
    category_id: int | None = None
    color: str | None = None
    due_date: str | None = None
    recurrence: str | None = None
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
        return [dict(r) for r in conn.execute(
            "SELECT * FROM todos ORDER BY done, created_at DESC")]


@router.post("/")
def add_todo(t: Todo):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO todos (title, person_id, category_id, color, due_date, recurrence, list_name) VALUES (?,?,?,?,?,?,?)",
            (t.title, t.person_id, t.category_id, t.color, t.due_date, t.recurrence, _ln(t.list_name)))
        return {"id": cur.lastrowid}


@router.put("/{todo_id}")
def update_todo(todo_id: int, t: Todo):
    with get_db() as conn:
        conn.execute(
            "UPDATE todos SET title=?, person_id=?, category_id=?, color=?, due_date=?, recurrence=?, list_name=COALESCE(?, list_name) WHERE id=?",
            (t.title, t.person_id, t.category_id, t.color, t.due_date, t.recurrence, _ln(t.list_name), todo_id))
        return {"id": todo_id}


@router.post("/{todo_id}/toggle")
def toggle(todo_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT done, recurrence, due_date FROM todos WHERE id=?",
                           (todo_id,)).fetchone()
        if not row:
            raise HTTPException(404, "no such to-do")
        rec = row["recurrence"]
        if rec and not row["done"]:
            base = date.fromisoformat(row["due_date"]) if row["due_date"] else date.today()
            nxt = next_occurrence(rec, base)
            conn.execute("UPDATE todos SET due_date=?, done=0 WHERE id=?",
                         (nxt.isoformat() if nxt else None, todo_id))
            return {"id": todo_id, "recurred": True, "next": nxt.isoformat() if nxt else None}
        new = 0 if row["done"] else 1
        conn.execute("UPDATE todos SET done=? WHERE id=?", (new, todo_id))
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
