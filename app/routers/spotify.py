"""FamilyHub's own Spotify link — see services/spotify_web.py.

  GET  /api/spotify/status       {configured, linked, user, wall_online, ...}
  GET  /api/spotify/login        {url} to open in a browser (one-time)
  GET  /api/spotify/callback     Spotify redirects here (works when done on the wall itself)
  POST /api/spotify/code         {text}: pasted callback URL or bare code (done from a phone/laptop)
  POST /api/spotify/unlink
  GET  /api/spotify/token        access token for the wall's Web Playback SDK player
  POST /api/spotify/device       {device_id, name} the wall registers its player
  GET  /api/spotify/devices · /state · /playlists
  POST /api/spotify/cmd          {action: play|pause|next|prev|volume|transfer|say, value?, device?}
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from ..services import spotify_web as sw

router = APIRouter()


@router.get("/status")
def status():
    return sw.status()


@router.get("/login")
def login(redirect: bool = False):
    if not sw.configured():
        raise HTTPException(400, "Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env first (same values you gave Home Assistant).")
    url = sw.authorize_url()
    return RedirectResponse(url) if redirect else {"url": url, "redirect_uri": sw.redirect_uri()}


@router.get("/callback", response_class=HTMLResponse)
def callback(code: str = "", state: str = "", error: str = ""):
    if error or not code:
        return HTMLResponse(f"<h2>Spotify said: {error or 'no code'}</h2><p>Go back to the phone app and try again.</p>", status_code=400)
    try:
        cur = sw.exchange_code(code, state or None)
    except Exception as e:
        return HTMLResponse(f"<h2>Couldn't finish: {e}</h2>", status_code=400)
    return HTMLResponse(f"<h2>Spotify connected{(' as ' + cur['user']) if cur.get('user') else ''}.</h2><p>You can close this tab. The wall will show up as a Spotify device within a minute.</p>")


@router.post("/code")
def code(payload: dict):
    text = (payload or {}).get("text", "")
    if "accounts.spotify.com" in text:
        raise HTTPException(400, "That's the login page link. Log in and tap Agree first, then paste the address of the page Spotify sends you to AFTER that — it starts with http://127.0.0.1:8000/api/spotify/callback?code=")
    code, state = sw.code_from_text(text)
    if not code or "code=" not in text and len(code) < 40:
        raise HTTPException(400, "Paste the full address of the page Spotify sent you to after you tapped Agree (starts with http://127.0.0.1:8000/…)")
    try:
        cur = sw.exchange_code(code, None)      # state can't be verified for a hand-pasted URL
    except Exception as e:
        raise HTTPException(400, f"Spotify rejected it: {e}")
    return {"ok": True, "user": cur.get("user"), "product": cur.get("product")}


@router.post("/unlink")
def unlink():
    sw.unlink()
    return {"ok": True}


@router.get("/token")
def token():
    tok = sw.access_token()
    if not tok:
        raise HTTPException(404, "Spotify not linked")
    return {"access_token": tok}


@router.post("/device")
def device(payload: dict):
    p = payload or {}
    if not p.get("device_id"):
        raise HTTPException(400, "device_id required")
    sw.set_wall_device(p["device_id"], p.get("name") or "Kitchen Wall")
    return {"ok": True}


_player_log: list[dict] = []


@router.post("/player_log")
def player_log(payload: dict):
    """The wall page reports what Spotify's Web Playback SDK is doing (drm / sdk / ready / errors)."""
    import time
    p = payload or {}
    _player_log.append({"t": time.strftime("%H:%M:%S"), "stage": str(p.get("stage", ""))[:40],
                        "detail": str(p.get("detail", ""))[:300]})
    del _player_log[:-30]
    return {"ok": True}


@router.get("/player_log")
def get_player_log():
    return {"log": _player_log}


@router.get("/devices")
def devices():
    return {"devices": sw.devices(), "wall": sw.wall_device()}


@router.get("/state")
def state():
    return {"playback": sw.playback()}


@router.get("/playlists")
def playlists():
    return {"playlists": sw.my_playlists()}


@router.post("/cmd")
def cmd(payload: dict):
    p = payload or {}
    a = (p.get("action") or "").lower()
    dev = p.get("device")
    if not sw.linked():
        raise HTTPException(400, "Spotify not linked — phone app → Settings → Spotify → Connect")
    try:
        if a == "say":                      # free text, same brain as the wall's voice
            import re
            words = set(re.findall(r"[a-z0-9']+", str(p.get("value", "")).lower()))
            return {"ok": True, "say": sw.voice(str(p.get("value", "")), words)}
        if a == "play":
            v = str(p.get("value", "") or "")
            if v.startswith("spotify:track:"):
                sw.play(dev, uris=[v])
            elif v:
                sw.play(dev, context_uri=v)
            else:
                sw.play(dev)
        elif a == "pause": sw.pause()
        elif a == "next": sw.next_track()
        elif a == "prev": sw.prev_track()
        elif a == "volume": sw.set_volume(int(float(p.get("value", 50))), dev)
        elif a == "transfer":
            if not dev: raise HTTPException(400, "device required")
            sw.transfer(dev)
        else:
            raise HTTPException(400, f"unknown action {a}")
        return {"ok": True}
    except RuntimeError as e:
        raise HTTPException(502, str(e))
