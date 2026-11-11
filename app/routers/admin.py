"""Housekeeping the phone app can trigger.
    POST /api/admin/clear-demo   wipe the sample family so the real one can go in.
Also sets settings.demo_cleared so SEED_DEMO never re-seeds on restart."""
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
    try:
        from ..services.doorbell import base_url
        out["address"] = base_url()                 # the LAN address phones/TVs use
    except Exception:
        pass
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


def _write_env(key: str, value: str | None):
    """Set (or remove, value=None) KEY=value in ROOT/.env, keeping every other line as is."""
    path = os.path.join(ROOT, ".env")
    lines = []
    if os.path.exists(path):
        with open(path) as f:
            lines = [l for l in f.read().splitlines() if not l.strip().startswith(key + "=")]
    if value is not None:
        lines.append(f"{key}={value}")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


@router.get("/pin")
def pin_status():
    from .. import auth
    return {"on": bool(auth.PIN)}


@router.post("/pin")
def set_pin(payload: dict):
    """Turn the family PIN on/change it ({pin: "1234"}) or off ({pin: ""}). Takes effect at once and is
    saved to .env for restarts. When a PIN is already on, this request itself needs it (pin_guard)."""
    import re as _re
    from .. import auth
    pin = str((payload or {}).get("pin", "")).strip()
    if pin and not _re.fullmatch(r"\d{4,8}", pin):
        raise HTTPException(400, "Use 4 to 8 digits")
    try:
        _write_env("FAMILYHUB_PIN", pin or None)
    except OSError as e:
        raise HTTPException(500, f"Couldn't save .env: {e}")
    auth.PIN = pin or None
    if pin:
        os.environ["FAMILYHUB_PIN"] = pin
    else:
        os.environ.pop("FAMILYHUB_PIN", None)
    return {"on": bool(pin)}


@router.post("/restart")
def restart():
    """Just restart the server (systemd brings it back in ~3 s)."""
    threading.Timer(1.0, lambda: os._exit(0)).start()
    return {"ok": True}


def _desktop_env() -> dict:
    """Environment to reach the wall's own desktop session (FamilyHub runs as the same user)."""
    env = dict(os.environ)
    env.setdefault("DISPLAY", ":0")
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{os.getuid()}/bus"
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    xa = os.path.expanduser("~/.Xauthority")
    if os.path.exists(xa):
        env.setdefault("XAUTHORITY", xa)
    return env


@router.post("/screen-keyboard")
def screen_keyboard(payload: dict | None = None):
    """Ubuntu's own on-screen keyboard on/off ({on: false}). GNOME ignores its setting on touchscreens, so
    "off" installs a tiny GNOME Shell extension (setup/disable-ubuntu-osk.sh); needs one restart of the wall."""
    import subprocess
    on = bool((payload or {}).get("on"))
    script = os.path.join(ROOT, "setup", "disable-ubuntu-osk.sh")
    try:
        r = subprocess.run(["bash", script] + (["--undo"] if on else []), env=_desktop_env(),
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "reason": f"couldn't run the installer: {e}"}
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    return {"ok": r.returncode == 0, "restart": True, "reason": out[-300:] or None}


def _kiosk_running() -> bool:
    import subprocess
    try:
        return subprocess.run(["pgrep", "-f", "kiosk.sh"], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@router.post("/desktop")
def to_desktop():
    """Close the full-screen wall browser so Ubuntu's desktop shows (Back to FamilyHub reopens it)."""
    import subprocess
    try:
        subprocess.run(["pkill", "-f", "kiosk.sh"], timeout=5)                 # the loop that relaunches the browser
        subprocess.run(["pkill", "-f", "familyhub-kiosk-profile"], timeout=5)  # the browser itself
    except (OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "reason": str(e)}
    return {"ok": True}


@router.post("/kiosk")
def to_kiosk():
    """Start the full-screen wall browser again (runs kiosk.sh on the wall's desktop)."""
    import subprocess
    script = os.path.join(ROOT, "kiosk.sh")
    if not os.path.exists(script):
        return {"ok": False, "reason": "kiosk.sh not found"}
    if _kiosk_running():
        return {"ok": True, "already": True}
    env = _desktop_env()
    try:
        # run it in the desktop's own session manager so a FamilyHub restart doesn't take the browser down with it
        setenv = [f"--setenv={k}={env[k]}" for k in ("DISPLAY", "XAUTHORITY", "DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "HOME", "PATH")
                  if env.get(k)]
        r = subprocess.run(["systemd-run", "--user", "--collect", "--unit", f"familyhub-kiosk-{int(time.time())}", *setenv,
                            "bash", script], env=env, capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            raise OSError(r.stderr.strip() or "systemd-run failed")
    except (OSError, subprocess.SubprocessError):
        try:
            subprocess.Popen(["bash", script], env=env, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as e:
            return {"ok": False, "reason": str(e)}
    return {"ok": True}


@router.post("/reboot")
def reboot():
    """Restart the wall computer (to finish the keyboard change, or when something's stuck)."""
    import subprocess
    for cmd in (["systemctl", "reboot"], ["sudo", "-n", "reboot"]):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return {"ok": True}
        except (OSError, subprocess.SubprocessError):
            continue
    return {"ok": False, "reason": "Ubuntu wouldn't let FamilyHub restart it. Press the mini PC's power button once, wait for it to turn off, then press it again."}


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
