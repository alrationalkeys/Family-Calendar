"""One flat JSON of 'the family's day' for Home Assistant to ingest as sensors
(REST sensor pointing at /api/summary — snippet in docs/home-assistant-setup.md §J).
Lets HA automations react to FamilyHub: flash the porch light before the next event,
pause the TV when chores aren't done, say 'dinner tonight' through the speakers."""
from datetime import date, datetime
from fastapi import APIRouter
from ..db import get_db

router = APIRouter()


@router.get("")
def summary():
    today = date.today().isoformat()
    now = datetime.now()
    out = {"date": today, "next_event": None, "next_event_at": None, "next_event_in_min": None,
           "events_today": 0, "chores_left": 0, "chores_by_person": {}, "todos": 0,
           "groceries": 0, "dinner": None, "routines_left": 0, "next_countdown": None,
           "next_countdown_days": None, "stars": {}}
    try:
        from .calendar import events as cal_events
        evs = [e for e in cal_events(days=1, back=0).get("events", [])
               if (e.get("start") or "").startswith(today) and not str(e.get("title", "")).startswith("[sync error")]
        out["events_today"] = len(evs)
        for e in sorted(evs, key=lambda x: x["start"]):
            if e.get("all_day"):
                continue
            try:
                st = datetime.fromisoformat(e["start"].replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                continue
            if st >= now:
                out["next_event"] = e["title"]; out["next_event_at"] = e["start"]
                out["next_event_in_min"] = int((st - now).total_seconds() // 60)
                break
    except Exception:
        pass
    with get_db() as conn:
        rows = conn.execute("SELECT p.name, COUNT(*) c FROM chores ch LEFT JOIN people p ON p.id=ch.person_id "
                            "WHERE ch.done=0 AND (ch.due_date IS NULL OR ch.due_date<=?) GROUP BY p.name", (today,)).fetchall()
        out["chores_by_person"] = {(r["name"] or "unassigned"): r["c"] for r in rows}
        out["chores_left"] = sum(out["chores_by_person"].values())
        out["todos"] = conn.execute("SELECT COUNT(*) c FROM todos WHERE done=0").fetchone()["c"]
        out["groceries"] = conn.execute("SELECT COUNT(*) c FROM groceries WHERE got=0").fetchone()["c"]
        d = conn.execute("SELECT title FROM meals WHERE date=? AND slot='dinner'", (today,)).fetchone()
        out["dinner"] = d["title"] if d else None
        for r in conn.execute("SELECT p.name, COALESCE(SUM(l.stars),0) s FROM people p LEFT JOIN reward_ledger l ON l.person_id=p.id GROUP BY p.id"):
            out["stars"][r["name"]] = r["s"]
        for r in conn.execute("SELECT title, date FROM countdowns WHERE date>=? ORDER BY date LIMIT 1", (today,)):
            out["next_countdown"] = r["title"]
            out["next_countdown_days"] = (date.fromisoformat(r["date"]) - date.today()).days
        try:
            from .routines import list_routines
            out["routines_left"] = sum(1 for r in list_routines(conn, only_today=True) if not r["complete"])
        except Exception:
            pass
    return out
