"""Manage color categories (work, kids, appointments, sports...)."""
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import get_db

router = APIRouter()


class Category(BaseModel):
    name: str
    color: str = "#4f86c6"


@router.get("/")
def list_categories():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM categories ORDER BY name")]


@router.post("/")
def add_category(c: Category):
    with get_db() as conn:
        cur = conn.execute("INSERT INTO categories (name,color) VALUES (?,?)", (c.name, c.color))
        return {"id": cur.lastrowid, "name": c.name, "color": c.color}


@router.put("/{cat_id}")
def update_category(cat_id: int, c: Category):
    with get_db() as conn:
        conn.execute("UPDATE categories SET name=?, color=? WHERE id=?", (c.name, c.color, cat_id))
        return {"id": cat_id, "name": c.name, "color": c.color}


@router.delete("/{cat_id}")
def delete_category(cat_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.execute("UPDATE chores SET category_id=NULL WHERE category_id=?", (cat_id,))
        conn.execute("UPDATE meals SET category_id=NULL WHERE category_id=?", (cat_id,))
        conn.execute("UPDATE todos SET category_id=NULL WHERE category_id=?", (cat_id,))
        conn.execute("UPDATE groceries SET category_id=NULL WHERE category_id=?", (cat_id,))
        return {"deleted": cat_id}


class Person(BaseModel):
    name: str
    color: str = "#4f86c6"


@router.get("/people")
def list_people():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM people ORDER BY name")]


@router.post("/people")
def add_person(p: Person):
    with get_db() as conn:
        cur = conn.execute("INSERT INTO people (name,color) VALUES (?,?)", (p.name, p.color))
        return {"id": cur.lastrowid, "name": p.name, "color": p.color}


@router.put("/people/{pid}")
def update_person(pid: int, p: Person):
    with get_db() as conn:
        conn.execute("UPDATE people SET name=?, color=? WHERE id=?", (p.name, p.color, pid))
        return {"id": pid, "name": p.name, "color": p.color}
