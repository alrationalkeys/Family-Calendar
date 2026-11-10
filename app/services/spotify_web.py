"""
FamilyHub's own Spotify link (Web API + Web Playback SDK) — the wall becomes an
*official* Spotify Connect device ("FamilyHub") inside its own Chromium, so
"Hey Hub, play Zach Bryan" comes out of the wall speaker with no phone involved.

Why not spotifyd/go-librespot: Spotify refuses audio keys to third-party clients
on many accounts (librespot #1649). The Web Playback SDK is Spotify's own player,
so it isn't subject to that block. Needs Premium + the developer app you made for
Home Assistant (SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET in .env).

Auth: authorization-code flow. Spotify only allows https or loopback-IP redirect
URIs, so the redirect is http://127.0.0.1:8000/api/spotify/callback. When the
login is done from a phone/laptop that page can't load — paste its address into
the phone app (POST /api/spotify/code) and we finish the exchange server-side.

Tokens live in the settings table (key spotify_auth). Never in git.
"""
from __future__ import annotations

import base64
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from ..db import get_db

KEY = "spotify_auth"
SCOPES = ("streaming user-read-email user-read-private user-read-playback-state "
          "user-modify-playback-state user-read-currently-playing playlist-read-private "
          "playlist-read-collaborative user-library-read user-top-read user-read-recently-played")
API = "https://api.spotify.com/v1"
_states: dict[str, float] = {}      # oauth state -> issued-at (anti-CSRF, 10 min)


def client_id() -> str:
    return os.getenv("SPOTIFY_CLIENT_ID", "").strip()


def client_secret() -> str:
    return os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()


def redirect_uri() -> str:
    return os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/api/spotify/callback").strip()


def configured() -> bool:
    return bool(client_id() and client_secret())


# ---------------------------------------------------------------- storage ----
def _load() -> dict:
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key=?", (KEY,)).fetchone()
        return json.loads(row["value"]) if row else {}
    except Exception:
        return {}


def _save(d: dict):
    with get_db() as conn:
        conn.execute("INSERT INTO settings (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (KEY, json.dumps(d)))


def linked() -> bool:
    return bool(_load().get("refresh_token"))


def unlink():
    _save({})


# ------------------------------------------------------------------ oauth ----
def authorize_url() -> str:
    st = secrets.token_urlsafe(16)
    _states[st] = time.time()
    q = {"client_id": client_id(), "response_type": "code", "redirect_uri": redirect_uri(),
         "scope": SCOPES, "state": st, "show_dialog": "false"}
    return "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(q)


def _token_request(data: dict) -> dict:
    body = urllib.parse.urlencode(data).encode()
    auth = base64.b64encode(f"{client_id()}:{client_secret()}".encode()).decode()
    req = urllib.request.Request("https://accounts.spotify.com/api/token", data=body, method="POST",
                                 headers={"Authorization": f"Basic {auth}",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def exchange_code(code: str, state: str | None = None) -> dict:
    if state is not None and state not in _states:
        raise ValueError("login expired — start again from the phone app")
    _states.pop(state, None)
    tok = _token_request({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()})
    cur = _load()
    cur.update({"access_token": tok["access_token"], "refresh_token": tok.get("refresh_token") or cur.get("refresh_token"),
                "expires_at": time.time() + int(tok.get("expires_in", 3600)) - 60})
    _save(cur)
    try:
        me = _api("GET", "/me") or {}
        cur["user"] = me.get("display_name") or me.get("id")
        cur["product"] = me.get("product")
        _save(cur)
    except Exception:
        pass
    return cur


def code_from_text(text: str) -> tuple[str, str | None]:
    """Accept a pasted callback URL or a bare code. -> (code, state)"""
    text = (text or "").strip()
    m = re.search(r"[?&]code=([^&\s]+)", text)
    if m:
        s = re.search(r"[?&]state=([^&\s]+)", text)
        return urllib.parse.unquote(m.group(1)), (urllib.parse.unquote(s.group(1)) if s else None)
    return text, None


def access_token() -> str | None:
    cur = _load()
    if not cur.get("refresh_token"):
        return None
    if cur.get("access_token") and time.time() < float(cur.get("expires_at", 0)):
        return cur["access_token"]
    try:
        tok = _token_request({"grant_type": "refresh_token", "refresh_token": cur["refresh_token"]})
    except urllib.error.HTTPError as e:
        if e.code in (400, 401):          # revoked / app deleted -> make the user re-link
            unlink()
        return None
    except Exception:
        return cur.get("access_token")
    cur["access_token"] = tok["access_token"]
    if tok.get("refresh_token"):
        cur["refresh_token"] = tok["refresh_token"]
    cur["expires_at"] = time.time() + int(tok.get("expires_in", 3600)) - 60
    _save(cur)
    return cur["access_token"]


# ---------------------------------------------------------------- web api ----
def _api(method: str, path: str, params: dict | None = None, body: dict | None = None):
    tok = access_token()
    if not tok:
        return None
    url = API + path + (("?" + urllib.parse.urlencode(params)) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read()
            return json.loads(raw.decode()) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            detail = ""
        raise RuntimeError(f"Spotify {e.code}: {detail or e.reason}")


def devices() -> list[dict]:
    try:
        return (_api("GET", "/me/player/devices") or {}).get("devices", [])
    except Exception:
        return []


def wall_device() -> dict | None:
    """The wall's own Web Playback device, if the wall page has registered it and Spotify sees it."""
    cur = _load()
    did = cur.get("wall_device_id")
    for d in devices():
        if did and d.get("id") == did:
            return d
    name = (cur.get("wall_device_name") or "").lower()
    for d in devices():
        if name and (d.get("name") or "").lower() == name:
            return d
    return None


def set_wall_device(device_id: str, name: str):
    cur = _load()
    cur["wall_device_id"] = device_id
    cur["wall_device_name"] = name
    _save(cur)


def playback() -> dict | None:
    try:
        p = _api("GET", "/me/player") or None
    except Exception:
        return None
    if not p:
        return None
    item = p.get("item") or {}
    return {"playing": bool(p.get("is_playing")),
            "title": item.get("name"), "artist": ", ".join(a.get("name", "") for a in item.get("artists", [])),
            "album": (item.get("album") or {}).get("name"),
            "art": ((item.get("album") or {}).get("images") or [{}])[0].get("url"),
            "device": (p.get("device") or {}).get("name"), "device_id": (p.get("device") or {}).get("id"),
            "volume": (p.get("device") or {}).get("volume_percent"), "shuffle": p.get("shuffle_state"),
            "context": (p.get("context") or {}).get("uri")}


def play(device_id: str | None = None, uris: list[str] | None = None, context_uri: str | None = None):
    body = {}
    if uris: body["uris"] = uris
    if context_uri: body["context_uri"] = context_uri
    params = {"device_id": device_id} if device_id else None
    return _api("PUT", "/me/player/play", params, body if body else None)


def pause():      return _api("PUT", "/me/player/pause")
def next_track(): return _api("POST", "/me/player/next")
def prev_track(): return _api("POST", "/me/player/previous")
def transfer(device_id: str, play_now: bool = True):
    return _api("PUT", "/me/player", None, {"device_ids": [device_id], "play": play_now})
def set_volume(pct: int, device_id: str | None = None):
    params = {"volume_percent": max(0, min(100, int(pct)))}
    if device_id: params["device_id"] = device_id
    return _api("PUT", "/me/player/volume", params)


def my_playlists(limit: int = 50) -> list[dict]:
    try:
        items = (_api("GET", "/me/playlists", {"limit": limit}) or {}).get("items", [])
    except Exception:
        return []
    return [{"name": p.get("name"), "uri": p.get("uri"), "art": (p.get("images") or [{}])[0].get("url")} for p in items]


def search(q: str, types: str = "track,artist,album,playlist", limit: int = 5) -> dict:
    try:
        return _api("GET", "/search", {"q": q, "type": types, "limit": limit, "market": "from_token"}) or {}
    except Exception:
        return {}


def status() -> dict:
    cur = _load()
    out = {"configured": configured(), "linked": bool(cur.get("refresh_token")), "user": cur.get("user"),
           "product": cur.get("product"), "redirect_uri": redirect_uri(),
           "wall_device_name": cur.get("wall_device_name"), "wall_online": False}
    if out["linked"]:
        wd = wall_device()
        out["wall_online"] = bool(wd)
        if wd: out["wall_device_name"] = wd.get("name")
    return out


# -------------------------------------------------------------- voice -------
_STOP = {"the", "a", "an", "some", "my", "me", "please", "music", "spotify", "on", "in", "to", "it", "up", "us"}


def _pick_device(words: set, prefer_wall: bool = True):
    """Device named in the sentence (… 'on the living room tv'), else the wall, else the active one."""
    devs = devices()
    best, score = None, 0
    for d in devs:
        dw = set(re.findall(r"[a-z0-9]+", (d.get("name") or "").lower())) - {"the", "tv", "speaker", "s"}
        n = len(dw & words)
        if n > score:
            best, score = d, n
    if best:
        return best
    if prefer_wall:
        wd = wall_device()
        if wd:
            return wd
    for d in devs:
        if d.get("is_active"):
            return d
    return devs[0] if devs else None


def voice(text: str, words: set) -> str | None:
    """Handle a music sentence with FamilyHub's own Spotify link. None = not handled."""
    tl = text.lower()
    dev = _pick_device(words)
    did = dev.get("id") if dev else None
    where = f" on {dev['name']}" if dev else ""
    try:
        if words & {"pause", "stop"} and not ({"play"} & words):
            pause(); return "Pausing the music."
        if words & {"next", "skip"}:
            next_track(); return "Skipping."
        if words & {"previous", "back", "last"} and words & {"song", "track"}:
            prev_track(); return "Going back a track."
        if (words & {"louder", "up"} or words & {"quieter", "lower", "softer", "down"}) and "play" not in words:
            louder = bool(words & {"louder", "up"})
            # nudge the active Spotify device's own volume (for the wall that's the Web
            # Playback player, the same level the Spotify app shows for "FamilyHub")
            v = (dev or {}).get("volume_percent", 50) or 50
            set_volume(min(100, v + 15) if louder else max(0, v - 15), did)
            return "Turning it up." if louder else "Turning it down."
        if (words & {"what", "whats", "what's", "who", "who's"} or re.search(r"\bwhat'?s\b", tl)) and words & {"playing", "song", "this"}:
            p = playback()
            if p and p.get("title"):
                return f"This is {p['title']} by {p['artist']}" + (f" on {p['device']}." if p.get("device") else ".")
            return "Nothing is playing right now."
        if not ({"play", "resume", "start", "put"} & words):
            return None
        if not did:
            return "I can't see any Spotify device to play on. Open Spotify on a phone once, or wait for the wall to register."

        # the thing to play: strip the verb and the device phrase
        q = re.sub(r"^\s*(hey\s+\w+[,]?\s+)?(can you |could you |please )?(play|put on|start|resume)\s+", "", tl).strip()
        if dev:
            dn = re.escape((dev.get("name") or "").lower())
            q = re.sub(rf"\b(on|in|through|to)\s+(the\s+)?{dn}\b", "", q).strip()
        q = re.sub(r"\b(on|in|through)\s+the\s+(kitchen|wall|living room|bedroom|tv|speaker)\b.*$", "", q).strip(" ,.")
        want = None
        for kind in ("playlist", "album", "artist", "song", "track"):
            if re.search(rf"\b{kind}\b", q):
                want = {"song": "track"}.get(kind, kind)
                q = re.sub(rf"\b(the\s+)?{kind}\b", "", q).strip(" ,.")
        q = re.sub(r"^(some|my|the|a)\s+", "", q).strip(" ,.")

        if not q or q in ("music", "it", "something", "anything"):
            play(did); return "Playing" + where + "."

        # 1) your own playlists by name (fuzzy on words)
        qw = set(re.findall(r"[a-z0-9]+", q)) - _STOP
        best, score = None, 0.0
        for pl in my_playlists():
            pw = set(re.findall(r"[a-z0-9]+", (pl.get("name") or "").lower())) - _STOP
            if not pw: continue
            s = len(pw & qw) / max(len(pw), 1)
            if s > score and (pw & qw):
                best, score = pl, s
        if best and (score >= 0.6 or want == "playlist"):
            play(did, context_uri=best["uri"]); return f"Playing your playlist {best['name']}{where}."

        # 2) Spotify search
        res = search(q)
        tracks = (res.get("tracks") or {}).get("items") or []
        artists = (res.get("artists") or {}).get("items") or []
        albums = (res.get("albums") or {}).get("items") or []
        pls = [p for p in ((res.get("playlists") or {}).get("items") or []) if p]
        if want == "playlist" and pls:
            play(did, context_uri=pls[0]["uri"]); return f"Playing the playlist {pls[0]['name']}{where}."
        if want == "album" and albums:
            play(did, context_uri=albums[0]["uri"]); return f"Playing the album {albums[0]['name']} by {albums[0]['artists'][0]['name']}{where}."
        if want == "artist" and artists:
            play(did, context_uri=artists[0]["uri"]); return f"Playing {artists[0]['name']}{where}."
        # no hint: exact artist name -> artist radio-ish (their top tracks context); else best track
        if artists and (artists[0].get("name") or "").lower() == q:
            play(did, context_uri=artists[0]["uri"]); return f"Playing {artists[0]['name']}{where}."
        if tracks:
            t = tracks[0]
            play(did, uris=[t["uri"]]); return f"Playing {t['name']} by {t['artists'][0]['name']}{where}."
        if artists:
            play(did, context_uri=artists[0]["uri"]); return f"Playing {artists[0]['name']}{where}."
        if pls:
            play(did, context_uri=pls[0]["uri"]); return f"Playing {pls[0]['name']}{where}."
        return f"I couldn't find {q} on Spotify."
    except RuntimeError as e:
        msg = str(e)
        if "404" in msg or "NO_ACTIVE_DEVICE" in msg:
            return "No Spotify device is active. Say it again in a moment, or start something on a phone first."
        if "403" in msg and "PREMIUM" in msg.upper():
            return "Spotify says this account isn't Premium, so I can't start playback."
        return "Spotify didn't accept that: " + msg
    except Exception:
        return "Spotify isn't answering right now."
