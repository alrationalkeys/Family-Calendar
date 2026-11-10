"""Grocery list with category + color support."""
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import get_db

router = APIRouter()


class Item(BaseModel):
    item: str
    qty: str | None = None
    category_id: int | None = None
    color: str | None = None


GOT_TTL_MIN = 30   # a ticked item stays crossed out this long (undo window), then leaves the list


def purge_got(conn):
    """Drop items ticked more than GOT_TTL_MIN ago (legacy rows ticked before got_at existed go too)."""
    conn.execute("DELETE FROM groceries WHERE got=1 AND (got_at IS NULL OR got_at < datetime('now', ?))",
                 (f"-{GOT_TTL_MIN} minutes",))


@router.get("/")
def list_items():
    with get_db() as conn:
        purge_got(conn)
        return [dict(r) for r in conn.execute(
            "SELECT * FROM groceries ORDER BY got, created_at DESC")]


@router.post("/")
def add_item(i: Item):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO groceries (item, qty, category_id, color) VALUES (?,?,?,?)",
            (i.item, i.qty, i.category_id, i.color))
        return {"id": cur.lastrowid}


@router.post("/{item_id}/toggle")
def toggle(item_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT got FROM groceries WHERE id=?", (item_id,)).fetchone()
        new = 0 if row["got"] else 1
        conn.execute("UPDATE groceries SET got=?, got_at=CASE WHEN ?=1 THEN datetime('now') ELSE NULL END WHERE id=?", (new, new, item_id))
        return {"id": item_id, "got": new}


@router.post("/clear-got")
def clear_got():
    with get_db() as conn:
        conn.execute("DELETE FROM groceries WHERE got=1")
        return {"ok": True}


@router.put("/{item_id}")
def update_item(item_id: int, i: Item):
    with get_db() as conn:
        conn.execute(
            "UPDATE groceries SET item=?, qty=?, category_id=?, color=? WHERE id=?",
            (i.item, i.qty, i.category_id, i.color, item_id))
        return {"id": item_id}


@router.delete("/{item_id}")
def delete_item(item_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM groceries WHERE id=?", (item_id,))
        return {"deleted": item_id}
