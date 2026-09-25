# CLAUDE.md — FamilyHub

Project anchor for Claude Code sessions. Read this first.

## What this is
A self-hosted family calendar / chore / grocery / meal-plan display — a DIY,
subscription-free alternative to Skylight Calendar. Runs on a Raspberry Pi (or any
machine), shown full-screen on a wall touchscreen, controlled from phones on the LAN.

Two interfaces:
- **Wall display** — `static/index.html`, served at `/`. Glanceable, dark. Week/month/day
  views with tap-to-drill, to-do + grocery + meal side panels, sleep-mode photo slideshow.
- **Phone app** — `static/phone.html`, served at `/phone.html`. Input-focused PWA. A natural-language
  "quick add" box (AI routes text to the right place) plus manual forms. Color picker on every input.

## Stack
- **Backend:** FastAPI (Python 3.12). Entry: `app/main.py`.
- **DB:** SQLite by default (`familyhub.db`, gitignored). Swap to Postgres via `DATABASE_URL`.
- **Frontend:** plain HTML/CSS/JS, no build step. Polls the API.
- **AI:** Anthropic API (`claude-opus-4-8`) for natural-language parsing. Needs `ANTHROPIC_API_KEY`.

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
    photos.py          slideshow photo feed
  services/
    google_sync.py     Google Calendar API (read + write)
    caldav_sync.py     iCloud/CalDAV
    ai_parse.py        text -> events
    ai_route.py        text -> {kind, items} classifier (event/todo/grocery/meal)
    color.py           central color resolver
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
  voice input, weather, optional PIN auth, DB backup.
- NEEDS CREDS to light up: Google (`credentials.json`/`token.json`), iCloud (app-specific password
  via /api/sources/caldav), AI text/vision quick-add (`ANTHROPIC_API_KEY`). Weather works with no key.
- Calendar events render once a source is connected (see README).

## Newer endpoints
- `/api/sources/` — list/add/remove Google + iCloud + ICS feeds (passwords never returned)
- `/api/calendar/events?person_id=N` — merged feed with optional per-person filter
- `/api/events/` — local events FamilyHub owns: recurrence + per-event reminders
- `/api/notifications/due` + `/digest` — reminders & morning summary (frontend polls)
- `/api/rewards/` — chore-star economy: balances, define rewards, grant, redeem
- `/api/ai/vision` — photo (base64) -> extracted events
- `/api/weather` — Open-Meteo, no key needed, defaults to Socastee SC
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

## Security & ops
- Optional PIN auth: set `FAMILYHUB_PIN` env var -> writes need `X-FH-PIN` header; reads stay open.
  For real exposure use Tailscale, not just the PIN.
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
