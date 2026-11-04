#!/bin/bash
# ============================================================================
# Make the wall a Spotify Connect speaker ("Kitchen Wall" in the Spotify app),
# playing through the USB speaker bar. Runs spotifyd as a systemd service on
# the SCREEN box. Needs Spotify Premium (Connect is a Premium feature).
#
#   bash setup/install-spotifyd.sh [alsa-device] [device-name]
#   e.g. bash setup/install-spotifyd.sh plughw:1,0 "Kitchen Wall"
#
# Get the ALSA device name from setup/audio-check.sh. No Spotify password is
# stored: the device uses zeroconf discovery, so you just pick it in the app.
# ============================================================================
set -euo pipefail
DEV="${1:-default}"
NAME="${2:-Kitchen Wall}"
say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "packages"
sudo apt-get install -y -qq curl tar alsa-utils libasound2 >/dev/null

say "spotifyd binary"
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)  ASSET="spotifyd-linux-x86_64-default.tar.gz" ;;
  aarch64) ASSET="spotifyd-linux-aarch64-default.tar.gz" ;;
  armv7l)  ASSET="spotifyd-linux-armv7-default.tar.gz" ;;
  *) echo "unsupported arch $ARCH"; exit 1 ;;
esac
URL=$(curl -fsSL https://api.github.com/repos/Spotifyd/spotifyd/releases/latest | grep -oE "https://[^\"]+/$ASSET" | head -1)
[ -n "$URL" ] || { echo "couldn't find a release asset named $ASSET — check github.com/Spotifyd/spotifyd/releases"; exit 1; }
TMP=$(mktemp -d); curl -fsSL "$URL" | tar -xz -C "$TMP"
sudo install -m 755 "$TMP/spotifyd" /usr/local/bin/spotifyd; rm -rf "$TMP"
spotifyd --version

say "config ~/.config/spotifyd/spotifyd.conf"
mkdir -p ~/.config/spotifyd
cat > ~/.config/spotifyd/spotifyd.conf <<EOF
[global]
device_name = "$NAME"
backend = "alsa"
device = "$DEV"
mixer = "PCM"
bitrate = 320
initial_volume = "60"
device_type = "speaker"
zeroconf_port = 5354
autoplay = true
EOF

say "systemd service spotifyd"
sudo tee /etc/systemd/system/spotifyd.service >/dev/null <<EOF
[Unit]
Description=Spotify Connect speaker ($NAME)
After=network-online.target sound.target
Wants=network-online.target

[Service]
User=$(id -un)
ExecStart=/usr/local/bin/spotifyd --no-daemon --config-path $HOME/.config/spotifyd/spotifyd.conf
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now spotifyd
sleep 2
systemctl --no-pager --lines=5 status spotifyd || true

cat <<EOF

Open Spotify on your phone → play something → tap the devices icon → "$NAME".
If it doesn't appear: phone and wall must be on the same Wi-Fi/LAN, and mDNS
(zeroconf) must not be blocked by the router's "AP isolation".
EOF
