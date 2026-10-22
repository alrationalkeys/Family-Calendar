# FamilyHub — hardware & 3D-printed mount

Everything you need to turn a Raspberry Pi + a 15.6" touchscreen into the wall
display. The print files are parametric OpenSCAD (`familyhub-mount.scad`) so they
fit *your* exact monitor.

## Shopping list (confirmed build, ~$248)

| Part | ~Cost | Notes |
|---|---|---|
| **HOWENS 15.6" IPS touchscreen** (B0D2D8CCY1) | $150 | VESA 75×75, HDMI+USB touch+12V brick in box. |
| Raspberry Pi 5 (4GB) | $60 | Drives the screen + runs FamilyHub. |
| 27W USB-C PSU (5V/5A) | $12 | Official Pi 5 supply. |
| microSD 64GB (A2) | $12 | Or an NVMe HAT + SSD for snappier boots. |
| Pi 5 active cooler | $8 | It runs warm behind the screen. |
| **micro-HDMI → HDMI adapter** | $6 | Pi 5 is micro-HDMI; the monitor's cable is full-size. |
| Filament (PLA/PETG) | ~$5 | Back case + cleats + stand (you have the printer). |
| M4 + M2.5 screws, wall anchors | ~$6 | M4 for VESA/cleat, M2.5 for the Pi. |

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

## The printed parts (tuned for the HOWENS 15.6" + Pi 5)

Clean, Skylight-style install: the **Pi and all cabling hide in a back case** that bolts to
the screen's **VESA 75×75** holes, and the whole display **lifts off a French cleat** onto a
counter stand — no tools. Open `familyhub-mount.scad` in OpenSCAD (free) and set `part`.

| Part | Qty | What it is |
|---|---|---|
| `back_case` | 1 | Box that bolts to the VESA holes — holds the Pi 5, vents heat, hides every cable, routes them down to the bottom ports. |
| `cleat_case` | 1 | French-cleat half that bolts to the back case. |
| `cleat_wall` | 1 | French-cleat half that screws to the wall (the display hangs on it). |
| `stand` | 1 | Counter easel; its tongue mates `cleat_case`, so the display drops from wall → stand in seconds. |
| `frame_seg` | 2–4 | **Optional** cosmetic front frame. 365mm > the Kobra's 250mm bed, so it prints as **joinable segments** (2 long + 2 short) you pin/glue at the corners. |
| `test_vesa` / `test_pi` | 1 ea | Small coupons — **print these first**. |

> **Bed-size reality (Anycubic Kobra S1 ≈ 250mm):** the back case, cleats, and stand all
> fit. A one-piece 365mm front frame does **not** — that's why the frame is segmented, and
> why the clean look is built around the *back case* (the front just uses the monitor's own
> slim bezel unless you want the framed look).

### Step 1 — print the test coupons first (~15 min)
Render `test_vesa` and `test_pi`, print both, and check: VESA screws thread into the
monitor's holes, and a Pi 5 bolts onto the standoff pattern. Tweak `vesa` / `pi_hx` / `pi_hy`
if anything's off before the big print.

### Step 2 — print the case + mounts
- `back_case`: **front-plate-down (cavity up)**, 0.2mm, 3 perimeters, 20% infill, no supports (~5–6h).
- `cleat_case`, `cleat_wall`, `stand`: flat; the 45° cleat bevels self-support.
- Vents are on by default (`vent = true`) — mount the case **vents-up** so Pi heat rises out.

### Step 3 — assemble & mount
1. Bolt `back_case` to the screen's **VESA 75** holes (M4).
2. Mount the Pi 5 on the standoffs (M2.5); plug in HDMI (via the micro-HDMI adapter), the
   USB touch cable, and power. Route all cables out the bottom slot.
3. Bolt `cleat_case` to the case's rear bosses.
4. **Wall:** screw `cleat_wall` to studs/anchors (use a level) → hang the display on it.
   **Counter:** drop the display's `cleat_case` onto the `stand` tongue.

### Step 4 (optional) — the framed look
Print `frame_seg` ×2 long + ×2 short, pin/glue at the corners, and set it over the front.
Tune `frame_face` (border width) and `frame_lip` (overlap — keep ≤ the screen's real black border).

## Wiring
Pi 5 **micro-HDMI → (adapter) → HDMI** into the monitor · monitor's **USB-B touch cable → a
Pi USB-A port** · monitor's **12V DC brick** (its own power) · **27W USB-C** to the Pi. All
cables tuck through the back-case bottom slot. Wall app boots full-screen via `kiosk.sh`.
