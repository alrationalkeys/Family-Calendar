"""Weekly meal planner with category + color."""
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import get_db

router = APIRouter()


class Meal(BaseModel):
    date: str
    slot: str
    title: str
    notes: str | None = None
    category_id: int | None = None
    color: str | None = None


@router.get("/")
def list_meals():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM meals ORDER BY date, slot")]


@router.post("/")
def add_meal(m: Meal):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO meals (date, slot, title, notes, category_id, color) VALUES (?,?,?,?,?,?)",
            (m.date, m.slot, m.title, m.notes, m.category_id, m.color))
        return {"id": cur.lastrowid}


@router.put("/{meal_id}")
def update_meal(meal_id: int, m: Meal):
    with get_db() as conn:
        conn.execute(
            "UPDATE meals SET date=?, slot=?, title=?, notes=?, category_id=?, color=? WHERE id=?",
            (m.date, m.slot, m.title, m.notes, m.category_id, m.color, meal_id))
        return {"id": meal_id}


@router.delete("/{meal_id}")
def delete_meal(meal_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM meals WHERE id=?", (meal_id,))
        return {"deleted": meal_id}
