"""Login/auth probe endpoints for the frontend gate.

    GET  /api/auth/status   is auth on? are reads locked? (always reachable)
    POST /api/auth/login    {pin} -> {ok:true} if correct (validates + lockout)

Both are exempt from pin_guard (see app/auth.EXEMPT_PATHS) so the login screen
can load and submit. /login still runs the same constant-time compare + per-IP
lockout as every other protected request.
"""
from fastapi import APIRouter, Request
from .. import auth

router = APIRouter()


@router.get("/status")
def status():
    on = bool(auth.PIN)
    return {"auth": on, "lock_reads": bool(on and auth.LOCK_READS)}


@router.post("/login")
def login(payload: dict, request: Request):
    if not auth.PIN:
        return {"ok": True}                     # auth disabled, nothing to unlock
    auth.verify(request, (payload or {}).get("pin", ""))   # raises on bad/locked
    return {"ok": True}
