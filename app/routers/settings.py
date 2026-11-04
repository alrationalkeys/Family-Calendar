"""Settings storage — theme, accent, font, density, panel visibility, holiday sets.
Stored as a single JSON blob under one key so the whole object round-trips cleanly."""
import json
from fastapi import APIRouter
from ..db import get_db

router = APIRouter()
KEY = "ui"

DEFAULTS = {
    "theme": "light",
    "accent": "#e9a23b",
    "font": "inter",
    "density": "comfortable",
    "panels": {"scoreboard": False, "todos": True, "groceries": True, "meals": True},
    "onscreenKbd": True,
    "wallMic": True,
    "heroEnabled": False,
    "heroDay": "",
    "heroNight": "",
    "holidays": {"us_federal": False, "christian": False, "jewish": False, "observances": False},
    "effects": True,
    "weatherFx": True,
    "effectPrefs": {"snow": True, "fireworks": True, "halloween": True, "petals": True},
    "dayStart": 6,         # first hour shown in the day/week time-grid (0–23)
    "dayEnd": 20,          # last hour shown (1–24)
    "hourPx": 46,          # zoom: pixel height of one hour row (26–120)
    "panelSizes": [1.1, 1.1, 0.9],   # relative heights of the side panels
    "textSize": "normal",            # normal | large
    "homeLayout": [],                # custom floor-plan rooms; [] = built-in sample
    "spotifyPlaylists": [],          # [{name, uri}] pinned on the Home tab's Spotify card
    "icloudAlbumUrl": "",            # iCloud Shared Album public link -> slideshow photos
    "assistantName": "Hub",          # what the family calls the voice assistant (she picks)
    "speakAlerts": True,             # wall speaks reminders / announcements / timers
    "morningBriefing": True,         # spoken "here's today" the first time someone walks up
    "briefingHour": 6,               # ...but not before this hour
}


@router.get("")
def get_settings():
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (KEY,)).fetchone()
    if not row:
        return DEFAULTS
    try:
        merged = {**DEFAULTS, **json.loads(row["value"])}
        return merged
    except json.JSONDecodeError:
        return DEFAULTS


@router.put("")
def put_settings(payload: dict):
    clean = {**DEFAULTS, **payload}
    with get_db() as conn:
        conn.execute(
            "INSERT INTO settings (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (KEY, json.dumps(clean)))
    return clean
