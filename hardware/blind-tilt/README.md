# FamilyHub blind tilt (DIY, battery + solar, no wires to the wall)

Turns the tilt wand on horizontal blinds so Home Assistant / FamilyHub can open and close the slats.
Status: **design started Nov 16, 2026. Nothing below is built or tested yet.**

## How it works
A small box sticks to the headrail next to the wand (3M VHB tape, no screws). The wand passes down through a hollow
gear inside the box; a split collar on that gear clamps the wand. A tiny gearmotor turns the gear, so the wand turns
exactly as if you twisted it by hand. You can still twist the wand yourself: the collar is a friction grip.

## Electronics (per window, about $25-30)
| Part | Why | ~Cost |
|---|---|---|
| ESP32-C6 "SuperMini" board | Has Zigbee, so it joins the SONOFF Zigbee stick already on Home Assistant; no WiFi = long battery life | $6 |
| N20 gearmotor, 6 V, ~100 RPM, with encoder | Small, strong enough for a wand; the encoder counts turns so it knows the slat position | $6 |
| DRV8833 motor driver | Drives the motor; draws almost nothing when asleep | $2 |
| 18650 lithium cell + holder | The battery | $6 |
| Solar charge board (CN3065 or TP4056 with protection) | Charges the cell from the panel, protects it | $2-4 |
| 6 V 1 W solar panel (about 110 x 60 mm) | Sticks to the glass at the top of the window, short thin wire to the box | $5 |
| 3M VHB tape, M2/M3 screws, wire | | $3 |

It shows up in Home Assistant as a blind with tilt (Zigbee "window covering"), so FamilyHub's routines, Good night /
Leaving and voice all work with it.

## Printed parts (to design once the measurements are in)
1. Box (motor pocket, gear seat, battery bay, electronics bay) + lid
2. Hollow gear in two halves + clamp collar (goes around the wand without taking the wand off)
3. Motor pinion
4. `wand-gauge.stl` - **print this first** (15 min): a card with round and hex holes, 7-13 mm

## What I need from Alex
1. Print `wand-gauge.stl`, slide the wand through: which is the tightest hole it passes, and round or hex row?
2. Photo of the top of one blind where the wand hooks on (straight on, and from the side).
3. Space: from the wand to the nearest end of the headrail, and from the headrail front to the glass.
4. How many full twists of the wand from fully closed one way to fully closed the other.
5. Is there a valance (decorative front strip) the box could hide behind?

## Plan
1. Gauge + photos (today) -> 2. first box for ONE window, run from USB on the bench -> 3. add battery + solar and
measure how long it lasts -> 4. print and build the other 5.

## Notes from Alex's photos (Nov 16, 2026)
- 2" faux-wood blinds (heavy), white steel headrail open at the top, crown-style valance on clear clips with end returns
  (valance ends about 1" past the blind). Wand: round, hooks onto the tilter stem at the front-bottom of the headrail
  with a clear sleeve. **5 full turns** closed-to-closed.
- The top slat sits right under the headrail, so nothing can hang below it: the motor has to live IN FRONT of the
  headrail, behind the valance, at the tilter stem.
- Heavy slats + 5 turns = the MG90S half-turn servos are out. Motor: N20 6 V, slow/strong ratio (1:298, ~30-45 RPM)
  with encoder -> 5 turns in about 8-10 s.
- Layout to design: slim motor pod behind the valance at the stem; battery + controller lying on top of / inside the
  open headrail (hidden by the valance); solar panel on the glass at the top; thin wires between.
- Still needed: gap headrail-front to valance-back, how far the valance hangs below the headrail, wand top diameter
  (gauge), and keep-the-wand vs replace-the-wand.
