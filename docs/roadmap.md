# FamilyHub — roadmap & decisions

The living plan: where we're going, what's decided, and what's built. Keeps the
vision in one place across sessions. (Day-to-day anchor is still `CLAUDE.md`.)

## The vision in one line
One wall touchscreen that does **everything** — family calendar, chores, lists, photos,
**and** the smart-home control center — simple enough that the whole family uses it without
help. Lift it off the wall, set it on the counter, still does it all.

## Architecture (decided)
- **One screen, two boxes.** The FamilyHub touchscreen is the only thing you touch. **Home
  Assistant runs headless on a *separate* Pi** so a FamilyHub update can never take the house
  (or alarm) down. FamilyHub draws HA's devices as tiles; HA is the brain that talks to gear.
- **Works offline.** Calendar, weather, lists keep working if the internet drops; sync when back.
- **LAN-first + encrypted.** No open ports to the internet; Tailscale (WireGuard) for remote.

## Decisions locked in
| Topic | Decision |
|---|---|
| Orientation | Rotatable, **landscape first** |
| Calendars | iCloud **and** Google |
| Family members | Added later (via phone/settings) |
| Photos | Phone upload |
| Weather | ZIP **29588** (Socastee SC), °F — already the default coords |
| Smart home | Through **Home Assistant OS** on a second **C3 mini PC** (headless, Ethernet). Pi 5 sold |
| Alarm | **Qolsys IQ Panel** via HA + `qolsysgw` (have dealer code). Start **status-only**, add arm/**disarm** behind a PIN pad |
| TVs | **Roku** (Hisense/TCL) via HA's built-in Roku integration — local ECP, auto-discovered. Need "Fast TV Start" on each TV to power on |
| Screen | **Forzola 15.6" industrial touchscreen monitor** (10-pt, HDMI + USB-B touch, VESA 75×75, 365×223 mm) — matches the 15" Skylight. $140, cables + remote in the box |
| Couch control | **Your phone** — Home Assistant app + FamilyHub web page on the LAN. No portable screen needed; the wall screen stays wired |
| Screen brain | **C3 mini PC (i3-5005U 8GB/512GB)** on Ubuntu + Xorg, FamilyHub in kiosk Chromium + the Wyoming voice satellite. HA on the second C3 |
| Voice | Tap-to-talk (browser) + hands-free **openWakeWord** on HA; USB speaker/mic bar in a side pocket of the printed case |
| Navigation | **Bottom nav bar**: Calendar · Home · Chores · Lists · Photos *(built)* |
| Disk encryption | Skip on the wall tablet (low value, headless hassle) |

## Phases

### Phase 0 — housekeeping
- [x] `.env.example` (secrets gitignored, server-side only) → `.env.example`
- [x] One-page **README for the family** → `docs/family-guide.md`
- [x] 3D-print enclosure retargeted to the HOWENS screen (back case hides Pi + cables, VESA mount, cleat, stand) → `hardware/`

### Phase 1 — finish the calendar (comes first, fully working)
- [x] Bottom-nav multi-page shell
- [x] Chore check-off celebration
- [x] Day/night hero banner · scheduled screen-off + wake · kids' scoreboard
- [x] Agenda view (4th calendar view)
- [x] Offline caching — localStorage data cache (calendar/weather/lists fall back when the
  net drops, with an "offline" badge) + a service worker for the app shell
- [x] On-screen keyboard for tap-to-add (pops up on any text field; settings toggle)
- [x] Phone page covers **all settings** (appearance, panels, holidays, effects, screen-off,
  family members, calendars, photos, email inbox, Spotify pins) → `static/phone.html` Settings view.
- [x] Portrait / mobile layout — responsive breakpoints so the wall display also
  works on a phone in portrait (stacks the calendar, compacts the nav)
- [ ] Verify real iCloud + Google two-way sync (connect from phone → Settings → Calendars)
- [x] Photo upload from the phone + **iCloud Shared Album** auto-slideshow
- [x] **Email import** (forward to a mailbox → approve events on the phone); .ics invites parsed exactly
- [x] **Routines** (step checklists w/ timers + stars), **kitchen timers**, **countdowns**
- [x] **Spotify** card + spotifyd on the wall
- [x] **Hardening:** constant-time PIN + per-IP brute-force lockout (`app/auth.py`); optional
  read-lock login gate for public URLs (`FAMILYHUB_LOCK_READS`, `static/auth.js`); Tailscale +
  local HTTPS (Caddy) guides → `docs/hardening.md`, `docs/tailscale.md`, `Caddyfile`

### Phase 2 — smart home control center (through HA)
- [x] **HA bridge + Home tab:** REST client (`app/services/ha_svc.py`, URL + long-lived
  token in `.env`) feeds big touch tiles grouped by type (lights, plugs, climate, doors,
  media, scenes, sensors). **Demo mode** (no creds, or `HA_DEMO=1`) shows sample devices so
  the tab is fully explorable before the HA Pi exists → `app/routers/ha.py`, `#page-home`
- [x] **Alarm:** tile + arm/disarm with an on-screen **PIN pad** (`/api/ha/alarm`, code
  passed straight to HA, never stored). *(Live arm/disarm needs `qolsysgw` on the HA Pi.)*
- [x] Tap-to-toggle lights/switches/fans/covers/locks; one-tap **scenes**
- [x] Graceful "Home Assistant offline" card
- [ ] HA **WebSocket** client for instant push updates (currently polls on tab open)
- [ ] Configure tiles/rooms from the phone (group by *room*, not just type)
- [x] **Roku TVs:** on-screen remote — power/volume/mute/D-pad/back/home/play + app launch
  (Netflix/YouTube/…) via `/api/ha/media`. *(A dedicated "Movie Time" scene still to add.)*
- [x] **Status bar** on the calendar: alarm state, open doors/garage, temps (taps to Home)
- [ ] **Two-way:** expose next event / chores left / grocery count back to HA for automations
- [x] HA setup checklist → `docs/home-assistant-setup.md`

### Phase 2.5 — security & network monitor
- [ ] **Security page:** devices on *your* LAN (name/vendor/IP) + **unknown-device alerts**
- [ ] Recent **failed logins** (hub + SSH) via fail2ban/auth logs
- [ ] Radar-sweep visual over the real data (flair, not fake neighbor-SSID "attacks")
- [ ] *(later)* True evil-twin/deauth detection via **Kismet** on a dedicated WiFi adapter (on the HA Pi)

### Phase 3 — optional, later
- [ ] Illustrated/3D floor plan — tap a room to toggle its lights (start 2D SVG, upgrade to 3D render; needs a floor plan of the house)
- [ ] Local voice control (no cloud if possible)

### TV Backlight (65" Hisense Roku TV) — planned, not started
Bias lighting behind the living-room TV, driven by Home Assistant off the Roku's state.

**Hardware (not built yet):** **Recommended: a pre-built WLED controller** (Athom WLED or
GLEDOPTO WLED unit, ~$20–25 — WLED pre-flashed, level shifter built in, screw terminals,
barrel jack; no soldering/flashing). Two power options:
- **Try first — TV-USB powered (Govee-style, no outlet needed):** 5 m **30 LEDs/m** strip,
  WLED power limit ≈ **800 mA**, brightness cap ≈ 25%. Soft bias light, and it powers
  on/off with the TV's USB port by itself (check whether the port stays live in standby; if
  it does, the HA automation handles off). ~$35 total.
- **Bright version:** 60 LEDs/m, dedicated **5 V 10 A** supply, **power injected at both
  ends**. Needs an outlet behind the TV. ~$60.
DIY alternative: bare ESP32 + WLED + external level shifter (saves ~$10, costs an evening).
Skip screen-sync for now: a built-in Roku TV has no HDMI path to capture. The Hisense Roku TV is already
in HA (`media_player.living_room_tv`). The strip joins HA via the **WLED integration** —
expected entity `light.tv_backlight`, **confirm the real name once discovered** and record
it here.

- [ ] 1. Build the hardware, flash WLED, set LED count + color order + a **power limit**,
      cap brightness at ~50%.
- [ ] 2. Add the device in HA (Settings → Devices & services → WLED, auto-discovered).
      Record the final entity IDs in this section:
      - `light.tv_backlight` → _TBD_
      - `media_player.living_room_tv` → confirmed
- [ ] 3. HA automation: strip **on** when the Roku `media_player` is `on` (optionally only
      after sunset); **off** when the TV is `off`, `standby`, or `unavailable`. Keep the
      entity IDs in one place (automation variables / a single package file); no secrets
      hardcoded.
- [ ] 4. Scenes: *movie* (dim warm white), *game mode*, etc. Surface them as scene tiles
      on the wall's Home tab (they appear automatically via `/api/ha/home`).
- [ ] 5. Back up WLED `cfg.json` + `presets.json` into the repo (`hardware/wled/`), with
      Wi-Fi credentials kept out of git (HA `secrets.yaml`; confirm `.gitignore` covers it).
- [ ] 6. Later: **screen sync** (HDMI capture + Hyperion → WLED).

## Hardware
- **Wall screen:** **HOWENS 15.6" IPS capacitive touchscreen** (ASIN B0D2D8CCY1), ~$150.
  Confirmed: FHD 1920×1080, 10-pt capacitive, VESA 75×75, **36.5 × 23 × 1 cm**, ports on the
  **bottom edge** (USB-B touch, audio, VGA, DVI, HDMI, DC 12V). Box includes HDMI cable, USB
  touch cable, 12V DC power brick, remote. Amazon confirms Raspberry Pi compatible.
- **Screen brain:** **C3 mini PC** drives the monitor + runs FamilyHub in kiosk Chromium (`setup/install-kiosk.sh`).
  Plus 27W USB-C PSU ($12), 64GB microSD ($12), active cooler ($8), and a **micro-HDMI→HDMI
  adapter ($6)** — the Pi 5 is micro-HDMI; the monitor's included HDMI cable is full-size.
  Touch plugs into a Pi USB-A port with the included USB-B cable (no extra cable needed).
- **HA brain:** existing **Pi 5 8GB**, headless, in a cupboard.
- **Couch control:** your **phone** (Home Assistant app + FamilyHub web). No portable screen.
- **Mounting:** the **VESA 75×75** makes this easy — a cheap VESA wall bracket, or 3D-print a VESA
  plate (wall) + tilt stand (counter). Parametric files in `hardware/` get sized to this screen.
- **Screen sleep:** the Pi-side `vcgencmd` night screen-off we already built applies here.

> Cost: ~$240 once, then **$0/yr** — vs Skylight ~$300 + ~$40–80/yr forever. Full 15" size, wired
> like the Skylight itself.

## How we work
- Dev branch `claude/tender-fermi-1g1upo` (never `main`). Small, reviewable commits.
- Baby-step deploy/test notes on the Pi after each phase.
- Simple, commented code; easy DB backups; no clever tricks.

## Idea backlog (brainstorm, Nov 2026)
Unordered. Effort: S = an evening, M = a weekend, L = a project. (No kids in the house yet — the kid-specific ideas are parked at the bottom for later.)

**Wall / family**
- Leave-the-house countdown: next event with a location → live drive time → "Leave for the dentist in 14 min" bar, spoken at T-5 (M) ★
- Who's-home strip: avatars from HA phone presence; "Rachell home since 5:12" (S) ★
- Morning dashboard mode 6–8 AM: big type — weather, each person's day, dinner plan, commute (M)
- Meal plan → pre-filled Walmart / Instacart cart (M)
- Guest/sitter QR view: house notes, emergency numbers, Wi-Fi, how the TV works (S)
- Photo of the day: "3 years ago today" from the iCloud album (S)
- Package radar: USPS/UPS emails via the mail importer + doorbell/porch motion snapshot (M)
- Birthday / anniversary memory with an auto "buy a gift" to-do (S)
- Weather dresser: "jacket and umbrella today" (S)
- 3D house as the night screensaver, slow orbit with real lights glowing (M)

**Home Assistant automations**
- Good Night scene: lights off, alarm home, lock, garage check (wall asks if open), TVs off, thermostat down, wall night mode (S after ratgdo) ★
- Arrive home: geofence → garage opens, porch + kitchen strips after dark, alarm disarms, "Welcome home" (M) + CarPlay manual button ★
- Away mode: 30 min empty → lights off, thermostat eco, lived-in lighting, alarm away; vacation events extend it (M)
- Freeze/storm alerts spoken on the wall; garage ThermoPro confirms (S)
- Laundry done: Zigbee vibration/power sensor on the washer → wall + phones + to-do (S) ★
- Leak sensors under water heater, washer, sinks (S)
- Motion-lit night path at 10 % between 11 PM and 6 AM (S)
- TV off when nobody's watching (motion quiet 45 min) (S)
- Wake-word satellite upstairs (HA Voice PE / ESP32) (S)
- Doorbell on the wall: the existing doorbell camera is tied to the IQ Panel (Alarm.com?). If it's Alarm.com, the
  HACS `alarmdotcom` integration gives ring + motion events (no video); ring → wall chime + snapshot if the
  camera exposes RTSP. Otherwise a Reolink/UniFi doorbell later gives full video on the wall + Roku PiP (M–L)

**Bigger builds**
- Energy dashboard: Emporia Vue per-circuit power → today's cost, dryer running, water heater load (L)
- TV backlight synced to the Roku picture (see above)

**Parked until there are kids**
- Chore photo proof · screen-time bank (stars → Roku minutes) · bedtime nudge (LEDs dim, Roku off) ·
  school lunch menu + bus delays · kid check-in on the wall · kid tablets in kid mode · kid weather dresser

★ = suggested first picks: Good Night scene, Arrive home, Leave-the-house countdown, Laundry done, Who's home.
