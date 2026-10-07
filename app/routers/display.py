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


@router.get("/state")
def state():
    return display_svc.tick()      # tick() self-heals the backlight, then returns state


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
