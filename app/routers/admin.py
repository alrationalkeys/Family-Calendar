"""Housekeeping the phone app can trigger.
    POST /api/admin/clear-demo   wipe the sample family so the real one can go in.
Also sets settings.demo_cleared so SEED_DEMO never re-seeds on restart."""
import json
from fastapi import APIRouter, HTTPException
from ..db import get_db

router = APIRouter()
TABLES = ["routine_log", "routines", "countdowns", "mail_imports", "notifications", "reward_ledger",
          "rewards", "local_events", "meals", "groceries", "todos", "chores", "categories", "people"]


@router.get("/dbinfo")
def dbinfo():
    """Where is the database and is it on a persistent disk? (open /api/admin/dbinfo)"""
    import os
    from ..db import DB_PATH
    path = os.path.abspath(DB_PATH)
    d = os.path.dirname(path)
    info = {"db_path": path, "exists": os.path.exists(path),
            "size_bytes": os.path.getsize(path) if os.path.exists(path) else 0,
            "dir_is_mount": os.path.ismount(d),
            "env_FAMILYHUB_DB": os.environ.get("FAMILYHUB_DB"),
            "env_SEED_DEMO": os.environ.get("SEED_DEMO"),
            "persistent": os.path.ismount(d) or d.startswith("/data")}
    try:
        with get_db() as conn:
            info["people"] = conn.execute("SELECT COUNT(*) c FROM people").fetchone()["c"]
            info["sources"] = conn.execute("SELECT COUNT(*) c FROM cal_sources").fetchone()["c"]
            info["settings_keys"] = [r["key"] for r in conn.execute("SELECT key FROM settings")]
            info["todos"] = conn.execute("SELECT COUNT(*) c FROM todos").fetchone()["c"]
    except Exception as e:
        info["db_error"] = str(e)
    info["verdict"] = ("OK — on the volume" if info["persistent"] else
                       "NOT persistent: FAMILYHUB_DB must point inside the mounted volume (e.g. /data/familyhub.db)")
    return info


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
