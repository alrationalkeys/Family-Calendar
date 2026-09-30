#!/bin/bash
# Launch Chromium full-screen pointed at the local display. Add to autostart.
# Wayland (Pi OS Trixie): put this in ~/.config/wayfire.ini or labwc autostart.
xset s off; xset -dpms; xset s noblank          # never sleep the screen

# Touch wall: hide the mouse pointer so nothing floats over the UI.
# X11 only; needs `sudo apt install unclutter`. Harmless if it's missing.
command -v unclutter >/dev/null && unclutter -idle 0 -root &

chromium-browser --kiosk --noerrdialogs --disable-infobars \
  --check-for-update-interval=31536000 \
  --touch-events=enabled \
  --overscroll-history-navigation=0 \
  --disable-pinch \
  --app=http://localhost:8000 &

# Touch flags above:
#   --touch-events=enabled          treat the panel as a real touchscreen
#   --overscroll-history-navigation=0  a left/right swipe won't trigger back/forward
#   --disable-pinch                 stop the browser zooming the whole page on pinch
#                                   (the calendar has its own pinch-to-zoom handler)
