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


# ---- self-update from the phone --------------------------------------------
# POST /api/admin/update pulls the repo, installs requirements, then exits the
# process; systemd (Restart=always) brings it back on the new code and the wall
# page reloads itself via the display reload token. No sudo, no keyboard.
import os
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_upd = {"running": False, "log": "", "started": None, "finished": None, "changed": None, "error": None}


def _git(*args, timeout=30):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)


@router.get("/version")
def version(check: bool = False):
    """What code is the wall running, and (check=1) is there something newer upstream?"""
    out = {"root": ROOT, "git": os.path.isdir(os.path.join(ROOT, ".git"))}
    if not out["git"]:
        return out
    try:
        r = _git("log", "-1", "--format=%h|%cs|%s")
        h, d, s = (r.stdout.strip().split("|", 2) + ["", "", ""])[:3]
        out.update({"commit": h, "date": d, "subject": s})
        out["branch"] = _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if check:
            _git("fetch", "-q", "origin", out["branch"], timeout=25)
            behind = _git("rev-list", "--count", f"HEAD..origin/{out['branch']}").stdout.strip()
            out["behind"] = int(behind or 0)
            r2 = _git("log", "-1", "--format=%h|%cs|%s", f"origin/{out['branch']}")
            h2, d2, s2 = (r2.stdout.strip().split("|", 2) + ["", "", ""])[:3]
            out["latest"] = {"commit": h2, "date": d2, "subject": s2}
    except Exception as e:
        out["error"] = str(e)
    out["update"] = {k: v for k, v in _upd.items() if k != "log"}
    return out


def _do_update():
    log = []
    try:
        before = _git("rev-parse", "HEAD").stdout.strip()
        r = _git("pull", "--ff-only", "-q", timeout=120)
        log.append((r.stdout + r.stderr).strip())
        if r.returncode != 0:
            raise RuntimeError("git pull failed: " + (r.stderr.strip() or r.stdout.strip()))
        after = _git("rev-parse", "HEAD").stdout.strip()
        _upd["changed"] = before != after
        pip = os.path.join(os.path.dirname(sys.executable), "pip")
        if os.path.exists(pip) and os.path.exists(os.path.join(ROOT, "requirements.txt")):
            r = subprocess.run([pip, "install", "-q", "-r", "requirements.txt"], cwd=ROOT,
                               capture_output=True, text=True, timeout=600)
            log.append((r.stdout + r.stderr).strip()[-800:])
        _upd["log"] = "\n".join(x for x in log if x)
        _upd["finished"] = time.time()
        _upd["running"] = False
        # restart onto the new code (systemd Restart=always). Give the status reply time to leave.
        if _upd["changed"]:
            time.sleep(1.5)
            os._exit(0)
    except Exception as e:
        _upd.update({"error": str(e), "running": False, "finished": time.time(), "log": "\n".join(log)})


@router.post("/update")
def update():
    """Pull + install + restart. Returns immediately; poll /version until the commit changes."""
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        raise HTTPException(400, "not a git checkout")
    if _upd["running"]:
        return {"started": False, "reason": "already running"}
    _upd.update({"running": True, "started": time.time(), "finished": None, "changed": None, "error": None, "log": ""})
    threading.Thread(target=_do_update, daemon=True).start()
    return {"started": True}


@router.post("/restart")
def restart():
    """Just restart the server (systemd brings it back in ~3 s)."""
    threading.Timer(1.0, lambda: os._exit(0)).start()
    return {"ok": True}


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
