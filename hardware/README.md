# FamilyHub — hardware & 3D-printed mount

Everything you need to turn a mini PC + a 15.6" touchscreen into the wall
display. The print files are parametric OpenSCAD (`familyhub-mount.scad`) so they
fit *your* exact monitor.

## Shopping list — current build (two matching C3 mini PCs, Pi 5 sold)

> **2026 price note:** both Raspberry Pis *and* mini PCs spiked (global RAM/SSD
> shortage). A new 16GB/512GB N100 is ~$340–400 now, and a Pi 5 8GB resells for
> ~$100–150. So the build is **two cheap i3 mini PCs** — one drives the screen, one is
> the headless Home Assistant box — funded partly by selling the Pi 5.

| Part | ~Cost | Amazon listing | Notes |
|---|---|---|---|
| **Forzola 15.6" FHD Touchscreen Monitor Industrial (HDMI/VGA/DVI, with remote)** | $140 | `15.6 inch touchscreen monitor industrial HDMI VESA` | **Chosen.** 10-pt capacitive, 300 nit IPS, **VESA 75×75**, 365×223×10 mm (23 mm at the port hump, 170 mm port strip along the bottom). In the box: HDMI cable, USB-B touch cable, 12V brick, remote. Dual speakers + audio out. |
| **C3 Mini PC, Intel i3-5005U, 8GB / 512GB** (origimagic) — **×2** | $170 each | `C3 Mini PC i3-5005U 8G 512G` | 2× HDMI, 4× USB-A + USB-C, Gigabit LAN, Wi-Fi 5, BT 5.0, **Auto Power On + Wake-on-LAN**, Linux-compatible, 15 W, 128×127×43 mm. #1 = FamilyHub kiosk + voice satellite behind the screen. #2 = Home Assistant OS, headless. |
| **USB speakerphone** (kitchen mic+speaker) | $35 | `USB speakerphone conference mic` (Anker PowerConf / eMeet) | Mic + speaker in one, for the wall voice / openWakeWord. |
| M4 screws + wall anchors | ~$6 | `M4 screw assortment wall anchors` | For the VESA bolts / cleat. The mount itself is 3D-printed (below). |

**≈ $520 total**, minus the Pi 5 sale (~$100–150) → **≈ $370–420 net.** No HDMI cable or
VESA bracket to buy — the monitor ships with cables and the mount is printed.

> Skip the thin "portable" touch monitors (CAPERAVE / UPERFECT / InnoView / cocopar):
> they work electrically but have no VESA holes and power over USB-C. The industrial
> kiosk panel bolts straight to the printed case.

### Home Assistant "brain" (smart home / alarm / TVs)
Runs **separately** from the screen so a FamilyHub reboot/update can never take the house
(or alarm) down. Nothing about it "pairs" with the screen — FamilyHub only ever talks to it
over the LAN via `HA_URL`, so the HA box could be anything.
- **Chosen: the second C3 mini PC.** Boot the HAOS installer from a USB stick, install to
  its SSD, done. Headless in a cupboard — plug in **Ethernet** (it's the alarm bridge; don't
  rely on Wi-Fi) and power, enable **Auto Power On** in BIOS so it recovers from outages.
- Faster than a Pi 5 for HA, ~10–15 W. Matching hardware with the screen box means one
  spare-parts story.
- Alternatives if you'd rather not buy a second box: keep the Pi 5 (~5–8 W, HAOS on SD/NVMe)
  or a **Home Assistant Green** (~$99). Running HA *on the screen box* is possible but a
  reboot/update then drops the alarm too — not worth it.

### Voice — the touchscreen has NO mic or (usually) speaker
The 15.6" touchscreen is display + touch only. Pick the level of voice you want:

**A) Tap-to-talk on the wall** (built into FamilyHub — tap the mic, speak, it acts + replies aloud).
Needs a **mic + speaker on the screen C3**. Cleanest: one USB speakerphone on the counter.
- **USB speakerphone** (`USB speakerphone conference mic`, ~$30–45, e.g. Anker PowerConf / eMeet) — mic **and** speaker in one, great kitchen pickup. **Best pick.**
- Budget: a **USB mini microphone** (~$12) + the monitor's own speakers if it has them (check the listing; many 15.6" panels include small speakers + a 3.5 mm jack). Add cheap **USB speakers** (~$12) if not.

**B) Hands-free "Hey …" wake word — CHOSEN: openWakeWord (DIY, no extra hardware).**
Runs entirely on our own boxes, private (no Google/Amazon cloud):
1. On the HA C3, enable the **openWakeWord** add-on (it does the "Hey Jarvis" detection).
2. On the kitchen (screen) C3, run a **Wyoming satellite** that streams the **USB speakerphone's**
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

**Rough total for the wall unit: ~$350** once (screen + one C3 + speakerphone + screws).
vs Skylight ~$300 up front **plus ~$40–80/yr forever**.

## Touchscreen alternatives (if the Forzola is out of stock)

Buy **capacitive multi-touch** with **VESA 75×75 holes** and a separate **USB-touch cable**
(USB-A end for the C3). Confirm the listing says **driver-free / plug-and-play**; avoid
"Windows driver required." Any "industrial / kiosk / POS" 15.6" HDMI touch panel with a
VESA badge is the same form factor as the Forzola.

> Prices/models drift and I can't see live listings from here — verify current
> availability and that the box includes the USB touch cable + HDMI cable.

## The printed parts (being retuned for the Forzola 15.6" + C3 mini PC)

> The `.scad` was originally dimensioned around a HOWENS panel + Pi 5. Now that the parts
> are picked, the back case gets re-sized for the **C3 (128×127×43 mm)** and the Forzola's
> **23 mm port hump / 170 mm port strip**. Send a photo of the back of the screen when it
> arrives so the VESA hole depth can be checked before printing.

Clean, Skylight-style install: the **mini PC and all cabling hide in a back case** that bolts to
the screen's **VESA 75×75** holes, and the whole display **lifts off a French cleat** onto a
counter stand — no tools. Open `familyhub-mount.scad` in OpenSCAD (free) and set `part`.

| Part | Qty | What it is |
|---|---|---|
| `back_case` | 1 | Box that bolts to the VESA holes — holds the C3 mini PC, vents heat (fan intake faces out), hides every cable, routes them down to the bottom ports. |
| `cleat_case` | 1 | French-cleat half that bolts to the back case. |
| `cleat_wall` | 1 | French-cleat half that screws to the wall (the display hangs on it). |
| `stand` | 1 | Counter easel; its tongue mates `cleat_case`, so the display drops from wall → stand in seconds. |
| `frame_seg` | 2–4 | **Optional** cosmetic front frame. 365mm > the Kobra's 250mm bed, so it prints as **joinable segments** (2 long + 2 short) you pin/glue at the corners. |
| `test_vesa` / `test_pi` | 1 ea | Small coupons — **print these first**. (`test_pi` becomes a C3 footprint coupon in the retune.) |

> **Bed-size reality (Anycubic Kobra S1 ≈ 250mm):** the back case, cleats, and stand all
> fit. A one-piece 365mm front frame does **not** — that's why the frame is segmented, and
> why the clean look is built around the *back case* (the front just uses the monitor's own
> slim bezel unless you want the framed look).

### Step 1 — print the test coupons first (~15 min)
Render `test_vesa` and `test_pi`, print both, and check: VESA screws thread into the
monitor's holes, and the mini PC sits in its cradle. Tweak `vesa` / cradle dims
if anything's off before the big print.

### Step 2 — print the case + mounts
- `back_case`: **front-plate-down (cavity up)**, 0.2mm, 3 perimeters, 20% infill, no supports (~5–6h).
- `cleat_case`, `cleat_wall`, `stand`: flat; the 45° cleat bevels self-support.
- Vents are on by default (`vent = true`) — mount the case **vents-up** so the C3's fan
  exhaust rises out.

### Step 3 — assemble & mount
1. Bolt `back_case` to the screen's **VESA 75** holes (M4).
2. Seat the C3 in its cradle; plug in HDMI, the USB touch cable, the USB speakerphone,
   and power. Route all cables out the bottom slot.
3. Bolt `cleat_case` to the case's rear bosses.
4. **Wall:** screw `cleat_wall` to studs/anchors (use a level) → hang the display on it.
   **Counter:** drop the display's `cleat_case` onto the `stand` tongue.

### Step 4 (optional) — the framed look
Print `frame_seg` ×2 long + ×2 short, pin/glue at the corners, and set it over the front.
Tune `frame_face` (border width) and `frame_lip` (overlap — keep ≤ the screen's real black border).

## Wiring
C3 **HDMI → HDMI** into the monitor (cable in the monitor box) · monitor's **USB-B touch
cable → a C3 USB-A port** · **USB speakerphone → C3 USB-A** · monitor's **12V DC brick** (its
own power) · C3's own **DC brick**. Ethernet to the C3 if you can run one. All cables tuck
through the back-case bottom slot. Wall app boots full-screen via `kiosk.sh`.

The HA C3 lives elsewhere (cupboard/closet): **power + Ethernet only**, nothing else plugged in.
