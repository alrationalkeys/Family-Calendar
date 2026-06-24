"""Chore chart with stars, person/category color, recurrence, and edit/delete."""
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime, date
from ..db import get_db
from ..services.recurrence import next_occurrence

router = APIRouter()


class Chore(BaseModel):
    title: str
    person_id: int | None = None
    category_id: int | None = None
    color: str | None = None
    due_date: str | None = None
    recurrence: str | None = None
    stars: int = 0


@router.get("/")
def list_chores():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM chores ORDER BY done, due_date")]


@router.post("/")
def add_chore(c: Chore):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO chores (title, person_id, category_id, color, due_date, recurrence, stars) "
            "VALUES (?,?,?,?,?,?,?)",
            (c.title, c.person_id, c.category_id, c.color, c.due_date, c.recurrence, c.stars))
        return {"id": cur.lastrowid}


@router.put("/{chore_id}")
def update_chore(chore_id: int, c: Chore):
    with get_db() as conn:
        conn.execute(
            "UPDATE chores SET title=?, person_id=?, category_id=?, color=?, due_date=?, "
            "recurrence=?, stars=? WHERE id=?",
            (c.title, c.person_id, c.category_id, c.color, c.due_date, c.recurrence, c.stars, chore_id))
        return {"id": chore_id}


@router.delete("/{chore_id}")
def delete_chore(chore_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM chores WHERE id=?", (chore_id,))
        return {"deleted": chore_id}


@router.post("/{chore_id}/toggle")
def toggle(chore_id: int):
    """Complete a chore. If it recurs, roll due_date forward and stay active.
    Completing a chore with stars credits the assigned person's reward balance."""
    with get_db() as conn:
        row = conn.execute("SELECT done, recurrence, due_date, stars, person_id, title FROM chores WHERE id=?",
                           (chore_id,)).fetchone()
        rec = row["recurrence"]
        completing = not row["done"]
        if completing and row["stars"] and row["person_id"]:
            conn.execute("INSERT INTO reward_ledger (person_id,stars,reason) VALUES (?,?,?)",
                         (row["person_id"], row["stars"], f"chore: {row['title']}"))
        if rec and completing:
            base = date.fromisoformat(row["due_date"]) if row["due_date"] else date.today()
            nxt = next_occurrence(rec, base)
            conn.execute("UPDATE chores SET due_date=?, done=0 WHERE id=?",
                         (nxt.isoformat() if nxt else None, chore_id))
            return {"id": chore_id, "recurred": True, "next": nxt.isoformat() if nxt else None,
                    "stars_earned": row["stars"] if row["person_id"] else 0}
        new = 0 if row["done"] else 1
        conn.execute("UPDATE chores SET done=?, done_at=? WHERE id=?",
                     (new, datetime.now().isoformat() if new else None, chore_id))
        return {"id": chore_id, "done": new,
                "stars_earned": row["stars"] if (completing and row["person_id"]) else 0}
