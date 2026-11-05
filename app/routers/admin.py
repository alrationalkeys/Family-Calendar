"""Housekeeping the phone app can trigger.
    POST /api/admin/clear-demo   wipe the sample family so the real one can go in.
Also sets settings.demo_cleared so SEED_DEMO never re-seeds on restart."""
import json
from fastapi import APIRouter, HTTPException
from ..db import get_db

router = APIRouter()
TABLES = ["routine_log", "routines", "countdowns", "mail_imports", "notifications", "reward_ledger",
          "rewards", "local_events", "meals", "groceries", "todos", "chores", "categories", "people"]


@router.post("/clear-demo")
def clear_demo(payload: dict | None = None):
    if not (payload or {}).get("confirm"):
        raise HTTPException(400, "send {confirm: true}")
    counts = {}
    with get_db() as conn:
        for t in TABLES:
            counts[t] = conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
            conn.execute(f"DELETE FROM {t}")
        conn.execute("INSERT INTO settings (key,value) VALUES ('demo_cleared','1') "
                     "ON CONFLICT(key) DO UPDATE SET value='1'")
    return {"cleared": counts}
