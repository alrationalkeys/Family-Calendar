"""
Optional simple PIN auth. Off by default (LAN use). Turn on by setting
FAMILYHUB_PIN in the environment; then write endpoints require an X-FH-PIN header.
The wall display (read-only dashboard/calendar GETs) stays open so it always shows.

This is deliberately lightweight — a shared family PIN, not per-user accounts —
because the threat model is "someone else on our wifi," not the public internet.
For public exposure, put it behind Tailscale (see README) rather than relying on this.
"""
import os
from fastapi import Request, HTTPException

PIN = os.getenv("FAMILYHUB_PIN")  # None => auth disabled

# write methods that require the PIN when auth is enabled
PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
# paths that stay open even for writes (e.g. toggling a chore from the wall)
OPEN_PREFIXES = ()


async def pin_guard(request: Request):
    if not PIN:
        return  # auth disabled
    if request.method not in PROTECTED_METHODS:
        return
    supplied = request.headers.get("X-FH-PIN")
    if supplied != PIN:
        raise HTTPException(status_code=401, detail="PIN required")
