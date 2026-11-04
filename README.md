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

## Parts (late-2026 pricing — Pis and mini PCs both spiked with the RAM shortage)
| Part | ~Cost | Notes |
|---|---|---|
| 15.6" industrial touchscreen monitor (Forzola, HDMI + USB touch, VESA 75) | $140 | The wall. 10-pt capacitive, cables + 12V brick in the box. |
| C3 mini PC (i3-5005U, 8GB/512GB) — the screen's brain | $170 | Runs the kiosk + voice satellite. Any x86 box with HDMI works; a used tiny-PC is fine too. |
| C3 mini PC #2 — Home Assistant (optional, smart-home only) | $170 | Or a Pi 5 / HA Green. Separate box so a FamilyHub update never takes the house down. |
| USB speaker + mic bar | $15 | For tap-to-talk and "Hey Jarvis". |
| Filament + M4/M3 screws | ~$10 | Your printer: back case, cleat, stand (`hardware/`). |
| **Total** | **~$350** (calendar wall) / **~$520** (with the HA box) | vs ~$300 Skylight + $40–80/yr forever |

Full parts list and parametric 3D-print files are in [`hardware/`](hardware/).
Step-by-step install day: [`docs/first-boot.md`](docs/first-boot.md).

> Cheaper: reuse any old laptop/mini PC + an HDMI monitor and drive it from your phone —
> the software doesn't care.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open `http://<pi-ip>:8000` on the wall screen.

### Connect calendars
Easiest: phone app → **Settings → Calendars** (iCloud with an app-specific password, any
Outlook/Google/school **ICS link**, or Google OAuth once set up). Under the hood:
- **Google:** create OAuth desktop creds, drop `credentials.json` in the project root,
  run the auth flow once on your desktop, copy `token.json` to the Pi. (see `app/services/google_sync.py`)
- **iCloud:** generate an app-specific password at appleid.apple.com, then insert a
  `cal_sources` row with `kind='caldav'`, config `{"url":"https://caldav.icloud.com/","username":"...","password":"..."}`.

### Auto-start on the wall box (one command)
```bash
bash setup/install-kiosk.sh   # Ubuntu/Debian: service + auto-login + Chromium kiosk on boot
```
(Does the `familyhub.service` + `kiosk.sh` autostart wiring for you — see `docs/first-boot.md`.)

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
