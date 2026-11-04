# FamilyHub — hardware & 3D-printed mount

Everything you need to turn a Raspberry Pi + a 15.6" touchscreen into the wall
display. The print files are parametric OpenSCAD (`familyhub-mount.scad`) so they
fit *your* exact monitor.

## Shopping list — current build (Intel N100 brain, ~$325)

Because Raspberry Pi 5 prices spiked in 2026, the screen "brain" is now a small
**Intel N100 mini PC** — cheaper than a Pi 5 kit, faster, x86 (no Pi quirks), and
it has a **full-size HDMI** so there's no micro-HDMI adapter to buy.

| Part | ~Cost | Amazon search | Notes |
|---|---|---|---|
| **15.6" IPS capacitive touchscreen** | $150 | `15.6 inch IPS capacitive touchscreen HDMI VESA` (e.g. HOWENS B0D2D8CCY1) | VESA 75×75; HDMI + USB-touch cable + 12V brick usually in box. Want it bigger for the kitchen? search `21.5 inch touchscreen monitor HDMI`. |
| **Intel N100 mini PC** (16GB/512GB) | $150 | `Intel N100 mini PC 16GB` (Beelink / GMKtec / Trigkey) | Runs FamilyHub in kiosk Chrome/Edge. RAM, SSD, case, power brick all included. |
| HDMI cable | $0–7 | `HDMI cable 6ft` | Usually included with the monitor; buy only if not. |
| USB-A → USB-B touch cable | $0 | — | Included with the touchscreen (carries touch to the mini PC). |
| VESA wall mount **or** 3D print | $0–13 | `VESA 75x75 monitor wall mount` | You can print the mount (you have the printer) or grab a cheap bracket. |
| M4 screws + wall anchors | ~$6 | `M4 screw assortment wall anchors` | For the VESA mount / cleat. |
| Filament (PLA/PETG) | ~$5 | — | Only if you print the mount. You have it. |

### Home Assistant "brain" (smart home / alarm / TVs)
Runs **separately** from the screen so a FamilyHub update can never take the house down.
- **Chosen build: a second N100** (~$150) runs Home Assistant (HAOS installed bare, or HA in
  Docker/Proxmox). x86 runs HA great and leaves headroom. So: **N100 #1 = screen/FamilyHub,
  N100 #2 = Home Assistant.** (No Pi 5 needed — it can be sold.)
- Alternative: **Home Assistant Green** (~$99) if you'd rather have a tiny purpose-built box.

### Voice — the touchscreen has NO mic or (usually) speaker
The 15.6" touchscreen is display + touch only. Pick the level of voice you want:

**A) Tap-to-talk on the wall** (built into FamilyHub — tap the mic, speak, it acts + replies aloud).
Needs a **mic + speaker on the N100**. Cleanest: one USB speakerphone on the counter.
- **USB speakerphone** (`USB speakerphone conference mic`, ~$30–45, e.g. Anker PowerConf / eMeet) — mic **and** speaker in one, great kitchen pickup. **Best pick.**
- Budget: a **USB mini microphone** (~$12) + the monitor's own speakers if it has them (check the listing; many 15.6" panels include small speakers + a 3.5 mm jack). Add cheap **USB speakers** (~$12) if not.

**B) Hands-free "Hey …" wake word — CHOSEN: openWakeWord (DIY, no extra hardware).**
Runs entirely on our own boxes, private (no Google/Amazon cloud):
1. On the HA N100, enable the **openWakeWord** add-on (it does the "Hey Jarvis" detection).
2. On the kitchen N100, run a **Wyoming satellite** that streams the **USB speakerphone's**
   mic to HA and plays replies back on its speaker.
So the only hardware is the **USB speakerphone we already listed** — the wake word is all
software. (Optional later: add an **ESP32-S3 Wyoming satellite** ~$10–15, or the
plug-and-play *Home Assistant Voice PE* ~$60, to add voice in other rooms.)

**Phone voice:** the **Home Assistant companion app** has built-in Assist voice that works
on iPhone/Android from anywhere — so "turn on the kitchen lights" works from your phone too.
(FamilyHub's *web-app* mic works on Android/desktop Chrome, but iOS Safari doesn't support
the browser speech API, so use the HA app for phone voice on an iPhone.)

> **Alarm needs no new hardware** — the Qolsys IQ Panel's built-in 3rd-party
> automation (enabled with your dealer code) talks to HA over the LAN via `qolsysgw`.

**Rough total for the wall unit: ~$300–325** once (screen + N100 + mount/screws),
reusing the Pi 5 for HA. vs Skylight ~$300 up front **plus ~$40–80/yr forever**.

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
