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
    "spotifyStartVolume": 45,        # % the wall's Spotify player starts at (perceived loudness, like the wall's volume buttons)
    "spotifyPlaylists": [],          # [{name, uri}] pinned on the Home tab's Spotify card
    "icloudAlbumUrl": "",            # iCloud Shared Album public link -> slideshow photos
    "assistantName": "Hub",          # what the family calls the voice assistant (she picks)
    "defaultCalendar": "",           # where new events go by default (a /api/sources/targets id)
    "speakAlerts": True,             # wall speaks reminders / announcements / timers
    "slideshowAfter": 5,             # minutes idle before the photo slideshow (0 = never)
    "slideSeconds": 8,               # seconds per photo
    "photoFit": "fit",               # slideshow: "fit" = whole photo over a blurred backdrop, "fill" = crop to screen
    "announceAdds": True,            # wall says "Rachell added …" when a phone adds something
    "announceQuietStart": None,      # "HH:MM"; None = follow the screen-off night window; "" = never quiet
    "announceQuietEnd": None,
    "pushAdds": True,                # Home Assistant pushes adds to the other phones (HA Companion app)
    "morningBriefing": False,        # auto-spoken "here's today" on first walk-up (off: use the button / ask)
    "briefingHour": 6,               # ...but not before this hour
    "doorbellTv": True,              # flash the doorbell snapshot on any Roku that is on
    "doorbellSpeak": True,
    "skin": "auto",                  # holiday skin: auto | off | christmas | thanksgiving
    "skinBanner": True,              # the "Days until …" card in the header
    "skinArt": True,                 # painted frame artwork when the skin has one (off = vector frame)
    "skinSlim": True,                # crop the painted frame so it's thinner and the panels get more room
    "calendarTasks": True,
    "sleepOnNightArm": True,         # alarm armed for the night -> wall dark (no screensaver) until morning
    "sleepArmStates": ["armed_night", "armed_home"],
    "sleepStayWindow": ["20:00", "05:00"],
    "closeGarageOnModes": True,
    "rokuApps": [],                  # TV remote: favorite apps shown first (both phones)
    "awayArm": "stay",               # Leaving arms Stay (dogs + motion sensors); "away" to arm Away      # Good night / Leaving close the garage door (like the Surety scenes)   # Armed Stay only means bedtime inside this window
    "homeAddress": "",               # where drive times start from (blank = Home Assistant's home location)
    "leaveBuffer": 5,                # minutes added to the drive for parking/walking in
    "leaveAlerts": True,             # show "Leave in N min" on the wall for events with a place           # due-dated to-dos + chores show as all-day chips on the calendar
    "nightTemp": None,               # Good Night sets the thermostat to this (None = leave it)
    "goodnightLightsOff": False,     # Good night also turns off lights + TVs
    "homeTemp": None,
    "openGarageOnHome": True,        # "I'm home" button opens the garage (after disarming)                # "I'm home" thermostat setting
    "awayTemp": None,                # Away mode thermostat setback           # wall says "someone's at the front door"
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
