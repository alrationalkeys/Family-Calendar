# Blind tilt firmware (ESP32-C6, Zigbee)

Firmware for the DIY blind tilt motor described in `../README.md`. One sketch: `BlindTilt/BlindTilt.ino`.

**Status: written Nov 18, 2026. It has NOT run on real hardware yet.** It was syntax-checked against the real
arduino-esp32 3.3.13 headers for the ESP32-C6 with the Zigbee library, but it was not built into a program and nothing
has been tested on a board, a motor or a blind. Expect to adjust the numbers at the top of the sketch.

It contains no Wi-Fi name, no passwords and no keys. It only joins the Zigbee network you put into pairing mode.

## What it does

- Shows up in Home Assistant (ZHA) as a **cover with tilt**, plus a battery level.
- Turns the wand to any tilt from 0 to 100 %, and answers Open, Close and Stop.
- Finds its own zero by turning gently toward one closed stop until the motor stops turning ("homing").
- Re-homes by itself when a move stops earlier than it should, which is what happens after someone twists the wand
  by hand.
- Every move has a time limit, a soft start, a slow finish, and the motor driver is put to sleep afterwards.
- Refuses to move when the battery is too low.

## Wiring

Pin numbers are the GPIO numbers printed on the ESP32-C6 SuperMini. They can all be changed at the top of the sketch.

| From | To | Notes |
|---|---|---|
| ESP32 `GPIO18` | DRV8833 `IN1` | Motor PWM, one direction |
| ESP32 `GPIO19` | DRV8833 `IN2` | Motor PWM, other direction |
| ESP32 `GPIO20` | DRV8833 `SLP` (also labelled `nSLEEP` or `EEP`) | HIGH = driver on. **Add a 100 k resistor from `SLP` to GND** so the driver stays asleep while the ESP32 sleeps or restarts. If your DRV8833 board has a solder jumper or resistor that ties `SLP` to power, cut or remove it, otherwise the driver never sleeps. |
| DRV8833 `OUT1`, `OUT2` | Motor `M1`, `M2` | The two motor terminals. If homing turns the wrong way, set `MOTOR_REVERSED` to `true` (or swap these two wires). |
| DRV8833 `VM` (or `VCC`) | Battery + (the OUT+ pad of the charger/protection board) | Motor power. |
| DRV8833 `GND` | GND | All grounds joined: battery, ESP32, driver, encoder. |
| 470 uF capacitor (10 V or more) | Across DRV8833 `VM` and `GND`, close to the driver | Stops the motor start from dipping the battery and restarting the ESP32. Mind the stripe = minus. |
| ESP32 `GPIO3` | Encoder `VCC` | The encoder is powered from this pin so it is off between moves. If you would rather wire encoder `VCC` to `3V3`, set `PIN_ENC_POWER` to `-1` (costs a few mA all the time, not good on battery). |
| ESP32 `GPIO1` | Encoder `A` (often labelled `C1`) | |
| ESP32 `GPIO2` | Encoder `B` (often labelled `C2`) | If you get the 5-blink fault, set `ENCODER_REVERSED` to `true` (or swap A and B). |
| Encoder `GND` | GND | |
| Battery + | 220 k resistor, then ESP32 `GPIO0` | Top half of the battery divider. |
| ESP32 `GPIO0` | 220 k resistor, then GND | Bottom half of the divider. Two equal resistors halve the voltage, so 4.2 V becomes 2.1 V at the pin. |
| 100 nF capacitor | From `GPIO0` to GND | Steadies the reading (the resistors are large to save power). |
| Battery + (charger OUT+) | ESP32 `5V` pin | Powers the board through its own 3.3 V regulator. See "To confirm" below. |
| Battery - (charger OUT-) | ESP32 `GND` | |
| Solar panel | Charger board `IN+` / `IN-` | As the charger board says. |

Already on the board, no wiring: the BOOT button (`GPIO9`) and the LED (`GPIO15`).

Do not use `GPIO8`, `GPIO9`, `GPIO15` (LED, button, start-up pins) or `GPIO12`, `GPIO13` (USB) for anything else.

The six wires on an N20 encoder motor are usually: motor, motor, encoder GND, encoder VCC, A, B. The order and
colours differ between sellers. Go by the labels on the little board on the back of your motor, not by colour.

## Arduino IDE settings

1. Install the board package: Boards Manager, search "esp32" by Espressif Systems, version 3.3 or newer
   (the sketch was checked against 3.3.13).
2. Open `BlindTilt/BlindTilt.ino`.
3. In the **Tools** menu set:

| Tools menu item | Set to |
|---|---|
| Board | ESP32C6 Dev Module |
| USB CDC On Boot | Enabled (otherwise you see nothing in the Serial Monitor) |
| Flash Size | 4MB (32Mb) |
| Partition Scheme | Zigbee 4MB with spiffs |
| Zigbee Mode | Zigbee ED (end device) |
| Erase All Flash Before Sketch Upload | Enabled for the very first upload, then Disabled (Enabled also wipes the Zigbee pairing every time) |
| Port | the port that appears when you plug the board in |

No extra libraries are needed. The Zigbee library comes with the board package.

If the upload will not start: hold BOOT, tap RESET, release BOOT, then upload again.

If the sketch stops with "set Tools > Zigbee mode", the Zigbee Mode setting above is missing.

## First bench test (USB power, no blind)

The sketch ships ready for this: `STAY_AWAKE` is `1` and `BATTERY_FITTED` is `0`. Leave them like that.

1. Wire the driver, motor and encoder. Leave the battery and solar parts off. For this test, power the DRV8833 `VM`
   from the ESP32 `5V` pin (USB power). Keep the 470 uF capacitor.
2. Do not put the motor on the blind yet. Stick a small tape flag on the output shaft so you can see it turn.
3. Upload, then open the Serial Monitor at **115200 baud**, line ending "Newline". Type `?` and Enter for the list of
   commands.
4. Type `t1`. The shaft should make about one turn and the monitor should say `reached target`.
   - `STALLED` right away with 0 counts: the encoder is not counting (check `GPIO1`, `GPIO2`, `GPIO3` and GND) or
     the motor is not turning.
   - `ENCODER COUNTS BACKWARDS`: set `ENCODER_REVERSED` to `true` and upload again.
5. **Stall test.** Type `t3` and, while it turns, pinch the shaft firmly with your fingers or soft pliers. It must
   stop within a fraction of a second and print `STALLED`. Do not go further until this works. This is the only thing
   that protects the blind.
6. Type `h` (home). It turns slowly toward "closed". With nothing to stop it, it gives up after about five and a
   half turns and blinks 3 times. That is correct with no blind attached. Now type `h` again and pinch the shaft
   after a turn or so: it should stop, print `Homed`, and the 3 blinks stop.
7. Type `50`, then `100`, then `c`. On `c` it runs fast most of the way, then slowly, looking for the stop. Pinch the
   shaft again to be the stop.
8. Any key plus Enter stops a move. So does a tap on the BOOT button.

Tip: `z` tells it "this spot is home" without moving, which is handy on the bench when there is no stop.

After the first join it also homes by itself once (see pairing below). On the bench, pinch the shaft to end it or let
it give up.

## Pairing with Home Assistant (ZHA)

1. In Home Assistant: Settings, Devices & services, Zigbee Home Automation, **Add device**.
2. Power the board. A board that has never been paired starts searching by itself. The LED blinks fast while it
   searches and changes to one tiny flash every 5 seconds when it has joined.
3. It appears as **FamilyHub BlindTilt**. Give it a name and a room. Wait until Home Assistant has finished
   setting it up (about a minute) before unplugging it.
4. You get a cover with a tilt slider and a battery sensor. On USB power with `BATTERY_FITTED` at `0` the battery
   just says 100 %.
5. "Identify" on the device page blinks the LED, which helps when six of these are on the wall.

To pair it again or move it to another network: hold BOOT for 5 seconds until the LED flickers, then let go. It
forgets the network, restarts and searches again. Also remove the old device in Home Assistant.

### What the tilt numbers mean

In Home Assistant, with the settings as shipped (`TILT_SCALE_TURNS = 5.0`):

| Tilt in Home Assistant | Slats |
|---|---|
| 0 % | Closed, at the home stop |
| 50 % | Level (open) |
| 100 % | Closed the other way |

Things to know:

- For a tilt-only blind, Home Assistant's **open tilt** button asks for 100 % and its **close tilt** button asks
  for 0 %. So with the table above, "close" closes the blind at the home stop (good), but "open" closes it the
  other way, not level. To get level slats, set the tilt to 50 %. Use "set tilt position 50" in FamilyHub routines.
- If you would rather have the open button mean "level", set `TILT_SCALE_TURNS` to `2.5`. Then 0 % is closed and
  100 % is level, both buttons do what they say, and the other closed direction is simply not used.
- Every time it goes to 0 % it finishes by feeling for the stop, which also corrects its position. If the slats ever
  look wrong, send it to 0 %.
- Which way is "home" is up to you: `MOTOR_REVERSED` picks which closed direction it homes to.

## Calibrate counts per turn

The firmware needs to know how many encoder counts make one full turn of the wand. The starting guess is
7 x 4 x 298 x 1 = 8344. Encoders, gearboxes and your printed gears will all make the real number different.

1. Bench mode, motor in the pod, wand in the collar but **unhooked from the blind** so it can turn freely (or do it
   with the pod on the bench and a tape flag on the collar).
2. Put a tape flag on the wand and a pencil mark next to it.
3. Type `t10`. It turns what it believes is 10 turns. Count the turns you actually see, to the nearest tenth.
4. New number = old number x 10 / turns you counted. Example: you count 9.6 turns, so 8344 x 10 / 9.6 = 8692.
5. Put the correction into the constants at the top of the sketch:
   - If you know your printed gear tooth counts, set `DRIVE_RATIO` to wand-gear teeth divided by motor-pinion teeth
     first, and run the test again.
   - Then trim `GEARBOX_RATIO` (or `ENCODER_PULSES_PER_MOTOR_TURN` if it is far out, for example 3 or 12 instead
     of 7) until `t10` gives exactly 10 turns.
6. Hook the wand to the blind. Home it (`h`), then type `100`. It should end fully closed the other way, at slow
   speed, without the 4-blink fault. If it stalls well before the end, lower `WAND_TURNS_FULL_TRAVEL` a little (for
   example 4.8). If it stops short of fully closed, raise it.
7. While you are there, watch the homing speed. If it will not start turning the loaded wand, raise `PWM_HOMING`. If
   it thumps into the stop, lower it.

## BOOT button

| Press | What happens |
|---|---|
| Tap | Stops a move. Clears a fault blink. |
| Hold about 2 seconds (LED goes solid), release | Re-home: finds the closed stop again. Use it if the position looks wrong. |
| Hold 5 seconds (LED flickers), release | Factory reset: forgets the Zigbee network and searches for a new one. |

Do not hold BOOT while plugging in or pressing RESET. That puts the chip into upload mode and the sketch will not run
until the next reset.

## LED blinks

| LED | Meaning |
|---|---|
| Fast blink (5 a second) | Not on the Zigbee network: searching or waiting to be paired |
| One tiny flash every 5 seconds | Joined and idle (stay-awake mode only; in battery mode the LED is off when idle) |
| Solid on | Moving. Also: BOOT held long enough to re-home |
| Slow blink (once a second) | Homing: feeling for the closed stop |
| Steady 2 blinks a second | Identify was pressed in Home Assistant |
| Very fast flicker | BOOT held 5 seconds: let go to factory reset |
| 2 blinks, pause | Battery too low, move refused |
| 3 blinks, pause | Homing failed: no stop found (collar slipping, wrong counts per turn, or too slow for the time limit) |
| 4 blinks, pause | Blocked: stalled in the middle twice in a row, or a move ran out of time |
| 5 blinks, pause | Motor not turning, or encoder not counting or counting backwards |

A fault blink clears on the next move that works, or with a tap on BOOT. In battery mode it only shows for a few
seconds before the board goes back to sleep.

## Battery mode and its trade-off

Set `STAY_AWAKE` to `0` and `BATTERY_FITTED` to `1` only after everything works on USB.

Stay-awake mode keeps the radio listening all the time. Commands arrive instantly, but the board draws tens of
milliamps and one 18650 would last a day or two. That mode is for USB power only.

The Zigbee library that comes with the Arduino board package supports one battery method: **deep sleep with a
timer**. (The gentler "light sleep between polls" used by shop-bought Zigbee blinds is not available in it: the
library has no code for it and power management is switched off in the board package. That was checked in the
3.3.13 source.) So battery mode works like this:

1. Sleep for `SLEEP_SECONDS` (20). Almost no power. The radio is off and it hears nothing.
2. Wake up, reconnect (a second or two), listen for `LISTEN_WINDOW_MS` (3 seconds).
3. If a command arrives, do it, report, stay awake 10 more seconds, then sleep again.

What that means for you:

- **A command can take up to about 25 seconds to happen, and it can be missed.** Zigbee only holds a message for a
  sleeping device for roughly 7 seconds. If the board does not wake inside that time, the message is dropped and Home
  Assistant shows an error or simply nothing happens. With the shipped numbers, a single command has roughly an even
  chance of getting through. Treat that as a guess until it is measured.
- You can trade speed for battery: a shorter `SLEEP_SECONDS` catches more commands and uses more power. Below about
  5 seconds of sleep it should catch nearly all of them, but then it is awake almost half the time.
- For routines (Good night, Leaving), have Home Assistant repeat the command until the reported tilt matches, for
  example every 5 seconds for up to a minute.
- The serial console does not work in battery mode, and USB disconnects each time it sleeps.
- The BOOT button only works while the board is awake. In battery mode, press RESET (or unplug and replug the
  battery) first: after that it stays awake for 3 minutes and the button works as normal. Do not hold BOOT while it
  is asleep and wait for it to wake, that may start it in upload mode instead.
- After a power cut it has forgotten the position and homes once when it rejoins.
- Twisting the wand by hand cannot be felt (the collar slips, the motor does not turn). The firmware only notices on
  the next move, when it reaches a stop too early, and then re-homes. If the hand twist went the other way it does
  not notice at all until the next close, which always re-zeroes.

Battery life has not been measured. A rough guess for the shipped numbers is an average of several milliamps, so
one to three weeks from a full 3000 mAh cell with no sun. Step 3 of the plan in `../README.md` (measure how long it
lasts) decides whether this is good enough. If it is not, the real fix is light sleep, which means building the
firmware with Espressif's ESP-IDF tools instead of the Arduino IDE. That is a separate job.

The battery reading: `BATT_FULL_MV` (4150) shows as 100 %, `BATT_EMPTY_MV` (3300) as 0 %, and below `BATT_CUTOFF_MV`
(3400) the motor will not run. To trim the reading, measure the battery with a multimeter, compare with the
`battery pin` value from the `p` command, and set `BATT_CALIBRATION` to multimeter divided by reported.

## Troubleshooting

- **Never joins (fast blink forever).** Is ZHA in Add device mode? Is the Zigbee Mode setting "Zigbee ED"? Is the
  partition scheme "Zigbee 4MB with spiffs"? Try once with "Erase All Flash Before Sketch Upload" enabled. Move it
  closer to the Zigbee stick or a mains-powered Zigbee device.
- **Nothing in the Serial Monitor.** "USB CDC On Boot" must be Enabled. Baud 115200.
- **Board restarts when the motor starts.** Fit the 470 uF capacitor at the driver. Use thicker, shorter battery
  wires. Lower `PWM_RUN`.
- **5 blinks.** No encoder counts or counting backwards. Check encoder power (`GPIO3`), A and B, and GND. Try
  `ENCODER_REVERSED = true`. If the motor hums but does not turn while homing, raise `PWM_HOMING`.
- **3 blinks on the blind.** It turned more than the full travel without feeling a stop. Either the collar is slipping
  on the wand before the motor stalls (tighten the collar, or lower `PWM_HOMING` so the motor gives up first), or
  the counts per turn are too low, or it is so slow that `HOMING_TIME_LIMIT_MS` ran out.
- **4 blinks.** It stalled in the middle of the travel twice. Something is jamming the wand or slats, or
  `WAND_TURNS_FULL_TRAVEL` is larger than the real travel.
- **It hits the stop hard.** Lower `PWM_HOMING` and `PWM_APPROACH`. Check `WAND_TURNS_FULL_TRAVEL`.
- **It stops before the stop.** The motor is too weak at homing speed: raise `PWM_HOMING` a little at a time.
- **Home Assistant shows the wrong tilt.** Send it to 0 %, or hold BOOT 2 seconds to re-home.
- **A command does nothing and the tilt in Home Assistant already shows that number.** The Zigbee library drops a
  "go to" command when it matches the tilt it already has. Send a different number first, or re-home with the button.
- **It homes toward the wrong closed side.** Set `MOTOR_REVERSED = true`. You may then need to flip
  `ENCODER_REVERSED` as well.
- **Battery always 0 % or the 2-blink fault on USB.** `BATTERY_FITTED` must be `0` when no battery is connected.

## To confirm on the real hardware

These are assumptions the firmware makes. Each one needs a look at the real parts.

1. **SuperMini pins.** That your ESP32-C6 SuperMini brings out GPIO 0, 1, 2, 3, 18, 19 and 20, has the plain LED on
   GPIO15 (lit when HIGH) and the BOOT button on GPIO9. Clones differ. Change the pin numbers at the top if not.
2. **Encoder.** 7 pulses per motor turn, happy on 3.3 V, and drawing little enough to be powered from a GPIO pin
   (should be a few mA).
3. **Gear ratios.** The real gearbox ratio, and the tooth counts of the printed pinion and wand gear (`DRIVE_RATIO`
   is 1.0 until you set it).
4. **The slip collar must hold more than the motor can push at homing speed.** Homing only works if the motor stalls
   against the stop. If the collar slips first, the encoder keeps counting and you get 3 blinks.
5. **Motor power.** The firmware assumes the DRV8833 runs straight from the battery (3.4 to 4.2 V) with no boost
   converter, so the 6 V motor runs slower than its rating. The time limits allow 8 seconds per wand turn.
6. **DRV8833 board.** That it has a `SLP`/`EEP` pin you can reach, and that any pull-up on it can be removed.
7. **Powering the ESP32 from the cell.** Feeding 3.4 to 4.2 V into the `5V` pin relies on the board's regulator
   passing enough voltage through. If the board resets or the radio drops out at lower battery levels, raise
   `BATT_CUTOFF_MV` or power the board another way.
8. **Charger board.** That its output is protected (over-discharge cut-off). The firmware's cutoff only stops the
   motor. It does not disconnect the battery.
9. **Travel.** 5 full wand turns closed to closed, and that the blind's own tilter has firm stops at both ends.
