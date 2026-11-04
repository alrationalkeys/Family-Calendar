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
3. Connect to the network (Ethernet just works). Open a terminal (`Ctrl+Alt+T`):
   ```bash
   lsblk                       # find the internal SSD: usually nvme0n1 or sda, ~476G
   cd ~ && wget https://github.com/home-assistant/operating-system/releases/latest/download/haos_generic-x86-64-$(curl -s https://api.github.com/repos/home-assistant/operating-system/releases/latest | grep -oP '"tag_name": "\K[^"]+').img.xz
   xz -dc haos_generic-x86-64-*.img.xz | sudo dd of=/dev/nvme0n1 bs=4M status=progress conv=fsync
   ```
   (If `lsblk` showed `sda`, use `of=/dev/sda`. **Double-check** — this wipes that disk.
   If the `wget` one-liner trips, open github.com/home-assistant/operating-system/releases
   on your phone and copy the `haos_generic-x86-64-*.img.xz` link by hand.)
4. `sudo poweroff`, pull the stick. Power back on → `Del` → BIOS:
   - **Boot mode: UEFI**, **Secure Boot: Disabled** (HAOS won't boot with it on)
   - **Auto Power On / Restore on AC Loss: Power On**
   - Save & exit. HAOS boots to a text console; it's ready in ~5 min.
5. On your desktop: **http://homeassistant.local:8123** → create your admin account,
   name the home, confirm the location (Socastee).
6. Settings → System → **Network**: set a **static IP** (or reserve it in your router). Write
   it down — it goes into FamilyHub's `.env` and into the satellite.
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

1. **Add-ons** (Settings → Add-ons → Store), install + start each, tick *Start on boot*:
   - **openWakeWord** — the "Hey Jarvis" detector (leave default models; `hey_jarvis`
     is one of them).
   - **Whisper** — speech-to-text. Model: `base-int8` (the i3 handles it; `tiny-int8`
     if replies feel slow). Language: `en`.
   - **Piper** — text-to-speech. Pick a voice you like (`en_US-lessac-medium` is good).
2. Each add-on announces itself: Settings → Devices & Services → three **Wyoming Protocol**
   discoveries → **Configure** each.
3. **Settings → Voice assistants → Add assistant**: name `Jarvis`, Conversation agent
   *Home Assistant*, STT *faster-whisper*, TTS *piper*, Wake word *openWakeWord → hey_jarvis*.
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
   → Configure → in the device page set **Assist pipeline: Jarvis** and turn **wake word
   detection on** (the satellite streams audio, HA's openWakeWord listens).
7. Say **"Hey Jarvis, turn on the kitchen lights."** Piper answers through the puck.

Useful phrases out of the box: *turn on/off <name>*, *set <name> to 50%*, *is the garage
open*, *arm the alarm away*, *what time is it*, *turn on living room tv*. Add your own with
Settings → Automations → *Sentence* triggers.

**Make "Hey Jarvis" answer real questions (the Alexa replacement).** HA's built-in agent
only does device control. Add the **Anthropic** integration (Settings → Devices & Services
→ Add → *Anthropic*, paste the same `ANTHROPIC_API_KEY` FamilyHub uses, model
`claude-opus-4-8`). Then in your `Jarvis` pipeline set **Conversation agent → Claude** and
turn on **"Prefer handling commands locally"** so lights/scenes stay instant and offline,
and only open questions ("how long do I boil an egg", "help with fractions") go to Claude.
Give it this as the prompt so it talks like a kitchen assistant, not a chatbot:

> You are the voice of a family's kitchen wall. Everyone, including kids, talks to you.
> Answer in one to three short spoken sentences, no lists or markdown. Be warm and
> practical. You can't browse the internet; for live news or scores say so.

Tap-to-talk on the wall itself already does this (same key), with today's calendar,
meals, chores and lists as context — *"what's for dinner"*, *"when is Ella's dentist"*.

> **Disarming by voice** is off by default in HA (needs a code) and FamilyHub's own voice
> interpreter refuses it too. Keep it that way — disarm stays behind the PIN pad.

## H. Spotify (two layers, both optional; needs Spotify Premium)

**1. The wall as a Spotify speaker.** On the **Screen C3**, with the USB speaker plugged in:
```bash
cd ~/familyhub && bash setup/install-spotifyd.sh plughw:1,0 "Kitchen Wall"
```
"Kitchen Wall" now shows up in the Spotify app's device picker, same as a Sonos. No
password stored; it's discovered over the LAN.

**2. Control + now-playing on the screen.** In HA: Settings → Devices & Services →
**Add Integration → Spotify**. It walks you through creating a free Spotify *developer
app* (developer.spotify.com → Create app, redirect URI `https://my.home-assistant.io/redirect/oauth`)
and signing in. HA then exposes `media_player.spotify_<you>`, and FamilyHub's Home tab
grows a **Spotify card**: album art, play/pause/next, volume, a "play on" picker (Kitchen
Wall / the Roku TVs / your phone), and your pinned playlists.

Pin playlists from the phone app → Settings → Spotify playlists (paste a share link).
Then: *"Hey Jarvis, play dinner vibes in the kitchen"*, *"pause the music"*, *"next song"*.

## G. (Optional) phone voice anywhere

Install the **Home Assistant companion app** — its Assist button uses the same `Jarvis`
pipeline, works on iPhone and Android, and works from outside the house once Tailscale or
HA's remote access is set up. For the FamilyHub web app itself from outside the house,
see `docs/tailscale.md`.

---

### What "done" looks like
- http://homeassistant.local:8123 loads; you can arm/disarm from HA; Roku TVs are listed.
- FamilyHub's Home tab shows the real house (no "demo" badge) and the status bar shows the alarm.
- "Hey Jarvis, turn off the kitchen lights" works from across the kitchen.
