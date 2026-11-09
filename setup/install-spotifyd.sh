#!/bin/bash
# ============================================================================
# Make the wall a Spotify Connect speaker ("Kitchen Wall" in the Spotify app),
# playing through the USB speaker bar. Runs spotifyd as a systemd service on
# the SCREEN box. Needs Spotify Premium (Connect is a Premium feature).
#
#   bash setup/install-spotifyd.sh [pulse|alsa-device] [device-name]
#   e.g. bash setup/install-spotifyd.sh pulse "Kitchen Wall"        (recommended)
#        bash setup/install-spotifyd.sh plughw:1,0 "Kitchen Wall"   (raw ALSA)
#
# "pulse" plays through the desktop's sound server (PipeWire), i.e. whatever
# setup/audio-default.sh made the default output, and doesn't fight Chromium
# for the sound card. A raw plughw:X,Y device grabs the card exclusively.
# Runs as a *user* service (the kiosk user is auto-logged-in) so it can reach
# the sound server. No Spotify password is stored: zeroconf discovery only.
# ============================================================================
set -euo pipefail
DEV="${1:-pulse}"
NAME="${2:-Kitchen Wall}"
say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "packages"
# Ubuntu 24.04 renamed libasound2 -> libasound2t64
sudo apt-get install -y -qq curl tar alsa-utils libasound2t64 >/dev/null 2>&1 || \
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
if [ "$DEV" = "pulse" ]; then
  AUDIO='backend = "pulseaudio"'
else
  AUDIO=$(printf 'backend = "alsa"\ndevice = "%s"\nmixer = "PCM"' "$DEV")
fi
cat > ~/.config/spotifyd/spotifyd.conf <<EOF
[global]
device_name = "$NAME"
$AUDIO
bitrate = 320
initial_volume = "60"
device_type = "speaker"
zeroconf_port = 5354
autoplay = true
EOF

say "systemd --user service spotifyd (runs in your desktop session, survives reboots)"
# a stale system-wide unit from an older install would fight this one
sudo systemctl disable --now spotifyd 2>/dev/null || true; sudo rm -f /etc/systemd/system/spotifyd.service
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/spotifyd.service <<EOF
[Unit]
Description=Spotify Connect speaker ($NAME)
After=network-online.target pipewire-pulse.service

[Service]
ExecStart=/usr/local/bin/spotifyd --no-daemon --config-path %h/.config/spotifyd/spotifyd.conf
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF
sudo loginctl enable-linger "$(id -un)"      # user services start at boot, not just at login
systemctl --user daemon-reload
systemctl --user enable --now spotifyd
sleep 3
systemctl --user --no-pager --lines=6 status spotifyd || true

cat <<EOF

Open Spotify on your phone → play something → tap the devices icon → "$NAME".
If it doesn't appear: phone and wall must be on the same Wi-Fi/LAN, and mDNS
(zeroconf) must not be blocked by the router's "AP isolation".
EOF
