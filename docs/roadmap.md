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
| Smart home | Through **Home Assistant** on the spare **Pi 5 8GB** |
| Alarm | **Qolsys IQ Panel** via HA + `qolsysgw` (have dealer code). Start **status-only**, add arm/**disarm** behind a PIN pad |
| TVs | **Roku** (Hisense/TCL) via HA's built-in Roku integration — local ECP, auto-discovered. Need "Fast TV Start" on each TV to power on |
| Screen | **Wired 15.6" IPS capacitive touchscreen** (10-pt, HDMI, VESA 75×75) on the wall — matches the 15" Skylight, which is itself plug-in (no battery). ~$150 (e.g. HOWENS 15.6"). Confirm the box has a USB touch cable + reviews show Pi touch works |
| Couch control | **Your phone** — Home Assistant app + FamilyHub web page on the LAN. No portable screen needed; the wall screen stays wired |
| Screen brain | **Pi 5 4GB** drives the monitor + runs FamilyHub in kiosk Chromium. HA stays on the separate **8GB Pi** |
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
- [ ] On-screen keyboard for tap-to-add
- [ ] Phone page covers **all settings** + photo upload (`familyhub.local`)
- [ ] Portrait/rotatable layout (landscape ships first)
- [ ] Verify real iCloud + Google two-way sync
- [ ] **Hardening:** Tailscale, local HTTPS (Caddy), stronger auth + lockout

### Phase 2 — smart home control center (through HA)
- [ ] HA WebSocket client (URL + long-lived token in `.env`), instant updates
- [ ] **Home tab:** big touch tiles grouped by room, configured from the phone (live list from HA)
- [ ] **Alarm:** status in the top bar; arm/disarm with a **PIN pad** (`qolsysgw`)
- [ ] **Roku TVs:** power/volume/app-launch/on-screen remote + "Movie Time" scene
- [ ] One-tap **scenes** (Good Night, Leaving, Movie Time, …)
- [ ] **Status bar** on the calendar: alarm state, open doors/garage, temps, alerts
- [ ] **Two-way:** expose next event / chores left / grocery count back to HA for automations
- [ ] Graceful "Home Assistant offline" state
- [ ] HA setup checklist → `docs/home-assistant-setup.md` *(done)*

### Phase 2.5 — security & network monitor
- [ ] **Security page:** devices on *your* LAN (name/vendor/IP) + **unknown-device alerts**
- [ ] Recent **failed logins** (hub + SSH) via fail2ban/auth logs
- [ ] Radar-sweep visual over the real data (flair, not fake neighbor-SSID "attacks")
- [ ] *(later)* True evil-twin/deauth detection via **Kismet** on a dedicated WiFi adapter (on the HA Pi)

### Phase 3 — optional, later
- [ ] Illustrated/3D floor plan — tap a room to toggle its lights (start 2D SVG, upgrade to 3D render; needs a floor plan of the house)
- [ ] Local voice control (no cloud if possible)

## Hardware
- **Wall screen:** **HOWENS 15.6" IPS capacitive touchscreen** (ASIN B0D2D8CCY1), ~$150.
  Confirmed: FHD 1920×1080, 10-pt capacitive, VESA 75×75, **36.5 × 23 × 1 cm**, ports on the
  **bottom edge** (USB-B touch, audio, VGA, DVI, HDMI, DC 12V). Box includes HDMI cable, USB
  touch cable, 12V DC power brick, remote. Amazon confirms Raspberry Pi compatible.
- **Screen brain:** **Pi 5 4GB** (~$60) drives the monitor + runs FamilyHub in kiosk Chromium.
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
