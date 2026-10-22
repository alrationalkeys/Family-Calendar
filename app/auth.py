"""
Optional PIN auth. Off by default (LAN use). Turn on by setting FAMILYHUB_PIN;
then write endpoints (POST/PUT/DELETE/PATCH) require an X-FH-PIN header. Reads
stay open so the wall display always shows.

Hardened for the day this controls real devices (alarm/locks via Home Assistant):
  - constant-time PIN compare (no timing leak)
  - per-IP lockout after repeated failures, to stop brute-forcing a short PIN

Still a shared family PIN, not per-user accounts — the threat model is "someone
else on our wifi." For public exposure, put it behind Tailscale + HTTPS
(see docs/hardening.md) rather than relying on this alone.
"""
import os
import time
import hmac
from collections import defaultdict
from fastapi import Request, HTTPException

PIN = os.getenv("FAMILYHUB_PIN")  # None => auth disabled

PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
MAX_FAILS = int(os.getenv("FAMILYHUB_MAX_FAILS", "5"))      # failures before lockout
LOCKOUT_SECONDS = int(os.getenv("FAMILYHUB_LOCKOUT", "60"))  # how long a lockout lasts
WINDOW = 300                                                 # count failures within 5 min

_fails = defaultdict(list)   # ip -> [failure timestamps]
_locked = {}                 # ip -> unlock_time


def _client_ip(request: Request) -> str:
    # behind the Caddy reverse proxy, the real client is the first X-Forwarded-For hop
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


async def pin_guard(request: Request):
    if not PIN:
        return                                  # auth disabled
    if request.method not in PROTECTED_METHODS:
        return                                  # reads stay open

    ip = _client_ip(request)
    now = time.time()

    unlock = _locked.get(ip)
    if unlock and now < unlock:
        raise HTTPException(status_code=429, detail=f"Locked out, try again in {int(unlock - now)}s")

    supplied = request.headers.get("X-FH-PIN") or ""
    if hmac.compare_digest(supplied, PIN):
        _fails.pop(ip, None)                    # success clears the record
        _locked.pop(ip, None)
        return

    # record the failure, prune old ones, lock out if over the limit
    recent = [t for t in _fails[ip] if now - t < WINDOW]
    recent.append(now)
    _fails[ip] = recent
    if len(recent) >= MAX_FAILS:
        _locked[ip] = now + LOCKOUT_SECONDS
        _fails.pop(ip, None)
        raise HTTPException(status_code=429, detail="Too many attempts; locked out")
    raise HTTPException(status_code=401, detail="PIN required")
