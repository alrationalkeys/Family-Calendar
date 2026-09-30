# FamilyHub — hardware & 3D-printed mount

Everything you need to turn a Raspberry Pi + a 15.6" touchscreen into the wall
display. The print files are parametric OpenSCAD (`familyhub-mount.scad`) so they
fit *your* exact monitor.

## Shopping list (touch build, ~$210–250)

| Part | ~Cost | Notes |
|---|---|---|
| Raspberry Pi 5 (4GB) | $75 | 4GB floor for kiosk Chromium. |
| 27W USB-C PSU (5V/5A) | $12 | Get the official Pi 5 supply. |
| microSD 32GB+ (A2) | $10–25 | Or an NVMe HAT + SSD for snappier boots. |
| 15.6" IPS **touchscreen** monitor | $120–160 | See picks below. |
| Filament (PLA/PETG) | ~$5 | Bezel + French cleat + optional stand. |
| M3 screws + wall anchors | ~$5 | For the cleat. |

## Touchscreen picks (all known to play nice with a Pi)

Buy **capacitive multi-touch**, and confirm the listing mentions **driver-free /
plug-and-play** and ideally Raspberry Pi. Touch rides a USB line (USB-C or a
separate USB-touch cable) back to the Pi — make sure that cable is included.

1. **Waveshare 15.6" HDMI capacitive touchscreen** — the safe pick. Waveshare
   documents Raspberry Pi use explicitly and it's driver-free on Pi OS.
2. **SunFounder / Elecrow 15.6" touchscreen for Raspberry Pi** — sold as
   Pi-companion displays, so touch works out of the box.
3. **Generic USB-C portable touch monitor** (UPERFECT / KYY / Cocopar and similar)
   — cheapest, usually work, but check recent reviews that mention Linux/Pi and a
   *USB-C to USB-A* cable so the Pi can read touch. Avoid "Windows driver required."

> Prices/models drift and I can't see live listings from here — verify current
> availability and that the box includes the USB touch cable + an HDMI or USB-C
> video cable that matches the Pi 5's full-size HDMI (you may need a
> micro-HDMI→HDMI or USB-C cable).

## The printed parts

Open `familyhub-mount.scad` in OpenSCAD (free). Set the `part` dropdown (or the
Customizer) to render each piece.

| Part | Qty | What it is |
|---|---|---|
| `bezel` | 1 | Frame the screen drops into; front lip hides the black border. |
| `cleat_wall` | 1 | French-cleat half that screws to the wall. |
| `cleat_frame` | 1 | French-cleat half that mounts to the bezel back. |
| `stand_foot` | 2 | Optional easel feet for the countertop / Echo-Show look. |

### Step 1 — measure your monitor
Edit the **YOUR MONITOR** block at the top of the `.scad`:
- `mon_w`, `mon_h`, `mon_t` — outer width, height, thickness (mm).
- `lip` — the black border width; the frame overlaps this. Keep it ≤ the
  narrowest border so you don't cover pixels.
- `ports[]` — one row per connector: `[side, position_from_left/top, width, height]`.
  Measure to the center of each port and add ~2mm slack.

### Step 2 — test the fit cheaply
Set `test_corner = true`, render (`F6`), export, and print just one corner
(~20 min). Check that the screen slides in and the lip sits flat. Adjust `clear`
(looser/tighter) or `lip` and reprint the corner until it's right.

### Step 3 — print for real
- **Bezel:** face-down, 0.2mm layers, 3 perimeters, 15–20% infill, no supports.
  A 15.6" frame is a long print (≈8–12h) — run it once the corner fits.
- **Cleats:** flat, same settings. The 45° bevels self-support.
- **Stand feet:** print two, on their flat side.

### Step 4 — mount
- **Wall:** screw `cleat_wall` to studs/anchors (use a level), attach
  `cleat_frame` to the bezel back, hang it — it lifts off for cable access.
- **Counter:** clip the two `stand_foot` pieces onto the bezel's bottom edge.

## Wiring
Pi 5 → monitor over HDMI (or USB-C). USB-C or the USB-touch cable → a Pi USB
port for touch. PSU → Pi. That's it — the wall app is at `http://localhost:8000`
(see the top-level README for software setup and `kiosk.sh` for full-screen boot).
