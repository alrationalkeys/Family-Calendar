#!/bin/bash
# Quick check that the USB speaker/mic is seen by Linux as BOTH a playback and a
# capture device, then a 4-second record → playback round trip.
#   bash setup/audio-check.sh
set -u
echo "== Playback devices (aplay -l) =="; aplay -l 2>/dev/null | grep '^card' || echo "  (none)"
echo
echo "== Capture devices (arecord -l) =="; arecord -l 2>/dev/null | grep '^card' || echo "  (none — no microphone found)"
echo
# pick the first USB card for both directions
PLAY=$(aplay -l 2>/dev/null | grep -i 'usb' | head -1 | sed -E 's/^card ([0-9]+).*device ([0-9]+).*/plughw:\1,\2/')
REC=$(arecord -l 2>/dev/null | grep -i 'usb' | head -1 | sed -E 's/^card ([0-9]+).*device ([0-9]+).*/plughw:\1,\2/')
if [ -z "$REC" ] || [ -z "$PLAY" ]; then
  echo "A USB device is missing for one direction. The speaker works but there is no mic,"
  echo "or vice versa — swap the puck for one that lists under BOTH aplay -l and arecord -l."
  exit 1
fi
echo "Using mic $REC and speaker $PLAY"
echo "Say something for 4 seconds..."
T=$(mktemp --suffix=.wav)
arecord -D "$REC" -f S16_LE -r 16000 -c 1 -d 4 "$T" 2>/dev/null
echo "Playing it back..."
aplay -D "$PLAY" "$T" 2>/dev/null
rm -f "$T"
echo
echo "If you heard yourself: good. Put these in the satellite service:"
echo "  MIC=$REC  SND=$PLAY   ->  bash setup/install-satellite.sh $REC $PLAY <home-assistant-ip>"
