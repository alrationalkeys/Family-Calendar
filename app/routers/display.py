"""Display power endpoints — scheduled screen-off + wake webhook.

    GET  /api/display/state    current power state (wall polls this)
    POST /api/display/wake     wake now (PIR sensor / Home Assistant webhook)
    POST /api/display/sleep    force off now
    GET  /api/display/config   schedule settings
    PUT  /api/display/config   update schedule settings
"""
from fastapi import APIRouter
from ..services import display_svc

router = APIRouter()

# "Reload the wall" from the phone: bump a token; the wall polls /state every 20 s
# and reloads its page when the token changes (no keyboard/SSH needed after a git pull).
import time
_reload_token = int(time.time())


@router.get("/state")
def state():
    st = display_svc.tick()        # tick() self-heals the backlight, then returns state
    st["reload_token"] = _reload_token
    return st


# ---- wall speaker volume (the C3's default output = the USB bar) --------------
# Uses PipeWire's wpctl as the kiosk user. The familyhub service runs as that user, so the
# user bus is reachable once XDG_RUNTIME_DIR is set.
import os
import re
import subprocess


def _wpctl(*args) -> str:
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return subprocess.run(["wpctl", *args], capture_output=True, text=True, timeout=5, env=env).stdout


def _get_volume() -> int | None:
    try:
        m = re.search(r"Volume:\s*([0-9.]+)", _wpctl("get-volume", "@DEFAULT_AUDIO_SINK@"))
        return round(float(m.group(1)) * 100) if m else None
    except Exception:
        return None


def _sinks() -> list[str]:
    """Every audio output PipeWire knows about (ids), so a volume change lands on the
    speaker bar even when the default sink points at the screen's HDMI audio."""
    try:
        out = _wpctl("status")
        block = out.split("Sinks:", 1)[1].split("Sources:", 1)[0] if "Sinks:" in out else ""
        ids = re.findall(r"^\s*[│├└─\s]*\*?\s*(\d+)\.", block, flags=re.M)
        return ids or ["@DEFAULT_AUDIO_SINK@"]
    except Exception:
        return ["@DEFAULT_AUDIO_SINK@"]


def _set_all_sinks(target: int):
    for sid in _sinks():
        _wpctl("set-volume", sid, f"{target/100:.2f}")
        _wpctl("set-mute", sid, "0")


@router.get("/volume")
def get_volume():
    return {"percent": _get_volume()}


@router.post("/volume")
def set_volume(payload: dict):
    """{delta: ±N} or {percent: N}. Clamped 0–100. Returns the new level."""
    p = payload or {}
    cur = _get_volume()
    if cur is None:
        return {"percent": None, "error": "no mixer (wpctl) on this box"}
    if "percent" in p:
        target = int(p["percent"])
    else:
        target = cur + int(p.get("delta", 0))
    target = max(0, min(100, target))
    try:
        _set_all_sinks(target)
    except Exception as e:
        return {"percent": cur, "error": str(e)}
    return {"percent": _get_volume() if _get_volume() is not None else target}


@router.post("/reload")
def reload_wall():
    global _reload_token
    _reload_token = int(time.time() * 1000)
    return {"ok": True, "reload_token": _reload_token}


@router.post("/wake")
def wake():
    return display_svc.wake()


@router.post("/sleep")
def sleep():
    return display_svc.sleep_now()


@router.get("/config")
def get_config():
    return display_svc.get_config()


@router.put("/config")
def put_config(payload: dict):
    return display_svc.set_config(payload)
