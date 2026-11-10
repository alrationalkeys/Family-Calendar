# Home Assistant on the HA C3 — alarm, TVs, and hands-free voice

This is the **other box**: the second C3 mini PC, headless in a cupboard, running Home
Assistant OS. It's deliberately *separate* from the screen so a FamilyHub update can never
take the alarm or the house down. FamilyHub only ever talks to it over the LAN.

You need: the HA C3, a **USB stick (8 GB+)**, a keyboard + any HDMI screen for the install
(borrow the Forzola for 20 minutes), your **IQ Panel dealer code**, and an Ethernet cable
to the router (strongly recommended — this box bridges the alarm).

> Menu wording drifts between HA releases. Where names vary I've said so — follow what's on
> screen.

---

## A. Install Home Assistant OS (~20 min)

HAOS on x86 is installed by booting a Linux live USB and writing the HAOS image onto the
C3's internal SSD.

1. On Windows: download **Ubuntu Desktop 24.04 ISO** and write it to the stick with
   **Rufus** (same stick/steps as `docs/first-boot.md` Part 1 — you can reuse that stick).
2. Plug the stick, keyboard, screen and **Ethernet** into the HA C3. Power on, tap `F7`
   → boot the stick → **Try Ubuntu** (do *not* install).
3. Connect to the network (top-right icon → Wi-Fi, or plug in Ethernet). Open a terminal
   (`Ctrl+Alt+T`) and find the internal SSD:
   ```bash
   lsblk                       # internal SSD = the ~476G disk (sda or nvme0n1); the stick is the small one
   ```
   Get the image. **Not every HAOS release ships an x86 build** (18.5 was Pi-only), so open
   github.com/home-assistant/operating-system/releases on your laptop and find the newest
   release that lists `haos_generic-x86-64-<ver>.img.xz` (as of Nov 2026: 18.4). The live
   Ubuntu has no `curl`, so plain `wget` with the exact name:
   ```bash
   cd ~ && wget https://github.com/home-assistant/operating-system/releases/download/18.4/haos_generic-x86-64-18.4.img.xz
   xz -dc haos_generic-x86-64-*.img.xz | sudo dd of=/dev/sda bs=4M status=progress conv=fsync
   ```
   Use `of=/dev/nvme0n1` if that's what `lsblk` showed. **Double-check** — this wipes that
   disk. (Typing the URL by hand is error-prone: Firefox on the live desktop → the releases
   page → click the file → it lands in `~/Downloads`, then point `xz -dc` at that path.)
   HAOS updates itself to newer releases from Settings → System → Updates afterwards.
4. `sudo poweroff`, pull the stick. Power back on → `Del` → BIOS:
   - **Boot mode: UEFI**, **Secure Boot: Disabled** (HAOS won't boot with it on)
   - **Auto Power On / Restore on AC Loss: Power On**
   - Save & exit. HAOS boots to a text console; it's ready in ~5 min.
5. On your desktop: **http://homeassistant.local:8123** → create your admin account,
   name the home, confirm the location (Socastee).
6. Settings → System → **Network**: set a **static IP** (or reserve it in your router). Write
   it down — it goes into FamilyHub's `.env` and into the satellite.
   > **Which port?** Check with `ha core info` (Terminal & SSH add-on) → `port:`. Recent
   > HAOS images serve the UI on **port 80**, with `:8123` only a redirect that may answer on
   > IPv6 alone. If `curl http://<ip>:8123/api/` is "connection refused" but
   > `curl http://<ip>/api/` returns `401: Unauthorized`, use `HA_URL=http://<ip>` (no port).
   > Changing the IP while HA is running also leaves stale sockets — reboot the box after.
7. Unplug the screen/keyboard. The HA C3 now lives in the cupboard with power + Ethernet.

## B. Enable the 3rd-party connection on the IQ Panel

This exposes a local (LAN-only) control channel that `qolsysgw` talks to.

1. On the panel: **Settings → Advanced Settings →** enter your **dealer code**.
2. **Installation → Devices → Wi-Fi Devices → 3rd Party Connections** (older firmware:
   *Installation → Devices → 3rd Party Connections*).
3. Enable **"Control4"** — that toggle is the generic 3rd-party socket, not Control4-specific.
4. Tap **Reveal Secure Token** and copy the token. Note the panel's **IP** (Settings → Wi-Fi)
   and reserve it in the router too.

> The token can arm/disarm the house. Treat it like a key.

## C. Bridge the panel into HA with qolsysgw

1. HA → **Settings → Add-ons → Add-on Store**:
   - **Mosquitto broker** → install, start. Settings → People → Users → add a user `mqtt`
     with a password. Settings → Devices & Services → the **MQTT** integration appears →
     Configure with that user.
   - **AppDaemon** → install, start.
2. Add the **Samba share** add-on (or the File editor add-on) so you can reach
   `/addon_configs/a0d7b954_appdaemon/apps/`. Drop in **qolsysgw** from
   github.com/XaF/qolsysgw (the `apps/qolsysgw` folder) and write `apps.yaml`:
   ```yaml
   qolsys_panel:
     module: gateway
     class: QolsysGateway
     panel_host: <panel-ip>
     panel_token: <secure-token>
     panel_user_code: <your 4-6 digit user code>   # optional; needed for disarm
     mqtt_namespace: mqtt
   ```
   (The qolsysgw README has the exact current keys if any have moved.)
3. Restart AppDaemon. Within a minute HA shows:
   - **`alarm_control_panel.*`** — arm/disarm + state
   - **`binary_sensor.*`** for each door/window/motion zone
4. Test from HA itself: Settings → Devices & Services → Entities → the alarm panel → arm /
   disarm. If that works, FamilyHub's PIN pad will too.

## D. Roku TVs

Settings → Devices & Services → **Add Integration → Roku**. Every Roku TV on the LAN is
auto-discovered. On each TV: Settings → System → Power → **Fast TV Start: On**, otherwise
power-on over the network doesn't work. FamilyHub's remote drives these.

## E. The token FamilyHub uses

Profile (bottom-left) → **Security → Long-Lived Access Tokens → Create Token** → name it
`familyhub`. Copy it once. On the **Screen C3**, `nano ~/familyhub/.env`:
```
HA_URL=http://<ha-c3-ip>:8123
HA_TOKEN=<the token>
```
`sudo systemctl restart familyhub`. The Home tab now shows your real devices. (The token
never leaves the server — the browser never sees it.)

## F. Hands-free voice — openWakeWord + Whisper + Piper

Three add-ons on the HA C3 do the listening/talking; the kitchen puck is just a dumb
mic + speaker streamed from the Screen C3. Everything stays local.

**Pick the name first.** The wake word is a tiny speech model, so the name has to
exist as a model. Two ways:
- **Instant, built in** (openWakeWord ships these): **"Hey Jarvis"**, **"OK Nabu"**,
  **"Hey Mycroft"**, **"Hey Rhasspy"**, "Alexa" (don't — it'll fight the Echo).
- **Any name she wants** (~30 min, free): openWakeWord's training notebook at
  github.com/dscripka/openWakeWord → *Training custom models* (Google Colab). Type the
  phrase ("Hey Luna", "Hey Marvin", "Computer"…), run it, download the `.tflite`, drop
  it in HA's `/share/openwakeword/` folder (Samba add-on), restart the add-on, and it
  appears in the wake-word list. Two- or three-syllable names with hard consonants work
  best ("Hey Luna" > "Hey Sue"). There's also a community pile of ready-made ones at
  github.com/fwartner/home-assistant-wakewords-collection.
- Set the same name in the phone app → Settings → *Assistant's name* so the wall's
  tap-to-talk and spoken replies use it too.

Below, **`<Name>`** means whatever she picked.

1. **Add-ons** (Settings → Add-ons → Store), install + start each, tick *Start on boot*:
   - **openWakeWord** — the "Hey <Name>" detector.
   - **Whisper** — speech-to-text. Model: `base-int8` (the i3 handles it; `tiny-int8`
     if replies feel slow). Language: `en`.
   - **Piper** — text-to-speech. Pick a voice you like (`en_US-lessac-medium` is good).
2. Each add-on announces itself: Settings → Devices & Services → three **Wyoming Protocol**
   discoveries → **Configure** each.
3. **Settings → Voice assistants → Add assistant**: name it `<Name>`, Conversation agent
   *Home Assistant*, STT *faster-whisper*, TTS *piper*, Wake word *openWakeWord → <your model>*.
   Make it the **preferred** assistant.
4. **Expose devices to Assist**: Settings → Voice assistants → *Expose* tab → expose the
   lights, switches, TVs, scenes, and the alarm (arm only is wise — see note below). Give
   entities plain names ("Kitchen Lights", "Living Room TV") — that's what you'll say.
5. **Back on the Screen C3** (keyboard or SSH), with the puck plugged in:
   ```bash
   cd ~/familyhub
   bash setup/audio-check.sh                                  # gives you the device names
   bash setup/install-satellite.sh plughw:1,0 plughw:1,0 kitchen
   ```
6. HA discovers the satellite: Settings → Devices & Services → **Wyoming Protocol: kitchen**
   → Configure → in the device page set **Assist pipeline: <Name>** and turn **wake word
   detection on** (the satellite streams audio, HA's openWakeWord listens).
7. Say **"Hey <Name>, turn on the kitchen lights."** Piper answers through the puck.

Useful phrases out of the box: *turn on/off <name>*, *set <name> to 50%*, *is the garage
open*, *arm the alarm away*, *what time is it*, *turn on living room tv*. Add your own with
Settings → Automations → *Sentence* triggers.

**Make "Hey <Name>" answer real questions (the Alexa replacement).** HA's built-in agent
only does device control. Add the **Anthropic** integration (Settings → Devices & Services
→ Add → *Anthropic*, paste the same `ANTHROPIC_API_KEY` FamilyHub uses, model
`claude-opus-4-8`). Then in your `<Name>` pipeline set **Conversation agent → Claude** and
turn on **"Prefer handling commands locally"** so lights/scenes stay instant and offline,
and only open questions ("how long do I boil an egg", "help with fractions") go to Claude.
Give it this as the prompt so it talks like a kitchen assistant, not a chatbot:

> You are <Name>, the voice of a family's kitchen wall. Everyone, including kids, talks to you.
> Answer in one to three short spoken sentences, no lists or markdown. Be warm and
> practical. Use web search only for live information like news, scores or store hours.

Turn on **Web search** in that integration's options so "Hey <Name>" can answer live
questions too. Tap-to-talk on the wall already does all of this (same key): today's
calendar, meals, chores and lists as context — *"what's for dinner"*, *"when is Ella's
dentist"* — plus live lookups — *"did the Panthers win"*, *"is Publix still open"*.

> **Disarming by voice** is off by default in HA (needs a code) and FamilyHub's own voice
> interpreter refuses it too. Keep it that way — disarm stays behind the PIN pad.

## H. Spotify (needs Spotify Premium)

**The way that actually works: the wall is an *official* Spotify device.** Spotify
blocks third-party Connect clients (spotifyd, go-librespot) on many accounts — every
track "loads" then skips with `audio key error`. FamilyHub instead runs Spotify's own
Web Playback SDK inside the wall's Chromium, so "Hey Hub, play Zach Bryan" plays out of
the wall speaker with no phone involved, and "FamilyHub" shows in every Spotify app.

1. developer.spotify.com → your app (the one you made for HA) → **Settings** → Redirect
   URIs → add `http://127.0.0.1:8000/api/spotify/callback` → Save. Copy Client ID + Secret.
2. On the wall `.env`: `SPOTIFY_CLIENT_ID=…` and `SPOTIFY_CLIENT_SECRET=…`, then
   `sudo systemctl restart familyhub`.
3. Phone app → Settings → **Spotify → Connect Spotify to the wall**. Log in / approve.
   Spotify then sends you to `http://127.0.0.1:8000/…` which **won't load on the phone**
   (expected — it's the wall's own address). Copy that page's address from the address
   bar, paste it into the box under the button, **Finish connecting**.
4. The wall reloads and registers itself as "FamilyHub" (Spotify's DRM module downloads
   itself into Chromium on first use; give it a minute). Status on that phone page shows
   "online". Voice: *"play dinner vibes"*, *"play Zach Bryan"*, *"play the album Nation of
   Two"*, *"pause"*, *"next song"*, *"what's playing"*, *"play … on the living room TV"*.

The two older approaches below are kept for reference / other households.

### H-old. Third-party Connect clients (two layers, both optional)

**1. The wall as a Spotify speaker.** On the **Screen C3**, with the USB speaker plugged in:
```bash
cd ~/familyhub && bash setup/install-spotifyd.sh pulse "FamilyHub"
```
"FamilyHub" now shows up in the Spotify app's device picker, same as a Sonos. No
password stored; it's discovered over the LAN. `pulse` plays through the desktop's
default output (the speaker bar, per `setup/audio-default.sh`) without fighting Chromium
for the sound card; pass `plughw:X,Y` instead to grab a card directly.

> **If every track "loads" then skips** and `journalctl --user -u spotifyd` shows
> `error audio key 0 1` / `Service unavailable { audio key error }`: Spotify is refusing
> the open-source Connect client for that account (upstream librespot #1649, no fix on our
> side, Premium or not). First try the independent Go client, which the block doesn't
> always catch:
> ```bash
> bash setup/install-go-librespot.sh "FamilyHub"
> ```
> If that skips too, use the **Bluetooth speaker** fallback — no account involved:
> ```bash
> systemctl --user disable --now spotifyd go-librespot
> bash setup/install-bt-speaker.sh "FamilyHub"
> ```
> Phone → Bluetooth → pair "FamilyHub" (no PIN) → anything you play comes out of the bar.
> Layer 2 below still works for now-playing + voice control of whatever device is playing.

**2. Control + now-playing on the screen.** In HA: Settings → Devices & Services →
**Add Integration → Spotify**. It walks you through creating a free Spotify *developer
app* (developer.spotify.com → Create app, redirect URI `https://my.home-assistant.io/redirect/oauth`)
and signing in. HA then exposes `media_player.spotify_<you>`, and FamilyHub's Home tab
grows a **Spotify card**: album art, play/pause/next, volume, a "play on" picker (Kitchen
Wall / the Roku TVs / your phone), and your pinned playlists.

Pin playlists from the phone app → Settings → Spotify playlists (paste a share link).
Then: *"Hey <Name>, play dinner vibes in the kitchen"*, *"pause the music"*, *"next song"*.

## I. Your actual devices (what's in the house today)

| Device | HA integration | Steps |
|---|---|---|
| **Deako switches** (D.R. Horton package) | **Deako** (built in, local) | They're on Wi-Fi already if the Deako app works → Settings → Devices & Services → *Discovered: Deako* → Add. Only *Smart* Deako switches appear; the plain modular ones are just switches. |
| **Z-Wave devices** (plugs on the IQ Panel today, locks/garage later) | **Z-Wave JS** via the **SONOFF Z-Wave 800 Dongle Plus (Dongle-PZG23)** you have | See §I-1 below. `qolsysgw` only carries the alarm + door/motion sensors, not the panel's Z-Wave gear, so each device moves to the stick. |
| **Kitchen LED strips ×2** — **GLEDOPTO Zigbee Pro Max (GL-C-601P)** on the Aqara hub / Alexa | **ZHA** via a Zigbee USB stick | See §I-2 below. Pairs straight to HA as a colour + white-temperature light; the Aqara hub and Alexa drop out of the loop. |
| **Aqara motion sensor** (kitchen) | **ZHA** (same stick) | §I-2. The motion → lights rule becomes an HA automation. |
| **Garage door** (myQ, linked to the IQ Panel) | **ratgdo** (ESPHome, local) | myQ's cloud API was shut to third parties in 2023 and HA dropped the integration. A ratgdo board (~$45, pick the one for your opener's brand/year) wires to the opener and gives open/close + obstruction locally. The 3D house shows the door state and FamilyHub warns when it's left open. |
| **Govee porch lights** | **Govee** (built in, local LAN) | Govee app → device → ⚙ → **LAN Control: on** → HA discovers it. Recreate the Alexa sunset routine as an HA automation (Settings → Automations → trigger *Sun: sunset* → action *light.turn_on*). |
| **Roku TVs** | **Roku** (built in) | Fast TV Start on each TV (section D). |
| **IQ Panel** | `qolsysgw` | Sections B–C. |

Then the Home tab, floor plan rooms (matched by name — rename entities to "Kitchen Upper
Stove", "Kitchen Upper Front", "Kitchen Lower Fridge", "Porch Lights" so voice and rooms
line up), "all lights off", and "Hey <Name>, kitchen lights off" all just work.

### I-1. Z-Wave: the SONOFF Dongle-PZG23 (~10 min)
Z-Wave (908 MHz) and Zigbee (2.4 GHz) are different radios — one stick per protocol. Both
live happily in the same HA box.
1. Plug the stick in **using the short USB extension cable in its box**, and into a **USB 2
   port** if the C3 has one (USB 3 ports radiate noise that cripples both Z-Wave and Zigbee).
   Keep it a foot or two from the box and from the Zigbee stick.
2. HA → Settings → Devices & Services. It is usually **auto-discovered as "Z-Wave"** → *Configure*
   → accept "install the Z-Wave JS add-on" → wait ~2 min. If not discovered: Settings → Add-ons →
   Add-on store → **Z-Wave JS** → Install → Configuration → Device: pick the SONOFF entry → Start;
   then Settings → Devices & Services → Add integration → *Z-Wave* → use the add-on.
3. Moving a device off the IQ Panel: on the panel, Settings → Advanced Settings → Installation →
   Devices → Home Devices → **Remove Device** (exclusion), then press the device's pairing button.
   In HA: Z-Wave JS → **Add device** → press the button again. Use S2 security when offered (locks
   need it). Repeat per device.
4. Give each new device an **Area** so it lands in the right room on the wall and phone.

### I-2. Zigbee: GLEDOPTO strips + Aqara motion (~15 min)
1. Buy **one** Zigbee USB stick: *Home Assistant Connect ZBT-1* or *SONOFF Zigbee 3.0 USB Dongle
   Plus* (either ~$30). Same rules: extension cable, USB 2 port, away from the Z-Wave stick.
2. HA → Settings → Devices & Services → it appears as **Zigbee Home Automation (ZHA)** → *Configure*
   → create a new network. (Zigbee2MQTT is the power-user alternative; ZHA is enough here.)
3. Each GLEDOPTO GL-C-601P: unpair it from the Aqara hub first (Aqara app → device → Delete), or
   **factory reset**: hold the **Reset** button on the controller ~5 s until the strip blinks.
   In ZHA: **Add device** → within a minute it appears as *GLEDOPTO GL-C-601P*. In the device's
   settings pick the **light type** (RGB+CCT / RGBW / CCT) matching your strip.
4. Aqara motion sensor: hold its button ~5 s until the blue light flashes → ZHA *Add device*.
   Aqara sensors sleep aggressively; if it drops off, re-pair it next to the stick.
5. Re-create the kitchen rule: Settings → Automations → **Create** → trigger *Motion detected*
   → condition *Sun below horizon* (or a time window) → action *light.turn_on* the strip, plus a
   second automation *no motion for 5 min → light.turn_off*. Then **delete the strips from Alexa**
   and the Aqara app so nothing fights.
6. Set the Area to **Kitchen** on both strips and the sensor → they appear as pins in the kitchen
   on the 3D house and the strips light the room in the model when they're on.

## J. Make the two feel like one product

**FamilyHub inside the Home Assistant app.** Settings → Dashboards → **Add dashboard →
Webpage** → URL `http://familyhub.local:8000/phone.html`, title *FamilyHub*, icon
`mdi:calendar-heart`, *Show in sidebar*. The HA app on every phone now has FamilyHub one
tap away (same Wi-Fi, or over Tailscale).

**FamilyHub's day as HA sensors** — so automations can react to the family, not just the
house. Add to HA's `configuration.yaml` (File editor add-on), then restart:
```yaml
rest:
  - resource: http://familyhub.local:8000/api/summary
    scan_interval: 60
    sensor:
      - name: "FamilyHub next event"
        value_template: "{{ value_json.next_event or 'none' }}"
        json_attributes: [next_event_at, next_event_in_min, events_today]
      - name: "FamilyHub chores left"
        value_template: "{{ value_json.chores_left }}"
        json_attributes: [chores_by_person, routines_left]
      - name: "FamilyHub dinner"
        value_template: "{{ value_json.dinner or 'not planned' }}"
      - name: "FamilyHub groceries"
        value_template: "{{ value_json.groceries }}"
      - name: "FamilyHub countdown"
        value_template: "{{ value_json.next_countdown or 'none' }}"
        json_attributes: [next_countdown_days]
```
Ideas that take two minutes each in Settings → Automations:
- *next_event_in_min* hits 10 → flash the porch light / announce on the kitchen speaker
- *chores left* for Max > 0 at 7 pm → turn off the bedroom Roku
- 6:45 am on school days → Piper says the dinner + next event on the speaker (or let the
  wall's own briefing do it)
- **Expose** these sensors to Assist and "Hey <Name>, how many chores are left" works
  through HA too.

(If FamilyHub has `FAMILYHUB_PIN` with `FAMILYHUB_LOCK_READS=1`, add
`headers: {X-FH-PIN: "1234"}` under `resource`. On the LAN you won't need it.)

## G. (Optional) phone voice anywhere

Install the **Home Assistant companion app** — its Assist button uses the same `<Name>`
pipeline, works on iPhone and Android, and works from outside the house once Tailscale or
HA's remote access is set up. For the FamilyHub web app itself from outside the house,
see `docs/tailscale.md`.

---

### What "done" looks like
- http://homeassistant.local:8123 loads; you can arm/disarm from HA; Roku TVs are listed.
- FamilyHub's Home tab shows the real house (no "demo" badge) and the status bar shows the alarm.
- "Hey <Name>, turn off the kitchen lights" works from across the kitchen.
