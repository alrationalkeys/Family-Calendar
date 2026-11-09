#!/bin/bash
# Local, offline voice for the wall: Whisper (speech-to-text) + Piper (text-to-speech)
# running on the Screen C3 itself. Needed because Ubuntu's snap Chromium has no
# speech engine behind the Web Speech API (the mic button says "Didn't catch that"
# instantly, and spoken replies are silent).
#
#   cd ~/familyhub && bash setup/install-voice.sh [whisper-model] [piper-voice]
#
# Defaults: base.en (good accuracy, ~1-2 s per phrase on an i3) and en_US-lessac-medium.
# Other voices: en_US-amy-medium, en_US-ryan-medium, en_GB-alba-medium ...
# (see https://rhasspy.github.io/piper-samples/). Re-run with a new name to switch.
set -e
cd "$(dirname "$0")/.."
STT="${1:-base.en}"
VOICE="${2:-en_US-lessac-medium}"

say(){ printf '\n\033[1;36m%s\033[0m\n' "$*"; }

[ -x .venv/bin/pip ] || { echo "no .venv — run setup/install-kiosk.sh first"; exit 1; }

say "1/4  python packages (faster-whisper, piper-tts)"
.venv/bin/pip install -q --upgrade faster-whisper piper-tts

say "2/4  Piper voice: $VOICE  (~60 MB)"
mkdir -p models/piper
.venv/bin/python -m piper.download_voices "$VOICE" --data-dir models/piper
ls -la models/piper | grep "$VOICE" || { echo "voice download failed"; exit 1; }

say "3/4  Whisper model: $STT  (downloads once, ~150 MB for base.en)"
.venv/bin/python - <<EOF
from faster_whisper import WhisperModel
WhisperModel("$STT", device="cpu", compute_type="int8")
print("whisper ok")
EOF

say "4/4  point FamilyHub at them + restart"
touch .env
grep -q '^FAMILYHUB_STT_MODEL=' .env && sed -i "s|^FAMILYHUB_STT_MODEL=.*|FAMILYHUB_STT_MODEL=$STT|" .env || echo "FAMILYHUB_STT_MODEL=$STT" >> .env
VPATH="$PWD/models/piper/$VOICE.onnx"
grep -q '^FAMILYHUB_PIPER_VOICE=' .env && sed -i "s|^FAMILYHUB_PIPER_VOICE=.*|FAMILYHUB_PIPER_VOICE=$VPATH|" .env || echo "FAMILYHUB_PIPER_VOICE=$VPATH" >> .env
if systemctl is-active --quiet familyhub; then sudo systemctl restart familyhub; sleep 4; fi

echo
curl -fs http://localhost:8000/api/ai/voice/status 2>/dev/null && echo || echo "(server not running — start it and check /api/ai/voice/status)"
echo
echo "Done. Tap the mic on the wall and talk. Try the voice:  curl -s -X POST localhost:8000/api/ai/tts -H 'Content-Type: application/json' -d '{\"text\":\"Hello from the wall\"}' -o /tmp/t.wav && aplay /tmp/t.wav"
