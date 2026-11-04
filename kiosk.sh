#!/bin/bash
# Launch Chromium full-screen pointed at the local FamilyHub server.
# Installed into the desktop autostart by setup/install-kiosk.sh; also fine to
# run by hand. Works on x86 Ubuntu/Debian (the C3 mini PC) and on a Pi.
#
# The wall runs an Xorg session on purpose (not Wayland): `xset` is what lets
# FamilyHub's night screen-off actually cut the HDMI signal (see
# FAMILYHUB_SCREEN_OFF_CMD in .env).

URL="${FAMILYHUB_URL:-http://localhost:8000}"

# never let the desktop blank/sleep the screen — FamilyHub owns that schedule
xset s off; xset -dpms; xset s noblank

# Touch wall: hide the mouse pointer so nothing floats over the UI.
# Needs `unclutter` (apt). Harmless if it's missing.
command -v unclutter >/dev/null && unclutter -idle 0 -root &

# find whichever Chromium/Chrome is installed
for b in chromium chromium-browser google-chrome google-chrome-stable; do
  if command -v "$b" >/dev/null; then BROWSER="$b"; break; fi
done
if [ -z "$BROWSER" ]; then
  echo "kiosk.sh: no chromium found — run setup/install-kiosk.sh" >&2; exit 1
fi

# wait until the FamilyHub server answers (it starts as a systemd service)
for i in $(seq 1 60); do
  curl -fs "$URL/api/auth/status" >/dev/null 2>&1 && break
  sleep 1
done

# If Chromium was killed mid-session (power cut), it shows a "restore pages?"
# bar on next boot. Clear that flag so the kiosk comes up clean.
PREFS="$HOME/.config/chromium/Default/Preferences"
[ -f "$PREFS" ] && sed -i 's/"exited_cleanly":false/"exited_cleanly":true/; s/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS"

# Keep the browser up forever: if it crashes or someone closes it, relaunch.
while true; do
  "$BROWSER" --kiosk --noerrdialogs --disable-infobars \
    --check-for-update-interval=31536000 \
    --disable-session-crashed-bubble --disable-features=TranslateUI \
    --touch-events=enabled \
    --overscroll-history-navigation=0 \
    --disable-pinch \
    --autoplay-policy=no-user-gesture-required \
    --app="$URL"
  sleep 3
  [ -f "$PREFS" ] && sed -i 's/"exited_cleanly":false/"exited_cleanly":true/; s/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS"
done

# Touch flags above:
#   --touch-events=enabled             treat the panel as a real touchscreen
#   --overscroll-history-navigation=0  a left/right swipe won't trigger back/forward
#   --disable-pinch                    stop the browser zooming the whole page on pinch
#                                      (the calendar has its own pinch-to-zoom handler)
#   --autoplay-policy=...              lets spoken voice replies play without a tap first
