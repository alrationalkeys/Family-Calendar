# To do — Wednesday, Nov 11

## First thing
- [ ] **Update the wall:** phone → Settings → The wall → Update the wall. Then reload.
- [ ] **Family PIN:** phone → Settings → Family PIN → 4–8 digits → Turn on. Enter it once on the wall.

## Zigbee stick arrives — move the kitchen off Alexa + Aqara (in this order)
- [ ] Plug the stick into the Home Assistant box on a **short USB extension** (~1 ft away from the box).
      Accept the Zigbee setup Home Assistant offers.
- [ ] **Alexa app:** delete Fridge Upper, Stove Upper, Fridge Lower, Stove Lower, and "First motion sensor".
- [ ] **Aqara app:** under Hub M2, delete the Motion Sensor and the Button. Screenshot anything in
      Configure Automations first and send it.
- [ ] **Home Assistant → Zigbee → Add device**, then reset each device while it searches:
  - [ ] Four kitchen GLEDOPTO controllers — power-cycle ~5 times (≈2 s on, 2 s off) until the strip flashes.
  - [ ] Aqara motion sensor — hold its button ~5 s until the light blinks; pair near the stick,
        tap the button every few seconds until setup finishes, then move it back.
  - [ ] Aqara button — same as the sensor.
- [ ] **Rename the entities** to: `light.fridge_upper`, `light.stove_upper`, `light.fridge_lower`,
      `light.stove_lower`, `binary_sensor.kitchen_motion`, `sensor.kitchen_illuminance`
      (Back Patio Govee → `light.back_patio`).
- [ ] Put `docs/ha/kitchen-lights.yaml` in Home Assistant's `/config/packages/` and restart.
- [ ] **Alexa app:** turn the kitchen + Govee routines OFF (keep them for a day in case).
- [ ] After a day of it working: **unplug the Echo and the Aqara Hub M2.**
- [ ] Anything that won't pair or shows a strange name → screenshot to Claude.

## Test on the real gear
- [ ] Status bar says **"Door to garage open"** (not "Garage Door") when the house→garage door is open.
- [ ] **Doorbell:** press it — wall pops the camera + chimes + speaks; a Roku that's on flashes the picture;
      phones get a notification with the picture.
- [ ] **Live camera:** open a camera on the wall and on the phone — does it play live or stay a still?
- [ ] **Good Night** and **Leaving** buttons on the wall (lights, locks, alarm, thermostat).
- [x] **Sleep mode** works (tested Nov 11 with the panel's Sleep scene). ~~arm the IQ Panel for the night — the wall should go dark right away and stay dark
      (a tap shows it for a minute). Disarm in the morning — it comes back. If it doesn't go dark, tell Claude
      what the panel's arming mode is called (Night / Sleep / Stay).
- [ ] **Leave-by:** add an event with a "Where" ~45 min out and watch the wall's status bar.

## Set up the two unused Surety outdoor AI cameras
- [ ] Mount near outdoor power, under the eaves ~8–10 ft up (suggested: driveway/garage, and the side by the garage side door).
      Check phone Wi-Fi at each spot first.
- [ ] Alarm.com app → Settings → Video Devices → Add. Name them clearly ("Driveway Camera", "Side Yard Camera").
- [ ] Home Assistant → Devices & services → Alarm.com → ⋮ → Reload. They appear on the wall + phone automatically.

## Flaky door sensor (PowerG, always the same door)
- [ ] New battery (PG9303 = CR2032, PG9945 = CR123A), fix the magnet gap (≤ ½ in, marks lined up, off metal),
      test 5× at the panel's sensor screen and compare its signal to a good door. Still bad → Surety support for a swap.

## Install the Home Assistant routines (first thing — see the chat for step-by-step)
- [ ] File editor add-on → add `homeassistant:` / `packages: !include_dir_named packages` to configuration.yaml → make a `packages` folder.
- [ ] Add `peak-thermostat.yaml` and `outdoor-lights.yaml` (kitchen-lights.yaml after the Zigbee move). Check entity names.
- [ ] Developer tools → Check configuration → Restart. FamilyHub Settings → Automations should show them installed.
- [ ] Alarm.com: thermostat schedule Heat 67° 6 PM–9 AM, 60° 9 AM–6 PM, Cool 70° all day; turn OFF the 4 light schedules.

## Thermostat peak hours
- [x] Santee Cooper hours set (summer 3–6 PM, winter 6–9 AM). Every day, weekends included.
- [ ] Install `docs/ha/peak-thermostat.yaml` in /config/packages/ (check the two thermostat entity names), restart.
- [ ] Then simplify the Alarm.com schedule on BOTH thermostats, once: Heat 67° 6 PM–9 AM, 60° 9 AM–6 PM; Cool 70° all day.

## Quick settings (Home Assistant)
- [ ] Add **Waze Travel Time** (any start/end) so leave-by uses live traffic.
- [x] Two-factor login — done Nov 11.

## Around the house
- [ ] 4× AA (lithium) in the **side-door Kwikset** (Alarm.com critical battery).
- [ ] Return the **Z-Wave stick**.
- [ ] Try the **frame test corners** on the screen — tell Claude: tight / loose / any black showing, which edge.
- [ ] **Room photos** for the 3D house (doorway + opposite corner of each room, kitchen, stairs, garage, outside).
- [ ] Stair lights later: count the steps and measure one tread's width.

## Buy
- [ ] Washer: **Third Reality Zigbee smart plug with energy monitoring** (~$15).
- [ ] Dryer (electric, 240 V): **Aqara vibration sensor** (~$20) on top of the dryer.

## Send Claude when you have it
- [ ] Alarm.com rule screenshots (to move them into Home Assistant).
- [ ] What should happen when someone gets home (after the HA app is on both phones, location "Always").
- [ ] Holiday art from `docs/holiday-art-prompts.md`, one image per message.
