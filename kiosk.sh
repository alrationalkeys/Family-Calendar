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

# Browser profile. NOT under ~/.config: Ubuntu's Chromium is a snap and strict
# confinement can't read hidden dirs in $HOME — it then drops the profile *and*
# the kiosk flags and comes up as a plain window. A visible dir works for both
# snap and deb builds.
PROFILE="$HOME/familyhub-kiosk-profile"
if [ -d "$HOME/.config/familyhub-kiosk" ] && [ ! -d "$PROFILE" ]; then
  mv "$HOME/.config/familyhub-kiosk" "$PROFILE" 2>/dev/null || true
fi
mkdir -p "$PROFILE"

# If Chromium was killed mid-session (power cut), it shows a "restore pages?"
# bar on next boot. Clear that flag so the kiosk comes up clean.
PREFS="$PROFILE/Default/Preferences"
[ -f "$PREFS" ] && sed -i 's/"exited_cleanly":false/"exited_cleanly":true/; s/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS"

# Belt and braces: whatever Chromium thinks of --kiosk, have the window manager
# make its window fullscreen (removes GNOME's top bar + dock). Needs `wmctrl`.
force_fullscreen() {
  command -v wmctrl >/dev/null || return 0
  for i in $(seq 1 30); do
    sleep 1
    local wid
    wid=$(wmctrl -lx 2>/dev/null | grep -i -m1 chrom | awk '{print $1}')
    if [ -n "$wid" ]; then
      wmctrl -i -r "$wid" -b add,fullscreen
      wmctrl -i -r "$wid" -e 0,0,0,-1,-1
      wmctrl -i -a "$wid"
      return 0
    fi
  done
}

# Keep the browser up forever: if it crashes or someone closes it, relaunch.
while true; do
  force_fullscreen &
  # NOTE: no --app= here. Snap Chromium ignores --kiosk/--start-fullscreen for
  # app-mode windows (seen on Ubuntu 24.04); plain kiosk mode with the URL as the
  # argument goes truly full-screen. Notifications are handled in-app (banner +
  # speech), so silence the browser's permission prompt.
  "$BROWSER" --kiosk --start-fullscreen --start-maximized --window-position=0,0 \
    --noerrdialogs --disable-infobars --disable-notifications \
    --check-for-update-interval=31536000 \
    --disable-session-crashed-bubble --disable-features=TranslateUI \
    --touch-events=enabled \
    --overscroll-history-navigation=0 \
    --disable-pinch \
    --autoplay-policy=no-user-gesture-required \
    --use-fake-ui-for-media-stream \
    --user-data-dir="$PROFILE" \
    --no-first-run --password-store=basic \
    "$URL"
  sleep 3
  [ -f "$PREFS" ] && sed -i 's/"exited_cleanly":false/"exited_cleanly":true/; s/"exit_type":"Crashed"/"exit_type":"Normal"/' "$PREFS"
done

# Touch flags above:
#   --touch-events=enabled             treat the panel as a real touchscreen
#   --overscroll-history-navigation=0  a left/right swipe won't trigger back/forward
#   --disable-pinch                    stop the browser zooming the whole page on pinch
#                                      (the calendar has its own pinch-to-zoom handler)
#   --autoplay-policy=...              lets spoken voice replies play without a tap first
#   --use-fake-ui-for-media-stream     auto-allow the microphone (no "Allow?" prompt on a wall
#                                      with no mouse); the mic only feeds localhost FamilyHub
