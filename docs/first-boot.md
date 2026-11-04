# First boot — from boxes on the counter to a working wall

Follow this top to bottom with the hardware in hand. Each part is one sitting.
Box names used throughout:

| Box | What it is | What it runs |
|---|---|---|
| **Screen C3** | C3 mini PC behind the Forzola touchscreen | Ubuntu + FamilyHub kiosk + voice satellite |
| **HA C3** | the second C3, headless in a cupboard | Home Assistant OS (→ `docs/home-assistant-setup.md`) |

You'll need once: a **USB stick (8 GB+)**, a **USB keyboard** (any), and your Windows
desktop to write the stick. The touchscreen itself works as the monitor for setup.

---

## Part 1 — Ubuntu on the Screen C3 (~30 min)

The C3 ships with Windows 10. We replace it entirely.

1. On Windows, download **Ubuntu Desktop 24.04 LTS** (ubuntu.com/download/desktop)
   and **Rufus** (rufus.ie). Rufus → pick the stick → pick the Ubuntu ISO → Start
   (defaults are fine).
2. Plug into the C3: the stick, the keyboard, HDMI → Forzola, Forzola's USB touch cable
   → C3, power. Turn on the Forzola with its remote if it doesn't wake.
3. Power the C3 on and **tap `F7`** (or `Del` for BIOS → Boot menu) repeatedly → boot the
   USB stick → **Try or Install Ubuntu → Install Ubuntu**.
4. In the installer:
   - Keyboard: English (US). Wi-Fi: join your home Wi-Fi (or use Ethernet — better).
   - **Default installation**, tick *Install third-party software*.
   - **Erase disk and install Ubuntu** (this wipes Windows — intended).
   - Your name: `hub` · computer name: `familyhub` · username: **`hub`** · pick a password
     · **Log in automatically** ✔.
5. Reboot when asked, pull the stick. Log in as `hub`.

### BIOS: come back on after a power cut
While you're in there (`Del` at power-on): find **Auto Power On / Restore on AC Power Loss
→ Power On** (usually under *Chipset* or *Power Management*) and set it. Save & exit.
Without this, a storm leaves the wall dark until someone presses the button.

## Part 2 — install FamilyHub + kiosk (~10 min, one command)

Open a terminal (`Ctrl+Alt+T`):

```bash
sudo apt install -y git
git clone https://github.com/alrationalkeys/Family-Calendar ~/familyhub
cd ~/familyhub && bash setup/install-kiosk.sh
```

The script installs Chromium + Python, starts the FamilyHub server as a service, sets
auto-login on an **Xorg** session (needed so the night screen-off can actually cut the
HDMI signal), disables every screensaver/lock/update popup, and puts `kiosk.sh` in
autostart. When it prints **Done**, `sudo reboot`. The C3 should boot straight into
FamilyHub full-screen.

**Touch check:** tap around the calendar. Multi-touch pinch should zoom the week grid.
If touch is offset or rotated: `sudo apt install xinput` then `xinput list` /
`xinput map-to-output <touch-id> HDMI-1` — but the Forzola is a standard USB HID panel and
normally needs nothing.

**Phone check:** on your phone, same Wi-Fi: `http://familyhub.local:8000/phone.html`
(or the IP the script printed). Add to Home Screen.

## Part 3 — settings worth doing now

Edit `~/familyhub/.env` (`nano ~/familyhub/.env`, then `sudo systemctl restart familyhub`):

| Line | Why |
|---|---|
| `ANTHROPIC_API_KEY=` | natural-language quick-add + photo-flyer import + voice questions |
| `FAMILYHUB_PIN=1234` | optional — guests on your Wi-Fi can look but not edit |
| `HA_URL=` / `HA_TOKEN=` | after Part 5 — connects the Home tab to the real house |
| `FAMILYHUB_MAIL_HOST/USER/PASS` | optional "magic email": a spare Gmail + app password; forward school emails to it, approve the events on your phone |

Then from the **phone app → Settings**: theme/colors, side panels, holiday sets, family
members, **Calendars** (iCloud app-password / Outlook ICS link / Google), **Photos** (upload,
or paste an iCloud Shared Album link), the **night screen-off window**. The screen-off uses
`xset dpms force off`, which puts the Forzola to standby; it wakes on the schedule or when
you tap. (Forzola remote also works as a manual off switch.)

## Part 4 — speaker + mic (~5 min)

Plug the USB speaker/mic puck into the C3. Then:

```bash
cd ~/familyhub && bash setup/audio-check.sh
```

It lists playback + capture devices, records 4 s, plays it back. **Both lists must show
the puck.** If `arecord -l` shows nothing, the puck's mic is Bluetooth-only — return it.
Note the `plughw:X,Y` names it prints; you need them for the satellite in Part 5.

Tap the **mic button** on the wall and say "what's the weather" — tap-to-talk works right
now (it uses Chromium's speech engine; needs internet).

## Part 5 — Home Assistant + hands-free voice

That's the other box. Go to **`docs/home-assistant-setup.md`** — it walks through HAOS on
the HA C3, the IQ Panel alarm bridge, Roku TVs, the voice add-ons, and finally running
`setup/install-satellite.sh` back on this Screen C3 so "Hey Jarvis" works.

## Part 6 — mount it

Print and assemble per `hardware/README.md` (print the test coupons first). Route cables
out the case's bottom slot. Hang on the wall cleat.

---

## Day-to-day

| Need | Do |
|---|---|
| Update FamilyHub | `cd ~/familyhub && git pull && .venv/bin/pip install -q -r requirements.txt && sudo systemctl restart familyhub` then tap the screen twice to reload (or `sudo reboot`) |
| Server logs | `journalctl -u familyhub -f` |
| Chromium misbehaving | `pkill chromium` — `kiosk.sh` relaunches it in 3 s. The page also reloads itself nightly at 03:45. |
| Wrong time zone | the installer sets `America/New_York`; change with `sudo timedatectl set-timezone Region/City` |
| Get a terminal on the wall | plug in the keyboard, `Ctrl+Alt+T` (Chromium stays behind it) — or SSH: `sudo apt install openssh-server` once, then `ssh hub@familyhub.local` from your desktop |
| Backups | nightly 03:30 to `~/familyhub/backups/` (keeps 14). Copy them off occasionally. |
| Remote access from outside the house | `docs/tailscale.md` |
