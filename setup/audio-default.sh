#!/bin/bash
# Make the USB speaker/mic bar the desktop's default output + input so the wall's
# spoken replies (Chromium) and voice capture use it instead of HDMI/onboard.
# WirePlumber remembers the choice across reboots.
#   bash setup/audio-default.sh [match]      (match defaults to "usb")
MATCH="${1:-usb}"
command -v wpctl >/dev/null || { echo "wpctl not found (pipewire not running?)"; exit 1; }

pick() {  # pick <Sinks|Sources> -> node id of first match
  wpctl status 2>/dev/null | awk -v sec="$1" -v m="$MATCH" '
    $0 ~ sec":" {insec=1; next}
    insec && /^ *[│ ]*$/ {insec=0}
    insec && tolower($0) ~ tolower(m) { if (match($0, /[0-9]+\./)) { print substr($0, RSTART, RLENGTH-1); exit } }'
}

SINK=$(pick Sinks); SRC=$(pick Sources)
if [ -z "$SINK" ] && [ -z "$SRC" ]; then
  echo "No audio device matching '$MATCH'. Current devices:"; wpctl status | sed -n '/Audio/,/Video/p'
  exit 1
fi
[ -n "$SINK" ] && wpctl set-default "$SINK" && echo "default output -> node $SINK"
[ -n "$SRC"  ] && wpctl set-default "$SRC"  && echo "default input  -> node $SRC"
echo
wpctl status | sed -n '/Sinks:/,/Sources:/p;/Sources:/,/Filters:/p' | grep -E "Sinks|Sources|\*"
echo
echo "Test (should come out of the bar):  speaker-test -t wav -c 2 -l 1"
