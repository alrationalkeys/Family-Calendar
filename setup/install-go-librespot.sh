#!/bin/bash
# ============================================================================
# Make the wall a Spotify Connect speaker using go-librespot (an independent,
# Go-based Connect client). Try this when spotifyd skips every track with
# "audio key error" — Spotify's block on librespot doesn't always hit this one.
#
#   cd ~/familyhub && bash setup/install-go-librespot.sh ["Kitchen Wall"] [pulse|alsa-device]
#
# Plays through the desktop's default output (the speaker bar, per
# setup/audio-default.sh). Runs as a user service. Needs Spotify Premium.
# No password stored: pick "Kitchen Wall" in the Spotify app (zeroconf).
# ============================================================================
set -euo pipefail
NAME="${1:-Kitchen Wall}"
DEV="${2:-pulse}"
say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "packages"
sudo apt-get install -y -qq curl tar libvorbis0a libogg0 libmpg123-0 >/dev/null
sudo apt-get install -y -qq libflac12t64 >/dev/null 2>&1 || sudo apt-get install -y -qq libflac12 >/dev/null 2>&1 || sudo apt-get install -y -qq libflac8 >/dev/null 2>&1 || true
sudo apt-get install -y -qq libasound2t64 >/dev/null 2>&1 || sudo apt-get install -y -qq libasound2 >/dev/null 2>&1 || true

say "stop spotifyd if it's running (two Connect speakers would confuse the app)"
systemctl --user disable --now spotifyd 2>/dev/null || true

say "go-librespot binary"
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)  ASSET="go-librespot_linux_x86_64.tar.gz" ;;
  aarch64) ASSET="go-librespot_linux_arm64.tar.gz" ;;
  armv7l|armv6l) ASSET="go-librespot_linux_armv6.tar.gz" ;;
  *) echo "unsupported arch $ARCH"; exit 1 ;;
esac
URL="https://github.com/devgianlu/go-librespot/releases/latest/download/$ASSET"
TMP=$(mktemp -d); curl -fsSL "$URL" | tar -xz -C "$TMP"
BIN=$(find "$TMP" -type f -name 'go-librespot*' ! -name '*.tar.gz' | head -1)
[ -n "$BIN" ] || { echo "binary not found in $ASSET"; ls -R "$TMP"; exit 1; }
sudo install -m 755 "$BIN" /usr/local/bin/go-librespot; rm -rf "$TMP"
go-librespot -version 2>/dev/null || true

say "config ~/.config/go-librespot/config.yml"
mkdir -p ~/.config/go-librespot
if [ "$DEV" = "pulse" ]; then
  AUDIO=$'audio_backend: pulseaudio'
else
  AUDIO=$(printf 'audio_backend: alsa\naudio_device: %s' "$DEV")
fi
cat > ~/.config/go-librespot/config.yml <<EOF
device_name: "$NAME"
device_type: speaker
$AUDIO
bitrate: 160
zeroconf_enabled: true
credentials:
  type: zeroconf
  zeroconf:
    persist_credentials: true
server:
  enabled: false
log_level: info
EOF

say "systemd --user service go-librespot"
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/go-librespot.service <<'EOF'
[Unit]
Description=Spotify Connect speaker (go-librespot)
After=network-online.target pipewire-pulse.service

[Service]
ExecStart=/usr/local/bin/go-librespot
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF
sudo loginctl enable-linger "$(id -un)"
systemctl --user daemon-reload
systemctl --user enable --now go-librespot
sleep 3
systemctl --user --no-pager --lines=8 status go-librespot || true

cat <<EOF

Open Spotify on your phone → play something → devices icon → "$NAME".
If tracks skip again, check:  journalctl --user -u go-librespot -n 30
Fallback that never depends on Spotify:  bash setup/install-bt-speaker.sh "$NAME"
EOF
