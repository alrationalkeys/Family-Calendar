#!/bin/bash
# Hands-free wake word for the wall: say "Hey Jarvis, set a 5 minute timer for eggs" from across the kitchen.
# openWakeWord runs on this PC, offline, listening to the default microphone (the speaker bar). What you say after
# the word goes through the same Whisper + commands as the wall's mic button, so run setup/install-voice.sh first.
#
#   cd ~/familyhub && bash setup/install-wakeword.sh
#
# Pick the word / how easily it wakes: phone > Settings > Advanced > Voice.
# Your own word ("Hey Hub"...): train it free with openWakeWord's Colab notebook, then copy the .onnx file into
# ~/familyhub/models/wakeword/ and pick it on the phone (no restart needed).
set -e
cd "$(dirname "$0")/.."
say(){ printf '\n\033[1;36m%s\033[0m\n' "$*"; }
[ -x .venv/bin/pip ] || { echo "no .venv — run setup/install-kiosk.sh first"; exit 1; }

say "1/4  python packages (openWakeWord + onnxruntime)"
# --no-deps: openWakeWord asks for tflite-runtime, which has no build for this Python. We use its ONNX models instead.
.venv/bin/pip install -q --upgrade onnxruntime scipy tqdm requests scikit-learn numpy
.venv/bin/pip install -q --upgrade --no-deps "openwakeword>=0.6,<0.7"

say "2/4  wake word models (~10 MB, downloaded once)"
.venv/bin/python - <<'PY'
import openwakeword.utils as u
u.download_models(["hey_jarvis", "hey_mycroft", "hey_rhasspy", "alexa"])
from openwakeword.model import Model
Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
print("models ok")
PY
mkdir -p models/wakeword

say "3/4  microphone"
command -v parec >/dev/null || command -v arecord >/dev/null || sudo apt-get install -y pulseaudio-utils
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
echo "Say something for 3 seconds…"
if command -v parec >/dev/null; then
  timeout 3 parec --raw --format=s16le --rate=16000 --channels=1 > /tmp/fh-wake-test.raw 2>/dev/null || true
else
  timeout 3 arecord -q -D default -f S16_LE -r 16000 -c 1 -t raw > /tmp/fh-wake-test.raw 2>/dev/null || true
fi
.venv/bin/python - <<'PY'
import numpy as np
a = np.fromfile("/tmp/fh-wake-test.raw", dtype=np.int16).astype(np.float32) / 32768
if not a.size:
    print("!! no sound recorded. Is the speaker bar the default input?  bash setup/audio-default.sh"); raise SystemExit
peak = float(np.abs(a).max())
print(f"recorded {a.size/16000:.1f} s, loudest {peak:.2f}", "(good)" if peak > 0.05 else "(very quiet — check the mic / run setup/audio-default.sh)")
PY
rm -f /tmp/fh-wake-test.raw

say "4/4  restart FamilyHub"
if systemctl is-active --quiet familyhub; then sudo systemctl restart familyhub; sleep 8; fi
curl -fs http://localhost:8000/api/ai/wake | .venv/bin/python -c 'import json,sys; w=json.load(sys.stdin); print("listening for", w["name"], "on", w["mic"]) if w["running"] else print("not listening yet:", w["error"] or "starting… (check again in a minute: curl localhost:8000/api/ai/wake)")' \
  || echo "(server not running — start it and check  curl localhost:8000/api/ai/wake)"
echo
echo 'Done. From across the kitchen say:  "Hey Jarvis"  (wait for the chime or just keep going)  "set a 5 minute timer for eggs".'
