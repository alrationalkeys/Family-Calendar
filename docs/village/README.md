# North Pole Village: handoff for Home Assistant

> **In this repo:** the HA package is `docs/ha/north_pole_village.yaml` (install like the other packages), the
> dashboard card is `docs/village/north_pole_village_card.yaml`, firmware source is `docs/village/firmware/`.
> The PDFs, CAD/STL files and test sounds stay in Alex's handoff zip (not in git).

This folder is everything built for Alex and Rachell's Department 56 North Pole Christmas village: firmware, print files, docs, and a ready-made Home Assistant package. It is written for the Claude Code session that runs Alex's Home Assistant and family calendar on the local mini PCs.

**Goal:** control and monitor the village from Home Assistant (and optionally the family calendar display) without changing the village firmware. The village is finished, tested, and covered with snow foam, so **do not flash firmware unless Alex asks**. Everything Home Assistant needs is already served over HTTP by the boards.

---

## 1. What's in this folder

| Path | What it is |
|---|---|
| `home_assistant/packages/north_pole_village.yaml` | HA package: `rest_command`s, scripts (one per button), REST status sensors, two `input_number` helpers. Drop into `<config>/packages/`. |
| `home_assistant/dashboards/north_pole_village_card.yaml` | A Lovelace card (manual card YAML) with every button and status. |
| `firmware/VillageEffects/` | Board A source (Arduino). Version **A-2026.11.02d**. |
| `firmware/VillageTrain/` | Board B source (Arduino). Version **B-2026.11.01d**. |
| `firmware/secrets.h.example` | Template. The real `secrets.h` (WiFi + OTA password) is deliberately **not** included. Never add it to any repo or zip. |
| `docs/` | Build Book, wiring diagrams, software and printing guide, extras, track plan, Rachell's menu, parts inventory (PDFs). |
| `cad/` | Python CAD scripts (manifold3d + trimesh, helper `vlib.py`) and all STL print files. `sleigh_3d_v6.html` is a Three.js model of the (on-hold) sleigh loop. |
| `sounds/Village_Test_Sounds.zip` | Spoken-number test files for the SD cards. |

---

## 2. The system

Three controllers on the home WiFi (2.4 GHz). No data wires between them; they talk over HTTP and UDP.

| Device | Hostname | Last known IP | Role |
|---|---|---|---|
| **Board A** (ESP32 30-pin) | `village-fx.local` | 192.168.1.200 | Effects brain and the "hub": 2 DFPlayer sound players, buttons, motion sensors, rink motor, street lamps, sleigh (on hold), tells WLED which preset to show, tells Board B when to run. Serves the main phone page. |
| **Board B** (ESP32 30-pin) | `village-train.local` | 192.168.1.121 | Train: LionChief Bluetooth engine control (relay backup on track power), station IR sensors, red/green signal, railroad crossing (2 servos, flashing lamps). |
| **WLED** (GLEDOPTO ESP32, 4 outputs) | `village-lights.local` | 192.168.1.134 (confirmed by Alex, Nov 12) | All village lights and the tree. Stock WLED. |

**First step for HA: make DHCP reservations for all three** in the router so the IPs never move. mDNS (`.local`) often doesn't resolve inside the HA container, so the package uses IPs.

How they talk to each other:
- UDP discovery on port **4210** (each board announces its name; this is how A and B find each other's IP).
- Board A → WLED: `POST http://<wled>/json/state {"ps":N,"tt":T}` to switch presets.
- Board A → Board B: `GET /go?laps=N`, `/stop`, etc. Board A sends `TDUCK:<secs>` over UDP to quiet the train during songs.
- Board B → Board A: `GET /station` when the train arrives (Board A plays the station sound), plus `TLOG:` lines into Board A's log.

---

## 3. Board A HTTP API (village-fx)

| Endpoint | Does |
|---|---|
| `GET /` | Phone control page (HTML). |
| `GET /status` | Plain-text status (format below). |
| `GET /log` | Plain-text live log. `GET /logclear` clears it. |
| `GET /settings` | Settings page (HTML form). `POST /save` saves it. Settings live in ESP32 flash (Preferences). |
| `GET /cmd?do=<command>` | Runs a command, returns `ok`. |
| `GET /train?do=<cmd>` | Hub relay to Board B: `status`, `stop`, `xing`, `relaytest`, `bttest`, `go?laps=N` (URL-encode the value). |

`/cmd?do=` commands:

| Command | What happens |
|---|---|
| `wake` | Village wakes: WLED preset 3, sound 1, rink on, sleigh, train runs its wake laps. |
| `sleep` | Back to sleepy (preset 2) or closed (preset 1) depending on the clock. |
| `tree` | Tree show: preset 4 + sound 4 for 60 s, then back to the previous mode. |
| `rachell` | Rachell's show: preset 5 + sound 5 for 90 s, rink on, sleigh, train 1 lap, carolers sing. |
| `carol` | Carolers sing a random song on their own speaker. |
| `train` | Whistle (sound 2), waits for it to finish (setting "Train waits for the whistle", default 4 s), then train runs the button laps. |
| `play:N` | Play main-speaker file N (e.g. `play:7`). |
| `snd2_N` | Play carolers file N. |
| `light:N` | Switch WLED to preset N. |
| `rinkon` / `rinkoff` | Ice rink motor. |
| `lampson` / `lampsoff` / `lampsauto` | Street lamps forced on, forced off, or back to automatic. |
| `manual` | **Toggles** manual mode (no direct on/off; check `/status` first line). In manual mode nothing happens on its own. |
| `override` | Toggles "ignore the clock". |
| `station` | Station sound (as if the train arrived). |
| `sleigh` | Flies the sleigh (hardware on hold until 2027; harmless). |

`/status` format (one item per line, last line is the version):
```
AUTOMATIC: runs on its own            (or: MANUAL MODE: nothing happens unless you tap it)
Mode: awake                           (closed | sleepy | awake | tree show | Rachell show), may end with " (ignoring clock)"
Time: Wed 06:12 PM  |  open 16:00 to 23:00
Motion: 1 2                           (which sensors see motion right now; empty if none)
Sleigh: home (magnet seen)
Rink speed: 170/255   Street lamps: on
Main sound: ready   Carolers sound: ready
Lights: 192.168.1.133   Train: 192.168.1.121
Code version: A-2026.11.02d
```

## 4. Board B HTTP API (village-train)

| Endpoint | Does |
|---|---|
| `GET /` | Train phone page. `GET /fx` redirects to Board A. |
| `GET /status` | Plain text (format below). `GET /log`, `/logclear`. |
| `GET /go?laps=N` | Run N laps, stop at the station. |
| `GET /stop` | Stop now. |
| `GET /xing` | Test the crossing (gates down, lamps flash). |
| `GET /relaytest`, `GET /bttest` | Hardware tests. |
| `GET /settings`, `GET /save?...` | Train settings. |

`/status`:
```
State: stopped at station      (running | arriving at station | waiting at platform | leaving station | connecting to the engine (Bluetooth))
Laps left: 0   laps done since power-up: 12
Sensor 1 (in): clear   Sensor 2 (out): clear
Control: Bluetooth - connected to LC-0-1-6491-E335   speed 0/31   track power ON
Crossing: clear   sensor: clear
Code version: B-2026.11.01d
```

## 5. WLED (village-lights)

Use Home Assistant's **native WLED integration** (it usually auto-discovers). Outputs:

| Output | GPIO | LEDs (index range) | What |
|---|---|---|---|
| 1 | 2 | 0-299 | Tree |
| 2 | 4 | 300-499 | House row |
| 3 | 16 or 12 (check WLED; 16 is preferred because 12 is an ESP32 boot-strap pin) | 500-699 | Third strip |

All SK6812 RGBW, color order GRB, "make a segment for each output" on. Presets Board A relies on (keep these IDs):

| Preset | Name | Used when |
|---|---|---|
| 1 | Off | Village closed |
| 2 | Sleepy | Open, nobody around |
| 3 | Evening | Awake |
| 4 | Tree show | Tree button / `tree` |
| 5 | Rachell's show | Rachell's button / `rachell` |

Presets 6+ are free for extra looks. Each preset stores every segment's effect, so one preset can mix effects across segments.

## 6. Sound files

Each DFPlayer reads numbered files from an **`mp3` folder** on its own microSD (FAT32): `mp3/0001.mp3`, etc. (Files outside the `mp3` folder are ignored; this was the cause of a "won't play" bug.)

Main speaker (Board A, DFPlayer 1): 1 wake/sleigh, 2 train whistle, 3 random "ho ho ho", 4 tree show music, 5 Rachell's song, 6 train at station, 7-10 random extras while awake (reindeer, Santa landing, sleigh bells, one more), every 10-20 min, never cutting off another sound.

Carolers speaker (Board A, DFPlayer 2): 1-4 carols, picked at random (settings `cFirst`=1, `cLast`=4).

## 7. Board A pins (for reference)

| GPIO | Connects to |
|---|---|
| 16 / 17 | DFPlayer 1 TX / RX (via 1k), main speaker |
| 13 / 14 | DFPlayer 2 TX / RX (via 1k), carolers |
| 34, 35, 4 | Motion sensors 1 (front), 2 (side), 3 (carolers) |
| 5, 33, 32, 25 | Buttons: tree, train, Rachell, carolers (active LOW) |
| 23, 22, 2 | MOSFETs: rink, sleigh, street lamps |
| 21 | Hall sensor (sleigh home) |
| 18, 19 | Mist modules (disabled in code: `MIST_ENABLED = false`) |

Board B: relay 26, station IR in 34 / out 35, signal green 25 / red 27, crossing IR 32, gate servos 18 / 19, crossbuck lamps 21 / 22.

## 8. Firmware build notes (only if Alex asks for a change)

- Arduino IDE 2, **esp32 core 3.0.7**, partition scheme **Minimal SPIFFS (1.9MB APP with OTA)**.
- Libraries: DFRobotDFPlayerMini 1.0.6 (Board A), ESP32Servo (Board B).
- Upload over WiFi (OTA). If Board B's WiFi upload fails with an espota port error, upload over USB.
- **Board B is at ~91% of program space.** Avoid adding code there.
- Board A is at ~58%.
- Each folder needs its own `secrets.h` (see the example). Never put the real one in a zip, repo, or chat.
- Version strings are `FIRMWARE_VERSION` near the top of each `.ino`. Bump them on any change.

## 9. Current state and what's on hold

- Working and tested (Nov 11, 2026): sounds (main + carolers), all light presets, all four buttons, train laps / stop / station / crossing, rink, street lamps, motion wake, automatic mode.
- **Sleigh loop**: on hold until 2027. Firmware still "flies" it and plays sound 1 every few minutes while awake; Alex likes the random "ho ho ho", so leave it.
- **Mist**: disabled in code. **Window servos**: removed from code. **Smokestacks**: postponed.

## 10. Suggested Home Assistant work

1. Reserve the three IPs in the router; update the IPs in the package if they differ.
2. Enable packages (`homeassistant: packages: !include_dir_named packages`), drop in `north_pole_village.yaml`, restart, check the new `script.village_*` and `sensor.village_*` entities.
3. Add the WLED integration; fix the two WLED entity ids in the dashboard card.
4. Add the dashboard card.
5. Optional: a "Village" tile on the family calendar display that calls the same scripts, and automations (examples at the bottom of the package). Board A already runs its own schedule (open 16:00 to 23:00) and motion wake in automatic mode, so HA automations should complement it, not fight it.
