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
| Screen | **~15.6" Android tablet** (matches the 15" Skylight) — wireless + battery, runs FamilyHub in a kiosk browser. Budget off-brand at 15"; reliable fallback is an 11" Samsung Galaxy Tab A9+ |
| Backend host | **No 2nd Pi needed** — FamilyHub runs on the 8GB Pi (isolated from HA) or a cheap Pi Zero 2 W; the tablet just displays it |
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
- **Wall screen:** **~15.6" Android tablet** (wireless + battery) running FamilyHub in a kiosk
  browser (e.g. Fully Kiosk Browser). Matches the 15" Skylight; carry it wall ↔ counter, charge
  on the mount. Search Amazon: `15.6 inch Android tablet`. Reliable smaller option: 11" Samsung
  Galaxy Tab A9+.
- **FamilyHub backend:** the existing **Pi 5 8GB** (FamilyHub in a container, isolated from HA) or
  a cheap **Pi Zero 2 W** for strict separation. **No second full Pi needed.**
- **HA brain:** **Pi 5 8GB**, headless, in a cupboard. (Shared with FamilyHub backend if containerized.)
- **Mounting:** 3D-printed **magnetic tablet wall mount** + **counter tilt stand** — the parametric
  files in `hardware/` get re-sized to the tablet's dimensions once it's chosen. You have the printer.
- **Battery care (optional):** a smart plug to top the tablet to ~80% avoids 24/7-charging wear.

> Cost: ~$150–200 once, then **$0/yr** — vs Skylight ~$300 + ~$40–80/yr forever.

## How we work
- Dev branch `claude/tender-fermi-1g1upo` (never `main`). Small, reviewable commits.
- Baby-step deploy/test notes on the Pi after each phase.
- Simple, commented code; easy DB backups; no clever tricks.
