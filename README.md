# FamilyHub

A self-hosted, AI-native family calendar / chore chart / meal planner — a DIY,
subscription-free alternative to Skylight Calendar. Aggregates Google + iCloud
calendars, chores (with stars), meals, and photos into one wall display.
Runs on a Raspberry Pi, controlled from any phone on your network.

## Why it beats a Skylight
- **$0/mo forever.** Skylight paywalls chores/meals/photos/magic-import behind a ~$39/yr plan.
- **AI-native event entry.** `/api/ai/parse` turns "kids dentist next thursday at 4"
  or a pasted school newsletter into structured events — Skylight's paid "Magic Import," but better and free.
- **Two-way sync.** Writes events back to Google, not just read-only display.
- **It's yours.** Add weather, tee times, your work schedule, anything.

## Parts (mid-2026 pricing — note the RAM shortage inflated Pi prices)
| Part | ~Cost | Notes |
|---|---|---|
| Raspberry Pi 5 (4GB) | $75 | 4GB is the floor for kiosk Chromium. Or reuse a spare PC/monitor. |
| 27W USB-C PSU | $12 | Pi 5 needs 5V/5A |
| microSD 32GB+ or NVMe | $10–25 | |
| 15.6" IPS HDMI monitor | $70 | Non-touch is fine — you can drive it from your phone. |
| 15.6" touchscreen (if you want tap-on-wall) | $120–160 | Optional upgrade; the UI has full touch (tap/swipe/pinch). See `hardware/`. |
| Filament | ~$5 | Your printer; bezel + wall cleat + stand |
| **Total** | **~$175** (non-touch) / **~$225** (touch) | vs $160 Skylight + $39/yr forever |

Full parts list, touchscreen picks, and parametric 3D-print files are in [`hardware/`](hardware/).

> If you reuse an existing monitor and a Pi Zero 2 W (~$15, unaffected by the RAM
> price spike), you can land under $100.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open `http://<pi-ip>:8000` on the wall screen.

### Connect calendars
- **Google:** create OAuth desktop creds, drop `credentials.json` in the project root,
  run the auth flow once on your desktop, copy `token.json` to the Pi. (see `app/services/google_sync.py`)
- **iCloud:** generate an app-specific password at appleid.apple.com, then insert a
  `cal_sources` row with `kind='caldav'`, config `{"url":"https://caldav.icloud.com/","username":"...","password":"..."}`.

### Auto-start on the Pi
```bash
sudo cp familyhub.service /etc/systemd/system/
sudo systemctl enable --now familyhub
./kiosk.sh   # add to your desktop autostart so Chromium opens full-screen on boot
```

## Two interfaces
- **Wall display** (`/`) — glanceable, dark, week/month/day views with tap-to-drill,
  to-do + grocery + meal side panels, and a sleep-mode photo slideshow after 5 min idle.
- **Phone app** (`/phone.html`) — input-focused. A "quick add" box where you type
  naturally ("dentist thursday 4pm", "milk, eggs, bread") and AI files it in the right
  place, plus manual Event/To-do/Grocery/Meal forms with date/time pickers. Color picker
  on every input.

### Install the phone app (no app store)
On her phone, open `http://<address>/phone.html` in Safari/Chrome → Share →
**Add to Home Screen**. It gets its own icon and opens full-screen like a native app.
(Add `icon-192.png` and `icon-512.png` to `static/` for a custom icon.)

### Reach it from anywhere — Tailscale (simplest)
So she can add a grocery item from the store:
1. Install Tailscale on the Pi: `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`
2. Install the Tailscale app on her phone, sign in with the same account.
3. The phone app address becomes `http://<pi-tailscale-ip>/phone.html` and just works
   anywhere — no port forwarding, nothing exposed to the public internet, free.

## Color coding
Two color sources, applied everywhere (calendar, chores, to-dos, groceries, meals):
- **People** (you, her) — each a color
- **Categories** (Work, Kids, Appointments, Sports...) — each a color

Resolution: explicit item color → category color → person color → default.
Manage via `/api/categories/` and `/api/categories/people`.

## Roadmap (the actual 10x list)

## Layout
```
app/
  main.py            app wiring
  db.py              SQLite (swap to Postgres via DATABASE_URL)
  routers/           dashboard, calendar, chores, meals, photos, ai
  services/          google_sync, caldav_sync, ai_parse
static/index.html    the wall display (dark, glanceable, time-rail layout)
```
