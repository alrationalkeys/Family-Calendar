# Test FamilyHub on a Windows PC / Surface Pro

Run the whole thing on hardware you already own — before buying the screen. The
Surface's touchscreen makes it a realistic trial of the real wall experience.

## One-time setup

1. **Install Python 3.12** from python.org. On the first screen, tick
   **"Add python.exe to PATH"**, then Install.
2. **Get the code.** Either `git clone` the repo, or download the ZIP from GitHub
   and extract it. Open **PowerShell** in that folder
   (Shift-right-click the folder → "Open PowerShell window here").
3. **Create the environment and install:**
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
   (If PowerShell blocks the activate script, run once:
   `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then retry.)

## Load sample data (recommended for a demo)
So the wall isn't empty when you first open it — adds a sample family, a week of
events, chores with stars, lists and meals:
```powershell
python seed_demo.py
```
(To reset to a clean slate later, delete `familyhub.db` and restart.)

## Easiest way to run it
**Double-click `start-familyhub.bat`** (first run sets everything up automatically),
then open Edge to `http://localhost:8000`. Or for instant full-screen,
double-click **`start-familyhub-kiosk.bat`**.

## Or run it by hand

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Leave that window open (it's the server). Then:

- **Wall display:** open Edge → `http://localhost:8000`
- **Phone app:** `http://localhost:8000/phone.html`
- **From your actual phone** (same WiFi): find the Surface's IP with `ipconfig`
  (the "IPv4 Address", e.g. 192.168.1.42), then on your phone go to
  `http://192.168.1.42:8000`. Add events/lists/photos from the phone and watch
  them appear on the Surface.

Stop the server with **Ctrl-C** in the PowerShell window.

## Full-screen "wall" mode
```powershell
start msedge --kiosk "http://localhost:8000" --edge-kiosk-type=fullscreen --touch-events=enabled
```
Press **Ctrl-W** or Alt-F4 to exit kiosk. (On the real Pi this is `kiosk.sh` with
Chromium instead — same idea.)

## Optional — light up the live features
All optional; the app runs fine without them:
- **Weather** already works (no key) — defaults to Socastee, SC.
- **AI quick-add:** set your key in the server window before starting:
  `$env:ANTHROPIC_API_KEY="sk-ant-..."` then run uvicorn.
- **Google Calendar:** drop `credentials.json` in the project root and run the
  one-time auth (see the main README).
- **iCloud:** add a CalDAV source via the Sources settings (app-specific password).

## What won't match the Pi
- **Night screen-off** uses a Raspberry Pi command, so on Windows you'll see the
  black overlay but not a true backlight cut — expected.
- **Smart home / alarm** needs the separate Home Assistant Pi (Phase 2).
- **Service worker / offline** works on `localhost`; from your phone over plain
  `http://<ip>` it won't register until we add HTTPS (that's the Caddy step).

Everything else is exactly what you'll get on the wall.
