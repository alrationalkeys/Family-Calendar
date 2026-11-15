"""
Optional nicer voice from ElevenLabs (cloud), with Piper as the always-there fallback.

  .env                ELEVENLABS_API_KEY=...      (never in the repo; the key stays on the wall PC)
  settings            cloudVoiceId   everyday voice id ("" = keep the local Piper voice)
                      santaVoiceId   voice used in Santa season ("" = none)
                      santaVoice     bool, Santa season on/off (day after Thanksgiving .. Dec 25)

The free plan is about 10,000 credits a month, so every sentence is cached on disk (the washer is done, good
morning...) and anything that fails (no internet, out of credits, voice not allowed on the plan) silently falls back
to Piper and stays there for a while instead of retrying every sentence.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

API = "https://api.elevenlabs.io/v1"
MODEL = os.getenv("FAMILYHUB_ELEVEN_MODEL", "eleven_flash_v2_5")     # fast + half the credits per letter
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "tts_cache")
CACHE_MAX = 400
_S: dict = {"down_until": 0.0, "error": "", "voices": None, "voices_at": 0.0, "sub": None, "sub_at": 0.0}


def _key() -> str:
    return os.getenv("ELEVENLABS_API_KEY", "").strip()


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def santa_season(today: date | None = None) -> bool:
    d = today or date.today()
    nov1 = date(d.year, 11, 1)
    thanksgiving = nov1 + timedelta(days=(3 - nov1.weekday()) % 7 + 21)
    return thanksgiving < d <= date(d.year, 12, 25)


def voice_id(s: dict | None = None) -> str:
    """The cloud voice to use right now, or "" for the local voice."""
    if not _key():
        return ""
    s = s if s is not None else _settings()
    if s.get("santaVoice", True) and s.get("santaVoiceId") and santa_season():
        return str(s["santaVoiceId"])
    return str(s.get("cloudVoiceId") or "")


def ready() -> bool:
    return bool(voice_id()) and time.time() >= _S["down_until"]


def _req(path: str, body: dict | None = None, timeout: float = 8.0) -> bytes:
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, headers={
        "xi-api-key": _key(), "Content-Type": "application/json", "User-Agent": "familyhub"})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.read()


def _why(e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        try:
            d = json.loads(e.read().decode() or "{}").get("detail")
            msg = d.get("message") if isinstance(d, dict) else str(d or "")
        except Exception:
            msg = ""
        return f"ElevenLabs said no ({e.code}){': ' + msg[:160] if msg else ''}"
    return "Couldn't reach ElevenLabs"


def speak(text: str, vid: str | None = None, strict: bool = False) -> bytes | None:
    """-> MP3 bytes, or None to use the local voice. strict=True raises the reason instead (the Test button)."""
    text = (text or "").strip()
    vid = vid or voice_id()
    if not text or not vid or not _key():
        return None
    name = hashlib.sha1(f"{vid}|{MODEL}|{text}".encode()).hexdigest() + ".mp3"
    path = os.path.join(CACHE_DIR, name)
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        pass
    if not strict and time.time() < _S["down_until"]:
        return None
    try:
        audio = _req(f"/text-to-speech/{vid}?output_format=mp3_44100_128", {"text": text, "model_id": MODEL})
    except Exception as e:
        _S["error"] = _why(e)
        code = getattr(e, "code", 0)
        # out of credits / bad key / voice not allowed: no point retrying soon. A network blip: try again in a minute.
        _S["down_until"] = time.time() + (1800 if code in (401, 402, 403, 429) else 60)
        if strict:
            raise RuntimeError(_S["error"])
        return None
    if not audio:
        return None
    _S["error"] = ""
    _S["sub_at"] = 0.0
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(path, "wb") as f:
            f.write(audio)
        files = sorted((os.path.join(CACHE_DIR, n) for n in os.listdir(CACHE_DIR)), key=os.path.getmtime)
        for old in files[:-CACHE_MAX]:
            os.unlink(old)
    except OSError:
        pass
    return audio


def info() -> dict:
    """For phone Settings: is there a key, the account's voices, credits used this month."""
    out = {"key": bool(_key()), "voices": [], "used": None, "limit": None, "resets": None,
           "santa_now": santa_season(), "error": _S["error"]}
    if not out["key"]:
        return out
    now = time.time()
    if _S["voices"] is None or now - _S["voices_at"] > 600:
        try:
            vs = json.loads(_req("/voices")).get("voices") or []
            _S["voices"] = sorted(({"id": v.get("voice_id"), "name": v.get("name") or "?",
                                    "kind": v.get("category") or ""} for v in vs if v.get("voice_id")),
                                  key=lambda v: v["name"].lower())
            _S["voices_at"] = now
        except Exception as e:
            out["voices_error"] = _why(e)
    out["voices"] = _S["voices"] or []
    if _S["sub"] is None or now - _S["sub_at"] > 120:
        try:
            _S["sub"] = json.loads(_req("/user/subscription"))
            _S["sub_at"] = now
        except Exception:
            pass
    if _S["sub"]:
        out["used"] = _S["sub"].get("character_count")
        out["limit"] = _S["sub"].get("character_limit")
        out["resets"] = _S["sub"].get("next_character_count_reset_unix")
    return out
