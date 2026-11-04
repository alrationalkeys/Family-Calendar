# CLAUDE.md — FamilyHub

Project anchor for Claude Code sessions. Read this first.

## What this is
A self-hosted family calendar / chore / grocery / meal-plan display — a DIY,
subscription-free alternative to Skylight Calendar. Runs on a small x86 mini PC (or a Pi,
or any machine), shown full-screen on a wall touchscreen, controlled from phones on the LAN.

Two interfaces:
- **Wall display** — `static/index.html`, served at `/`. Glanceable, dark. A bottom nav bar
  switches between pages: **Calendar** (week/month/day + glance side panels), **Home**
  (smart-home tiles — Home Assistant, Phase 2 placeholder for now), **Chores** (checklist +
  scoreboard), **Lists** (groceries + to-do), **Photos**. Sleep-mode photo slideshow + night
  screen-off.
- **Phone app** — `static/phone.html`, served at `/phone.html`. Input-focused PWA. A natural-language
  "quick add" box (AI routes text to the right place) plus manual forms. Color picker on every input.

## Stack
- **Backend:** FastAPI (Python 3.12). Entry: `app/main.py`.
- **DB:** SQLite by default (`familyhub.db`, gitignored). Swap to Postgres via `DATABASE_URL`.
- **Frontend:** plain HTML/CSS/JS, no build step. Polls the API.
- **AI:** Anthropic API for natural-language parsing, voice Q&A (+ web search), meal plans. Needs
  `ANTHROPIC_API_KEY`; model via `FAMILYHUB_AI_MODEL` (`services/ai_model.py`, default `claude-opus-4-8`).

## Layout
```
app/
  main.py              app wiring, router registration, static mount
  db.py                schema + migration + color model docs
  routers/
    dashboard.py       aggregated feed the wall polls (resolves colors)
    calendar.py        merges Google + iCloud events; write-back
    chores.py          chore chart + stars
    todos.py           to-do list (separate from chores)
    groceries.py       grocery list
    meals.py           meal planner
    categories.py      color categories + people management
    ai.py              /parse, /route, /quick-add
    ha.py              Home Assistant tab: tiles, toggle, scenes, alarm PIN pad
    photos.py          slideshow photo feed
  services/
    google_sync.py     Google Calendar API (read + write)
    caldav_sync.py     iCloud/CalDAV
    ai_parse.py        text -> events
    ai_route.py        text -> {kind, items} classifier (event/todo/grocery/meal)
    color.py           central color resolver
    ha_svc.py          Home Assistant REST client (+ demo mode)
static/
  index.html           wall display
  phone.html           phone control app
  manifest.json        PWA (Add to Home Screen)
```

## Color model (important — keep consistent)
Two sources: **people** and **categories**, both with colors. Every item can carry a
`category_id` and/or explicit `color`. Resolution order, enforced in `services/color.py`:
`item.color → category.color → person.color → default`. The dashboard resolves a final
`color` field onto every item so the frontend never has to.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Wall: http://localhost:8000/  ·  Phone: http://localhost:8000/phone.html

## State of things
- DONE + tested: all views, lists, meals, color coding, sleep slideshow, phone app, quick-add saves,
  theme/light-dark, customization, holiday presets, seasonal effects, recurrence (chores/todos),
  edit/delete (all item types + calendar events), calendar source management, vision quick-add,
  voice input, weather, optional PIN auth, DB backup, day/night hero banner,
  scheduled screen-off + wake webhook, live kids' scoreboard,
  bottom-nav multi-page shell (Calendar/Home/Chores/Lists/Photos), chore check-off celebration.
- NEEDS CREDS to light up: Google (`credentials.json`/`token.json`), iCloud (app-specific password
  via /api/sources/caldav), AI text/vision quick-add (`ANTHROPIC_API_KEY`). Weather works with no key.
- Calendar events render once a source is connected (see README).

## Newer endpoints
- `/api/routines/` — daily step checklists (+ `/countdowns`); both ride `/api/dashboard`
- `/api/photos/upload` (multipart) + `DELETE /api/photos/{name}`; `settings.icloudAlbumUrl` → shared album merged into `/api/photos/`
- `/api/mail/*` — email import inbox (`status`, `pending`, `poll`, `{id}/approve`, `{id}/dismiss`); IMAP creds in `.env` only
- `/api/ha/spotify` (GET state / POST action), `/api/ha/art` — Spotify card; pins in `settings.spotifyPlaylists`
- `/api/ha/events` (SSE) + `/api/ha/version` — live HA state changes via `services/ha_live.py` (WebSocket mirror; demo toggles bump too)
- `/api/announce` — phone→wall intercom (queued as a notification; wall speaks `kind=announce`)
- `GET /api/notifications/digest` — spoken "today" briefing (`spoken`, `summary`, `details`); wall says it on first wake after `settings.briefingHour`
- `/api/ai/meal-plan` + `/apply` — AI dinner planner (built-in rotation without a key); ingredients → groceries, de-duplicated
- Wall kid mode: tap a scoreboard avatar → `openKidMode(person)`; voice "show Ella's day"
- `/api/sources/` — list/add/remove Google + iCloud + ICS feeds (passwords never returned)
- `/api/calendar/events?person_id=N` — merged feed with optional per-person filter
- `/api/events/` — local events FamilyHub owns: recurrence + per-event reminders
- `/api/notifications/due` + `/digest` — reminders & morning summary (frontend polls)
- `/api/rewards/` — chore-star economy: balances, define rewards, grant, redeem
- `/api/ai/vision` — photo (base64) -> extracted events
- `/api/weather` — Open-Meteo, no key needed, defaults to Socastee SC (now also returns sunrise/sunset)
- `/api/chores/scoreboard` — per-person star balance + today's chore progress (live kids' leaderboard)
- `/api/ha/*` — Home Assistant bridge for the Home tab: `status`, `home` (grouped tiles),
  `toggle` (lights/switches/covers/locks/scenes), `service` (escape hatch), `alarm`
  (arm/disarm w/ PIN). Runs in **demo mode** (sample devices) unless `HA_URL`+`HA_TOKEN`
  are set; force demo with `HA_DEMO=1`. HA talks to the gear; token stays server-side.
- `/api/display/*` — scheduled screen-off: `state` (wall polls), `wake` (PIR/HA webhook), `sleep`,
  `config` (GET/PUT the night window). On a Pi it cuts the backlight via `vcgencmd display_power`;
  override with `FAMILYHUB_SCREEN_ON_CMD` / `FAMILYHUB_SCREEN_OFF_CMD` for Wayland/non-Pi.
- recurrence: chores/todos/events with `recurrence` roll forward / expand

## Reminders & notifications
Local events can carry `reminder_minutes`; a notification is queued and the wall
polls `/api/notifications/due` every 30s, showing a banner + (if permitted) a native
browser notification. `/api/notifications/digest` builds a 'here's today' summary.
No external push service — all on the LAN.

## Rewards
Completing a chore with stars credits the assigned person's ledger. Define rewards
with a star cost; redeem draws down the balance. `/api/rewards/balances` shows totals.

## External feeds
Subscribe to any public ICS/webcal URL (sports schedules, golf tee times, school,
trash pickup) via `/api/sources/ics`. Parsed by stdlib, merged into the calendar.

## Hardware / install (decided Nov 2026)
- Wall: Forzola 15.6" touchscreen + **C3 mini PC** (Ubuntu, Xorg, kiosk Chromium). One-shot
  installer `setup/install-kiosk.sh`; walkthrough `docs/first-boot.md`. Screen-off uses
  `xset dpms` (set in `.env` by the installer). `familyhub.service` is a template
  (`__USER__`/`__HOME__`) with `EnvironmentFile=.env`.
- Home Assistant OS on a **second C3**, headless: `docs/home-assistant-setup.md` (HAOS x86
  install, IQ Panel via qolsysgw, Roku, openWakeWord/Whisper/Piper, Wyoming satellite via
  `setup/install-satellite.sh` on the screen box).
- 3D-printed mount: `hardware/familyhub-mount.scad` (C3 cradle, Forzola port-hump clearance,
  optional speaker pocket); parts + print order in `hardware/README.md`.
- Floor plan: `DEFAULT_LAYOUT` in `static/index.html` is the real house traced in feet
  (1 cell = 1 ft, mirrored, garage right); renderers scale adaptively via `layoutExtent()`.

## Security & ops
- Optional PIN auth: set `FAMILYHUB_PIN` env var -> writes need `X-FH-PIN` header; reads stay open.
  Add `FAMILYHUB_LOCK_READS=1` to gate *reads* too — a login screen (`static/auth.js`,
  `/api/auth/*`) asks for the PIN before any data loads; the static shell stays open so the
  login can render. Constant-time compare + per-IP lockout (empty PIN isn't counted as a guess).
  Use this on any public URL (e.g. Railway). For real exposure prefer Tailscale over the PIN.
- Backups: `python backup.py --keep 14`; systemd timer files included.

## Known follow-ups (not yet done)
- Jewish holiday dates are approximate (Hebrew calendar) — swap to a proper lib for precision.
- Vision + weather couldn't be tested against live APIs in the build sandbox (no network);
  they have error guards and degrade gracefully, but first real run should verify them.

## Conventions
- Keep the no-build-step frontend (no React/bundler) — simplicity is the point.
- Never commit secrets: `credentials.json`, `token.json`, `.env`, `ANTHROPIC_API_KEY`.
- Don't break the color resolution chain; route new item types through `services/color.py`.

## Next milestones (in priority order)
1. Connect Google + iCloud so the calendar fills with real events.
2. Vision quick-add: photograph a paper flyer/school schedule → events.
3. Recurring chore engine + weekly auto-reset.
4. Tailscale for off-network phone access (see README).
