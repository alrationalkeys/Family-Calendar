#!/bin/bash
# ============================================================================
# Wyoming satellite on the SCREEN box: streams the kitchen USB mic to Home
# Assistant (which runs openWakeWord + Whisper + Piper) and plays replies back
# on the USB speaker. This is what makes hands-free "Hey <Name>, ..." work.
#
#   bash setup/install-satellite.sh <mic-device> <speaker-device> [name]
#   e.g. bash setup/install-satellite.sh plughw:1,0 plughw:1,0 kitchen
#
# Get the device names from setup/audio-check.sh. The satellite then shows up
# automatically in HA -> Settings -> Devices & Services (Wyoming Protocol).
# Guide: docs/home-assistant-setup.md, section F.
# ============================================================================
set -euo pipefail
MIC="${1:?mic device, e.g. plughw:1,0}"
SND="${2:?speaker device, e.g. plughw:1,0}"
NAME="${3:-kitchen}"
DIR="$HOME/wyoming-satellite"

say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "packages"
sudo apt-get install -y -qq git python3-venv alsa-utils

say "wyoming-satellite in $DIR"
if [ ! -d "$DIR" ]; then
  git clone https://github.com/rhasspy/wyoming-satellite.git "$DIR"
fi
cd "$DIR"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip wheel setuptools
.venv/bin/pip install -q -f 'https://synesthesiam.github.io/prebuilt-apps/' -e '.[silerovad]'

say "systemd service wyoming-satellite"
sudo tee /etc/systemd/system/wyoming-satellite.service >/dev/null <<EOF
[Unit]
Description=Wyoming voice satellite ($NAME)
After=network-online.target sound.target
Wants=network-online.target

[Service]
User=$(id -un)
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python -m wyoming_satellite \\
  --name '$NAME' \\
  --uri 'tcp://0.0.0.0:10700' \\
  --mic-command 'arecord -D $MIC -r 16000 -c 1 -f S16_LE -t raw' \\
  --snd-command 'aplay -D $SND -r 22050 -c 1 -f S16_LE -t raw' \\
  --mic-auto-gain 5 --mic-noise-suppression 2 \\
  --vad
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now wyoming-satellite
sleep 2
systemctl --no-pager --lines=5 status wyoming-satellite || true

cat <<EOF

Satellite "$NAME" is listening on port 10700.
Next, in Home Assistant: Settings -> Devices & Services -> it should appear as a
discovered "Wyoming Protocol" device -> Configure -> pick your voice pipeline
and turn on the wake word (openWakeWord). Then say "Hey <Name>, what time is it?"
EOF
