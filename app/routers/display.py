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
