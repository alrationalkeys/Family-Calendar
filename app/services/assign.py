"""
Several people on one item (to-do, chore, calendar event).

`person_ids` (TEXT "1,3") holds everyone; `person_id` stays = the first one, so colors (services/color.py),
voice, summaries and older code keep working untouched.
"""
from __future__ import annotations


def norm(person_id=None, person_ids=None) -> tuple[int | None, str | None]:
    """-> (first id, "1,3" or None). person_ids wins when given; otherwise the single person_id."""
    ids: list[int] = []
    for x in (person_ids if person_ids is not None else ([person_id] if person_id else [])):
        try:
            v = int(x)
        except (TypeError, ValueError):
            continue
        if v and v not in ids:
            ids.append(v)
    return (ids[0] if ids else None), (",".join(map(str, ids)) if ids else None)


def ids_of(row) -> list[int]:
    """Everyone on a row (dict or sqlite Row)."""
    try:
        raw = row["person_ids"]
    except (KeyError, IndexError):
        raw = None
    out = [int(x) for x in str(raw or "").split(",") if x.strip().isdigit()]
    if not out:
        try:
            if row["person_id"]:
                out = [int(row["person_id"])]
        except (KeyError, IndexError):
            pass
    return out


def expand(d: dict) -> dict:
    """Add a parsed `person_ids` list to an item dict for the API."""
    d["person_ids"] = ids_of(d)
    return d


def has(pid_col="person_id", ids_col="person_ids") -> str:
    """SQL fragment: this person is on the row (one '?' parameter, used twice -> pass pid twice)."""
    return f"({pid_col}=? OR (','||COALESCE({ids_col},'')||',') LIKE '%,'||?||',%')"


def remove_person(conn, pid: int):
    """Take someone off every item (person deleted)."""
    for table in ("todos", "chores", "local_events"):
        for r in conn.execute(f"SELECT id, person_id, person_ids FROM {table} WHERE {has()}", (pid, str(pid))).fetchall():
            ids = [i for i in ids_of(r) if i != pid]
            first, joined = norm(None, ids)
            conn.execute(f"UPDATE {table} SET person_id=?, person_ids=? WHERE id=?", (first, joined, r["id"]))
