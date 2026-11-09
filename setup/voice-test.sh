#!/bin/bash
# End-to-end check of the wall's local voice: restart FamilyHub, record 4 s from
# the USB mic, send it to /api/ai/transcribe, speak the result through /api/ai/tts.
#   cd ~/familyhub && bash setup/voice-test.sh
cd "$(dirname "$0")/.."
URL="${FAMILYHUB_URL:-http://localhost:8000}"

echo "== restarting FamilyHub (needs your password) =="
sudo systemctl restart familyhub && sleep 5

echo; echo "== server voice status =="
curl -s "$URL/api/ai/voice/status"; echo

MIC=$(arecord -l 2>/dev/null | grep -i 'usb' | head -1 | sed -E 's/^card ([0-9]+).*device ([0-9]+).*/plughw:\1,\2/')
[ -n "$MIC" ] || { echo "no USB mic in 'arecord -l':"; arecord -l; exit 1; }
echo; echo "== recording 4 s from $MIC — SAY SOMETHING NOW =="
arecord -q -D "$MIC" -f S16_LE -r 16000 -c 1 -d 4 /tmp/fh-test.wav || exit 1

echo; echo "== transcribe =="
curl -s -X POST "$URL/api/ai/transcribe" -F "audio=@/tmp/fh-test.wav;type=audio/wav" | tee /tmp/fh-test.json; echo

echo; echo "== speak it back =="
TXT=$(sed -n 's/.*"text":"\([^"]*\)".*/\1/p' /tmp/fh-test.json)
if [ -n "$TXT" ]; then
  curl -s -X POST "$URL/api/ai/tts" -H 'Content-Type: application/json' -d "{\"text\":\"I heard: $TXT\"}" -o /tmp/fh-test-tts.wav && aplay -q /tmp/fh-test-tts.wav
else
  echo "(no text came back — server log follows)"
  echo; echo "== last server errors =="
  journalctl -u familyhub -n 60 --no-pager | grep -iE 'transcribe|Traceback|Error' -A4 | tail -30
fi
