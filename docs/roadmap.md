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
| Battery/UPS | **Skip for v1** (unplug/replug is fine) |
| Navigation | **Bottom nav bar**: Calendar · Home · Chores · Lists · Photos *(built)* |
| Disk encryption | Skip on the wall tablet (low value, headless hassle) |

## Phases

### Phase 0 — housekeeping
- [ ] `.env` + `.env.example` (secrets gitignored, server-side only)
- [ ] One-page **README for the family** (how to use, wall↔counter, what to do if it freezes)

### Phase 1 — finish the calendar (comes first, fully working)
- [x] Bottom-nav multi-page shell
- [x] Chore check-off celebration
- [x] Day/night hero banner · scheduled screen-off + wake · kids' scoreboard
- [ ] Agenda view (4th calendar view)
- [ ] Offline caching (service worker: cached calendar/weather, sync on reconnect)
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
- **Wall screen:** 15.6" capacitive **touchscreen** (Pi-friendly).
- **Screen brain:** a **second Raspberry Pi** (4GB is plenty) — the 8GB is now the HA box.
- **HA brain:** existing **Pi 5 8GB** (headless, in a cupboard).
- **Mounting:** 3D-printed bezel + French cleat (wall) + tilt stand (counter) — parametric files
  in `hardware/`. You have the printer, so just filament + M3 screws + anchors.
- See `README.md` → `hardware/` for the full parts list and current Amazon picks.

## How we work
- Dev branch `claude/tender-fermi-1g1upo` (never `main`). Small, reviewable commits.
- Baby-step deploy/test notes on the Pi after each phase.
- Simple, commented code; easy DB backups; no clever tricks.
