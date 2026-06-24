#!/bin/bash
# Launch Chromium full-screen pointed at the local display. Add to autostart.
# Wayland (Pi OS Trixie): put this in ~/.config/wayfire.ini or labwc autostart.
xset s off; xset -dpms; xset s noblank          # never sleep the screen
chromium-browser --kiosk --noerrdialogs --disable-infobars \
  --check-for-update-interval=31536000 \
  --app=http://localhost:8000 &
