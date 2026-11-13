"""Aggregates everything into the single feed the wall display polls.
Resolves a final `color` onto every item using the central color rule."""
from datetime import date
from fastapi import APIRouter
from ..db import get_db
from ..services.color import build_lookups, color_for
from ..services.assign import expand

router = APIRouter()


def _colorize(rows, cats, ppl):
    out = []
    for r in rows:
        d = dict(r)
        d["color"] = color_for(r, cats, ppl)
        if "person_id" in d:
            expand(d)
        out.append(d)
    return out


@router.get("/dashboard")
def dashboard():
    today = date.today().isoformat()
    with get_db() as conn:
        cats_map, ppl_map = build_lookups(conn)
        people = [dict(r) for r in conn.execute("SELECT * FROM people")]
        categories = [dict(r) for r in conn.execute("SELECT * FROM categories ORDER BY name")]
        chores = _colorize(conn.execute(
            "SELECT * FROM chores WHERE done=0 ORDER BY due_date"), cats_map, ppl_map)
        meals = _colorize(conn.execute(
            "SELECT * FROM meals WHERE date>=? ORDER BY date, slot", (today,)), cats_map, ppl_map)
        todos = _colorize(conn.execute(
            "SELECT * FROM todos WHERE done=0 ORDER BY created_at DESC"), cats_map, ppl_map)
        from .groceries import purge_got
        purge_got(conn)
        groceries = _colorize(conn.execute(
            "SELECT * FROM groceries ORDER BY got, created_at DESC"), cats_map, ppl_map)
        from .routines import list_routines, list_countdowns
        routines = list_routines(conn, only_today=True)
        countdowns = list_countdowns(conn)
    return {"people": people, "categories": categories, "chores": chores,
            "meals": meals, "todos": todos, "groceries": groceries, "today": today,
            "routines": routines, "countdowns": countdowns}
