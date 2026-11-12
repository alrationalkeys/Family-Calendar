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
  phone.html           phone control app (Home tab = dark command center + live 3D house)
  home-shared.js       layout (feet grid) + DEFAULT_PLAN (doors/windows), 2D floor plan, icon/state
                       helpers — shared by wall + phone. Rooms are written AS DRAWN on the D.R. Horton
                       sheet (garage left) and mirrored in code (MIRROR=true) because the house is the
                       mirror image. Furnishing hints per room: bed/tv/counter/tub side, shower corner.
  home3d.js            three.js dollhouse: walls/doorways/furniture from the layout, per-room point
                       lights + TV glow driven by HA, tappable device pins. FHHome.render3D(el,h,opts)
  skins.js             holiday skins, auto by date: Valentine's Feb 1–14, St. Patrick's Mar 10–17, Easter −14 d, 4th Jun 28–Jul 4, Halloween Oct,
                       Thanksgiving Nov 1→TG, Christmas →Dec 30, New Year's Eve Dec 31–Jan 1 (+ Birthday). Each DEFS entry: art (frame, per-skin
                       `slim` crop), sign (countdown card art + text insets), sprite (fly/run across). Art in static/skins/ (frames .webp): painted frame, lights,
                       lanterns, gifts, snow caps, countdown banner; settings.skin auto|off|christmas|thanksgiving,
                       ?skin= URL override for phone previews. Pins Seasonal.force(snow|leaves). A skin may carry
                       painted `art` (static/skins/<name>-frame.png, 1920x1080 PNG, centre keyed to transparent) drawn
                       BEHIND the panels with per-side pads; settings.skinArt=false falls back to the vector frame.
  vendor/three.min.js  three.js r160 (MIT, vendored so the wall works offline)
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
- `GET /api/sources/targets` — writable destinations (FamilyHub / Google / each iCloud calendar); `POST /api/calendar/events` takes `destination`; last choice remembered in `settings.defaultCalendar`
- iCloud **Reminders ↔ To-Do** two-way: `services/reminders_sync.py` (VTODO over the same CalDAV source, every 5 min + `POST /api/todos/sync`; ticking a synced to-do completes it upstream; `todos.ext_uid/ext_source/ext_list`)
- Automations page: `GET /api/ha/automations` (+ `/toggle`, `/setting`, `/routine` GET/POST/DELETE). Built-in packages
  `docs/ha/{peak_thermostat,outdoor_lights,kitchen_lights}.yaml` (underscores — HA rejects dashes) keep every time/temp/
  light list in HA helpers (no `initial:`; a `fh_*_defaults` automation seeds them once, so edits survive restarts).
  Light lists are `input_text` (comma ids) edited with a checklist. Descriptions fill in helper values ({input_x.y}).
  "Your routines" = builder (`automations.build(spec)`) -> HA `/api/config/automation/config/fhu_*` (needs an admin
  token); spec JSON lives in the automation description so it can be re-edited. Builder never unlocks/disarms.
  "Say on the wall" = HA event `familyhub` {kind:say} that `ha_live` turns into an announcement. UI: `static/automations.js`.
  Builder spec extras: `when.for` (minutes, quiet/closed triggers), `between` {after,before}, `dates` {from,to MM-DD, wraps
  New Year} + `dates_except`, `ifoff` (only if the lights it turns on are off), dim `white` warm|cool. "Turn these into my
  own routines" (`POST /api/ha/automations/convert {keys}`) rebuilds the outdoor/kitchen packages as fhu_* routines from the
  current helper values (stale ids fixed via `_guess`), switches the packaged automations off and hides those cards
  (settings key `routines_converted`). Thermostats stay packaged (peak save/restore).
  'Then wait…' steps: minutes = delay in the same run (mode restart); until a time / sunrise / sunset / motion quiet =
  a separate trigger in the same automation (trigger ids part0..N + choose), because HA cancels wait_for_trigger on every
  automation reload. Next-morning parts skip day/date checks. Saved routines are rebuilt once with the current builder (flag routines_parts_v2). Next-morning parts check yesterday's day/date; ifoff = "none of the first part's lights on"; Leaving with a door/garage open waits up to 5 min for it to shut, then arms (another button cancels; phones get a push if it never could); /api/ha/mode only counts as a tap for source wall|phone.
  Thermostat schedule = any number of slots {at, days, targets (climate ids), heat, cool}: `services/thermo_sched.py`,
  `GET/POST /api/ha/thermostat-schedule`. Saved into HA as `script.fhs_thermostat_now` (per thermostat, the latest slot
  looking back over the week; auto -> low/high) + automation `fhs_thermostat_slots` (fires at each slot time, not during
  peak, honours sched_enabled; slot list JSON in its description). peak_thermostat.yaml's fh_thermostat_schedule (v2)
  hands over to it, so peak end lands on the right slot; the old fh_sched_apply is switched off on save.
- `/api/summary` — flat JSON of the family's day for HA REST sensors (docs §J)
- Spotify on the wall (official device): `services/spotify_web.py` + `routers/spotify.py`
  (`/api/spotify/status|login|callback|code|token|device|devices|state|playlists|cmd`). The
  wall page loads Spotify's Web Playback SDK and registers "FamilyHub"; voice `_music`
  prefers this link (search anything → play on the wall) over HA's player. Env
  `SPOTIFY_CLIENT_ID/SECRET`, redirect `http://127.0.0.1:8000/api/spotify/callback`;
  tokens in settings key `spotify_auth`. Third-party Connect clients (spotifyd,
  go-librespot) are blocked by Spotify on this account — keep as fallbacks only.
- Voice commands: `services/voice_cmd.py` (`interpret`, devices/modes/timers/lists) + `services/voice_more.py`
  (no-AI-key events with date/time parsing, "we need X", list read-back, check-off, thermostats w/ peak guard).
  Every command + empty transcription is logged: `GET/DELETE /api/ai/voice/log` (phone Settings > Advanced > Voice,
  which also has a "Try a command" box). Whisper gets an `initial_prompt` of names/devices (`voice_cmd.stt_prompt`),
  beam 5 (`FAMILYHUB_STT_BEAM`). Device on/off only fires on command phrasing; scenes need their whole name.
- Local speech on the wall: `services/speech.py` (faster-whisper STT + Piper TTS, optional).
  `GET /api/ai/voice/status`, `POST /api/ai/transcribe` (multipart clip), `POST /api/ai/tts` (wav).
  The wall records with MediaRecorder when `stt` is true, else falls back to Web Speech API
  (snap Chromium has none). Install: `setup/install-voice.sh`; env `FAMILYHUB_STT_MODEL`,
  `FAMILYHUB_PIPER_VOICE`. kiosk.sh passes `--use-fake-ui-for-media-stream` (auto-allow mic).
- Cameras + doorbell: `GET /api/ha/camera/{entity}` (snapshot via HA camera_proxy, 4 s cache, token server-side),
  `GET /api/ha/doorbell` (last ring/motion), `POST /api/ha/doorbell/test`. `services/doorbell.py` watches
  ha_live state changes (binary_sensor/event named doorbell|ring|chime|button → ring; a camera's motion sensor →
  motion). SSE `/api/ha/events` carries `ring` (timestamp) so the wall pops the snapshot instantly + chime + speech;
  phones get an HA push with the picture; Rokus that are on show it via media_player.play_media (url/jpg).
  Settings `doorbellTv`, `doorbellSpeak`; env `FAMILYHUB_URL` = LAN URL phones/TVs load the snapshot from.
- 3D driveway: `/api/ha/home` carries `people` (house_modes.presence); Alex's white pickup / Rachell's white CX-9 show while their HA person is home (no person = shown). Garage furnished from photos (workbench wall, fridge, gym wall). Phone Home tab is live via the same SSE stream (30 s backup poll).
- `GET /api/ha/timeline?day=` (`services/timeline.py`): one day of HA history as on-spans (heat/AC from hvac_action, lights, plugs, TVs) + device_class power sensors + the peak window + stats; phone Home tab "📊 Today" (`static/timeline.js`, day nav, tap a bar for times).
- House watch (`services/watch.py`, 1-min loop): `GET /api/ha/health` (low batteries ≤ settings.batteryLow, unavailable devices → "Needs attention" card on wall + phone Home), peak alert (heat/AC on 3+ min into peak → push once/thermostat/day, settings row `peak_log`), night check at settings.nightCheckTime (`GET /api/ha/night-check`; push only if something's unlocked/open/alarm off), Sunday 18:00 weekly note. `GET /api/ha/timeline/week` feeds the Today dashboard's Week view. Phone Settings > Alerts to our phones. Pushes via HA mobile_app notifiers; never changes anything.
- Storms/rain/packages: `services/wx_alerts.py` (`GET /api/weather/alerts` = NWS active alerts for the house point, Moderate+; Severe/Extreme or hurricane/tropical/tornado/flood → push once + wall strip; hurricane/TS prep checklist ticked per device; rain check: ≥60% in 2 h + garage/window open → push, max every 6 h) and `services/porch.py` (camera motion/ring on a front camera → 25–45 s later snapshot → `FAMILYHUB_PACKAGE_MODEL` (default claude-haiku-5-5) says package yes/no → push with picture; reminder after 2 h if still there). Settings wxAlerts / rainCheck / packageAlerts. Both run from the house-watch loop / doorbell hook.
- Laundry (`services/laundry.py`, hooked into ha_live): GE SmartHQ washer GFW550 + dryer GFD55 via HACS `simbaja/ha_gehome`; a washer/dryer state sensor going running→end = "🧺 The washer is done" (wall voice by day, passive push in quiet hours laundryQuietStart/End). `GET /api/ha/laundry` = running + minutes left.
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
- Sleep mode: alarm armed Night (or FamilyHub "Good night") -> wall dark, no photo screensaver, a tap peeks 60 s; ends on disarm, "good morning", or `POST /api/display/morning` (`/bedtime` starts it). `display_svc.on_alarm` (live via ha_live + 30 s poll); settings `sleepOnNightArm`, `sleepArmStates`.
- `/api/display/*` — scheduled screen-off: `state` (wall polls), `wake` (PIR/HA webhook), `sleep`,
  `config` (GET/PUT the night window). On a Pi it cuts the backlight via `vcgencmd display_power`;
  override with `FAMILYHUB_SCREEN_ON_CMD` / `FAMILYHUB_SCREEN_OFF_CMD` for Wayland/non-Pi.
- recurrence: chores/todos/events with `recurrence` roll forward / expand

## North Pole Village (Christmas village, Nov 2026)
Handoff doc: `docs/village/README.md` — three ESP32 boards on the LAN, HTTP-controlled: Board A `village-fx`
(192.168.1.200, effects hub, `/cmd?do=wake|sleep|tree|rachell|carol|train|play:N|light:N|rinkon|lampson|manual…`,
`/status` plain text), Board B `village-train` (192.168.1.121, `/go?laps=N`, `/stop`, `/status`), WLED `village-lights`
(192.168.1.134, presets 1 Off · 2 Sleepy · 3 Evening · 4 Tree show · 5 Rachell's show).
FamilyHub side: `services/village.py` + `routers/village.py` (`GET /api/village/status`, `POST /api/village/cmd {do}` —
tree|rachell|carol|train|stop|laps1|laps3|wake|sleep|rinkon|rinkoff). Tile on the wall + phone Home pages only while the
boards answer. Voice: "start/stop the train", "tree show", "Rachell's show", "carolers", "village to sleep/wake" (+ a
`village` tool for the AI). Good night / Leaving (`settings.villageWithHouse`) = sleep + manual mode + WLED off; FamilyHub
flips it back to automatic 06:00–16:00 or on I'm home, only if it was the one that paused it (settings key `village_paused`).
Board IPs in `settings.villageFx` / `villageTrain` (private IPs only). Village is finished and
snow-covered: **never flash firmware unless Alex asks**; real `secrets.h` never goes in the repo. Board A runs its own
schedule (open 16:00–23:00) + motion wake, so HA/FamilyHub should complement it, not fight it. `manual`/`override` toggle.

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
- Alarm: nothing disarms or unlocks except the I'm home BUTTON (`/api/ha/mode` passes `tapped=True`). It disarms with the
  typed code, or with no code when Alex turned on `settings.welcomeNoCode` (his choice, Nov 2026). Voice/AI never disarm
  (house_modes.run without tapped). Garage only opens after a successful disarm. House buttons = editable steps in
  settings row `house_modes` (`GET/POST/DELETE /api/ha/modes/{mode}`), built-in sequence when empty. Modes: goodnight,
  morning (wakes the wall + briefing; default disarm -> thermostats back to schedule; `disarm` step allowed only here, same
  tap/code rule), away, welcome.

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
