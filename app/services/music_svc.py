"""
Now Playing for the wall display (Echo Show 15 style music widget).

Talks to the Spotify Web API when credentials are present, and degrades
gracefully to an empty "nothing playing" state when they are not -- same
spirit as weather_svc / ai_vision: needs creds to light up, never crashes
the wall if they are missing.

To light up, set three env vars (all obtained once via Spotify's OAuth
authorization-code flow, scopes: user-read-playback-state,
user-modify-playback-state):
    SPOTIFY_CLIENT_ID
    SPOTIFY_CLIENT_SECRET
    SPOTIFY_REFRESH_TOKEN

Reads (now-playing) work with any account. Playback controls
(play/pause/next/prev) require Spotify Premium -- the API returns 403 for
free accounts, which we surface as ok=False rather than an error.
"""
import os
import json
import time
import base64
import urllib.parse
import urllib.request
import urllib.error

TOKEN_URL = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"

# Cached access token so we don't refresh on every 5s poll.
_token = {"value": None, "expires_at": 0}


def _creds():
    return (
        os.getenv("SPOTIFY_CLIENT_ID"),
        os.getenv("SPOTIFY_CLIENT_SECRET"),
        os.getenv("SPOTIFY_REFRESH_TOKEN"),
    )


def configured():
    """True when all three Spotify env vars are present."""
    return all(_creds())


def _access_token():
    """Return a valid access token, refreshing via the refresh_token if needed."""
    if _token["value"] and time.time() < _token["expires_at"]:
        return _token["value"]

    cid, secret, refresh = _creds()
    if not (cid and secret and refresh):
        return None

    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh,
    }).encode()
    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    req = urllib.request.Request(TOKEN_URL, data=body, headers={
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read())
    except Exception:
        return None

    tok = data.get("access_token")
    if not tok:
        return None
    # Refresh a minute before the real expiry to be safe.
    _token["value"] = tok
    _token["expires_at"] = time.time() + max(0, data.get("expires_in", 3600) - 60)
    return tok


def _empty(connected):
    return {
        "connected": connected,
        "is_playing": False,
        "track": None, "artist": None, "album": None,
        "art_url": None,
        "progress_ms": 0, "duration_ms": 0,
        "source": "spotify",
    }


def get_now_playing():
    """Current track state for the wall widget. Never raises."""
    if not configured():
        return _empty(False)

    tok = _access_token()
    if not tok:
        return _empty(True)

    req = urllib.request.Request(
        f"{API}/me/player/currently-playing",
        headers={"Authorization": f"Bearer {tok}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=6) as r:
            # 204 = nothing playing / no active device
            if r.status == 204 or not r.length:
                return _empty(True)
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 204:
            return _empty(True)
        return _empty(True)
    except Exception:
        return _empty(True)

    item = data.get("item") or {}
    if not item:
        return _empty(True)

    images = ((item.get("album") or {}).get("images")) or []
    art = images[0]["url"] if images else None
    artists = ", ".join(a["name"] for a in item.get("artists", []) if a.get("name"))
    return {
        "connected": True,
        "is_playing": bool(data.get("is_playing")),
        "track": item.get("name"),
        "artist": artists or None,
        "album": (item.get("album") or {}).get("name"),
        "art_url": art,
        "progress_ms": data.get("progress_ms") or 0,
        "duration_ms": item.get("duration_ms") or 0,
        "source": "spotify",
    }


def _control(method, path):
    """Send a playback command. Returns {ok, reason?}. Never raises."""
    if not configured():
        return {"ok": False, "reason": "not_configured"}
    tok = _access_token()
    if not tok:
        return {"ok": False, "reason": "auth_failed"}
    req = urllib.request.Request(
        f"{API}{path}", method=method,
        headers={"Authorization": f"Bearer {tok}", "Content-Length": "0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=6):
            return {"ok": True}
    except urllib.error.HTTPError as e:
        # 403 -> not Premium; 404 -> no active device.
        reason = {403: "premium_required", 404: "no_active_device"}.get(e.code, f"http_{e.code}")
        return {"ok": False, "reason": reason}
    except Exception:
        return {"ok": False, "reason": "error"}


def play():      return _control("PUT", "/me/player/play")
def pause():     return _control("PUT", "/me/player/pause")
def next_track(): return _control("POST", "/me/player/next")
def prev_track(): return _control("POST", "/me/player/previous")
