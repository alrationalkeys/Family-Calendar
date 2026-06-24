"""
Central color resolution. One rule, used everywhere so colors stay consistent
across the calendar, chores, to-dos, groceries, and meals.

Order: explicit item color -> category color -> person color -> default.
"""
from ..db import DEFAULT_COLOR


def resolve(item_color=None, category_color=None, person_color=None):
    return item_color or category_color or person_color or DEFAULT_COLOR


def build_lookups(conn):
    """Return {category_id: color} and {person_id: color} dicts for fast joins."""
    cats = {r["id"]: r["color"] for r in conn.execute("SELECT id,color FROM categories")}
    ppl = {r["id"]: r["color"] for r in conn.execute("SELECT id,color FROM people")}
    return cats, ppl


def color_for(row, cats, ppl):
    """Resolve color for a sqlite row that may have color/category_id/person_id."""
    keys = row.keys() if hasattr(row, "keys") else row
    item = row["color"] if "color" in keys else None
    cat = cats.get(row["category_id"]) if "category_id" in keys else None
    per = ppl.get(row["person_id"]) if "person_id" in keys else None
    return resolve(item, cat, per)
