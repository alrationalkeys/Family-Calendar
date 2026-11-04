"""Routines — kids' (or anyone's) step-by-step checklists ("Morning: get dressed,
brush teeth, pack bag") that reset every day, with an optional timer per step
and stars when the whole routine is finished. The Skylight "Routines" feature.

Also hosts countdowns ("12 days until Disney") since they're tiny and both are
per-family motivational widgets.

routines.steps is JSON: [{"title": "Brush teeth", "minutes": 2, "emoji": "🪥"}, ...]
routines.days is a comma list of weekday abbreviations ("Mon,Tue,...") or "" for every day.
"""
import json
from datetime import date, datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..db import get_db

router = APIRouter()
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class Step(BaseModel):
    title: str
    minutes: int | None = None
    emoji: str | None = None


class Routine(BaseModel):
    name: str
    emoji: str | None = None
    person_id: int | None = None
    time_of_day: str = "morning"      # morning | afternoon | bedtime | any
    days: str = ""                    # "" = every day
    steps: list[Step] = []
    stars: int = 0


class Countdown(BaseModel):
    title: str
    date: str                         # YYYY-MM-DD
    emoji: str | None = None
    color: str | None = None
    person_id: int | None = None


def _today():
    return date.today().isoformat()


def _runs_today(days: str, d: date | None = None) -> bool:
    if not days:
        return True
    d = d or date.today()
    return DAYS[d.weekday()] in [x.strip() for x in days.split(",") if x.strip()]


def _shape(conn, r, today):
    done = [row["step_idx"] for row in conn.execute(
        "SELECT step_idx FROM routine_log WHERE routine_id=? AND date=?", (r["id"], today))]
    steps = json.loads(r["steps"] or "[]")
    person = conn.execute("SELECT name,color FROM people WHERE id=?", (r["person_id"],)).fetchone() \
        if r["person_id"] else None
    return {
        "id": r["id"], "name": r["name"], "emoji": r["emoji"] or "", "person_id": r["person_id"],
        "person": person["name"] if person else None, "color": person["color"] if person else None,
        "time_of_day": r["time_of_day"], "days": r["days"] or "", "stars": r["stars"] or 0,
        "steps": steps, "done": sorted(done),
        "complete": bool(steps) and len(set(done)) >= len(steps),
        "today": _runs_today(r["days"] or ""),
    }


def list_routines(conn, only_today=False):
    today = _today()
    out = [_shape(conn, r, today) for r in conn.execute(
        "SELECT * FROM routines ORDER BY CASE time_of_day WHEN 'morning' THEN 0 WHEN 'afternoon' THEN 1 "
        "WHEN 'bedtime' THEN 2 ELSE 3 END, name")]
    return [r for r in out if r["today"]] if only_today else out


def list_countdowns(conn):
    today = date.today()
    out = []
    for r in conn.execute("SELECT * FROM countdowns ORDER BY date"):
        try:
            d = date.fromisoformat(r["date"])
        except ValueError:
            continue
        left = (d - today).days
        if left < -1:          # drop the day after it happened
            continue
        person = conn.execute("SELECT color FROM people WHERE id=?", (r["person_id"],)).fetchone() \
            if r["person_id"] else None
        out.append({"id": r["id"], "title": r["title"], "date": r["date"], "emoji": r["emoji"] or "",
                    "color": r["color"] or (person["color"] if person else None),
                    "person_id": r["person_id"], "days_left": left})
    return out


# ---- routines ----------------------------------------------------------------

@router.get("/")
def get_routines(today: bool = False):
    with get_db() as conn:
        return list_routines(conn, only_today=today)


@router.post("/")
def add_routine(r: Routine):
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO routines (name, emoji, person_id, time_of_day, days, steps, stars) VALUES (?,?,?,?,?,?,?)",
            (r.name.strip(), r.emoji, r.person_id, r.time_of_day, r.days,
             json.dumps([s.model_dump() for s in r.steps]), r.stars))
        return {"id": cur.lastrowid}


@router.put("/{rid}")
def update_routine(rid: int, r: Routine):
    with get_db() as conn:
        conn.execute(
            "UPDATE routines SET name=?, emoji=?, person_id=?, time_of_day=?, days=?, steps=?, stars=? WHERE id=?",
            (r.name.strip(), r.emoji, r.person_id, r.time_of_day, r.days,
             json.dumps([s.model_dump() for s in r.steps]), r.stars, rid))
        return {"id": rid}


@router.delete("/{rid}")
def delete_routine(rid: int):
    with get_db() as conn:
        conn.execute("DELETE FROM routine_log WHERE routine_id=?", (rid,))
        conn.execute("DELETE FROM routines WHERE id=?", (rid,))
        return {"deleted": rid}


@router.post("/{rid}/step/{idx}")
def toggle_step(rid: int, idx: int):
    """Tick / untick one step for today. Finishing the last step awards the
    routine's stars to its person — once per day."""
    today = _today()
    with get_db() as conn:
        r = conn.execute("SELECT * FROM routines WHERE id=?", (rid,)).fetchone()
        if not r:
            raise HTTPException(404, "no such routine")
        steps = json.loads(r["steps"] or "[]")
        if idx < 0 or idx >= len(steps):
            raise HTTPException(400, "bad step")
        was_complete = _shape(conn, r, today)["complete"]
        exists = conn.execute("SELECT 1 FROM routine_log WHERE routine_id=? AND date=? AND step_idx=?",
                              (rid, today, idx)).fetchone()
        if exists:
            conn.execute("DELETE FROM routine_log WHERE routine_id=? AND date=? AND step_idx=?", (rid, today, idx))
        else:
            conn.execute("INSERT INTO routine_log (routine_id, date, step_idx, done_at) VALUES (?,?,?,?)",
                         (rid, today, idx, datetime.now().isoformat()))
        shaped = _shape(conn, r, today)
        stars = 0
        if shaped["complete"] and not was_complete and r["stars"] and r["person_id"]:
            already = conn.execute(
                "SELECT 1 FROM reward_ledger WHERE person_id=? AND reason=? AND date(at,'localtime')=?",
                (r["person_id"], f"routine: {r['name']}", today)).fetchone()
            if not already:
                conn.execute("INSERT INTO reward_ledger (person_id,stars,reason) VALUES (?,?,?)",
                             (r["person_id"], r["stars"], f"routine: {r['name']}"))
                stars = r["stars"]
        shaped["stars_earned"] = stars
        return shaped


@router.post("/{rid}/reset")
def reset_routine(rid: int):
    with get_db() as conn:
        conn.execute("DELETE FROM routine_log WHERE routine_id=? AND date=?", (rid, _today()))
        return {"id": rid, "reset": True}


# ---- countdowns --------------------------------------------------------------

@router.get("/countdowns")
def get_countdowns():
    with get_db() as conn:
        return list_countdowns(conn)


@router.post("/countdowns")
def add_countdown(c: Countdown):
    date.fromisoformat(c.date)   # validate
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO countdowns (title, date, emoji, color, person_id) VALUES (?,?,?,?,?)",
            (c.title.strip(), c.date, c.emoji, c.color, c.person_id))
        return {"id": cur.lastrowid}


@router.put("/countdowns/{cid}")
def update_countdown(cid: int, c: Countdown):
    date.fromisoformat(c.date)
    with get_db() as conn:
        conn.execute("UPDATE countdowns SET title=?, date=?, emoji=?, color=?, person_id=? WHERE id=?",
                     (c.title.strip(), c.date, c.emoji, c.color, c.person_id, cid))
        return {"id": cid}


@router.delete("/countdowns/{cid}")
def delete_countdown(cid: int):
    with get_db() as conn:
        conn.execute("DELETE FROM countdowns WHERE id=?", (cid,))
        return {"deleted": cid}
