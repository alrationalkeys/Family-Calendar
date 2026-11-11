"""
Optional PIN auth. Off by default (LAN use). Turn on by setting FAMILYHUB_PIN.

Two levels:
  - FAMILYHUB_PIN set            -> *writes* (POST/PUT/DELETE/PATCH) need the PIN.
                                     Reads stay open so the wall always shows.
  - FAMILYHUB_LOCK_READS=1 too   -> *reads* need the PIN as well, so nobody can
                                     even view the calendar without unlocking.
                                     Use this when the app is on a public URL
                                     (e.g. Railway). See docs/railway-deploy.md.

The PIN travels in an `X-FH-PIN` header (the frontend attaches it from a small
login gate; the static app shell itself stays open so the login screen can load).

Hardened for the day this controls real devices (alarm/locks via Home Assistant):
  - constant-time PIN compare (no timing leak)
  - per-IP lockout after repeated *wrong* guesses, to stop brute-forcing a short
    PIN. A missing PIN is not counted as a guess, so idle background polling from
    a not-yet-unlocked page can't lock anyone out.

Still a shared family PIN, not per-user accounts — the threat model is "someone
with the link / on our wifi." For strong privacy, prefer Tailscale + HTTPS
(see docs/hardening.md) over exposing a public URL at all.
"""
import os
import time
import hmac
from collections import defaultdict
from fastapi import Request, HTTPException

PIN = os.getenv("FAMILYHUB_PIN")  # None => auth disabled


def _truthy(v):
    return (v or "").strip().lower() in ("1", "true", "yes", "on")


# Lock reads too (view requires the PIN), not just writes.
LOCK_READS = _truthy(os.getenv("FAMILYHUB_LOCK_READS"))

PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
# These API paths must stay reachable without a PIN so the login screen works:
# a probe to learn whether auth is on, and the login endpoint itself.
EXEMPT_PATHS = {"/api/auth/status", "/api/auth/login"}

MAX_FAILS = int(os.getenv("FAMILYHUB_MAX_FAILS", "5"))      # wrong guesses before lockout
LOCKOUT_SECONDS = int(os.getenv("FAMILYHUB_LOCKOUT", "60"))  # how long a lockout lasts
WINDOW = 300                                                 # count failures within 5 min

_fails = defaultdict(list)   # ip -> [failure timestamps]
_locked = {}                 # ip -> unlock_time


def _client_ip(request: Request) -> str:
    # behind a reverse proxy (Caddy / Railway), the real client is the first
    # X-Forwarded-For hop
    xff = request.headers.get("X-Forwarded-For") if os.getenv("FAMILYHUB_TRUST_PROXY") == "1" else None
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def verify(request: Request, supplied: str):
    """Shared check: enforce lockout, constant-time compare, record failures.
    Returns None on success; raises HTTPException(429/401) otherwise.

    A blank `supplied` is treated as 'not logged in yet' — rejected with 401 but
    NOT counted toward the lockout (so polling from a gated page is harmless).
    Only a non-empty wrong guess counts as a brute-force attempt.
    """
    ip = _client_ip(request)
    now = time.time()

    unlock = _locked.get(ip)
    if unlock and now < unlock:
        raise HTTPException(status_code=429, detail=f"Locked out, try again in {int(unlock - now)}s")

    if PIN and hmac.compare_digest(supplied or "", PIN):
        _fails.pop(ip, None)                    # success clears the record
        _locked.pop(ip, None)
        return

    if not supplied:
        # no PIN offered yet — ask for one, but don't treat it as a guess
        raise HTTPException(status_code=401, detail="PIN required")

    # record the wrong guess, prune old ones, lock out if over the limit
    recent = [t for t in _fails[ip] if now - t < WINDOW]
    recent.append(now)
    _fails[ip] = recent
    if len(recent) >= MAX_FAILS:
        _locked[ip] = now + LOCKOUT_SECONDS
        _fails.pop(ip, None)
        raise HTTPException(status_code=429, detail="Too many attempts; locked out")
    raise HTTPException(status_code=401, detail="Incorrect PIN")


async def pin_guard(request: Request):
    if not PIN:
        return                                  # auth disabled
    if request.url.path in EXEMPT_PATHS:
        return                                  # login probe / login endpoint
    needs_pin = (request.method in PROTECTED_METHODS) or LOCK_READS
    if not needs_pin:
        return                                  # reads stay open (writes-only mode)
    verify(request, request.headers.get("X-FH-PIN") or "")
