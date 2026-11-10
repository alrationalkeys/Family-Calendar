#!/bin/bash
# ============================================================================
# Make the wall a Bluetooth speaker ("Kitchen Wall" in any phone's Bluetooth
# list) playing through the USB speaker bar. Account-independent fallback for
# when Spotify refuses the open-source Connect client (librespot #1649).
#
#   cd ~/familyhub && bash setup/install-bt-speaker.sh ["Kitchen Wall"]
#
# Pairing is "just works" (no PIN): the wall auto-accepts and remembers each
# phone. Audio goes to the desktop's default output (setup/audio-default.sh).
# ============================================================================
set -euo pipefail
NAME="${1:-Kitchen Wall}"
say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "packages (bluez + PipeWire Bluetooth plugin + bt-agent)"
sudo apt-get install -y -qq bluez bluez-tools libspa-0.2-bluetooth pipewire-audio >/dev/null
sudo rfkill unblock bluetooth || true

say "bluetooth config: always discoverable, audio-sink class, name \"$NAME\""
sudo mkdir -p /etc/bluetooth
sudo tee /etc/bluetooth/main.conf >/dev/null <<EOF
[General]
Name = $NAME
Class = 0x200414
DiscoverableTimeout = 0
PairableTimeout = 0
JustWorksRepairing = always
FastConnectable = true

[Policy]
AutoEnable = true
ReconnectAttempts = 7
EOF
sudo systemctl enable --now bluetooth
sleep 2

say "auto-accept pairing agent (no PIN prompts on a wall with no keyboard)"
sudo tee /etc/systemd/system/bt-agent.service >/dev/null <<'EOF'
[Unit]
Description=Bluetooth auto-pairing agent (NoInputNoOutput)
After=bluetooth.service
Requires=bluetooth.service

[Service]
ExecStartPre=/bin/sleep 2
ExecStart=/usr/bin/bt-agent -c NoInputNoOutput
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now bt-agent

say "power on, discoverable, pairable"
bluetoothctl power on >/dev/null
bluetoothctl system-alias "$NAME" >/dev/null 2>&1 || true
bluetoothctl discoverable on >/dev/null
bluetoothctl pairable on >/dev/null

say "trust phones automatically once paired (so they reconnect without asking)"
# WirePlumber already routes a connected phone's audio to the default sink.
# This small watcher marks newly paired devices as trusted.
mkdir -p ~/.local/bin ~/.config/systemd/user
cat > ~/.local/bin/bt-autotrust.sh <<'EOF'
#!/bin/bash
# every 10 s: mark any paired-but-untrusted device as trusted
while true; do
  bluetoothctl devices Paired 2>/dev/null | awk '{print $2}' | while read -r mac; do
    bluetoothctl info "$mac" 2>/dev/null | grep -q "Trusted: no" && bluetoothctl trust "$mac" >/dev/null 2>&1
  done
  sleep 10
done
EOF
chmod +x ~/.local/bin/bt-autotrust.sh
cat > ~/.config/systemd/user/bt-autotrust.service <<EOF
[Unit]
Description=Trust newly paired Bluetooth devices
After=bluetooth.target

[Service]
ExecStart=$HOME/.local/bin/bt-autotrust.sh
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now bt-autotrust
sudo loginctl enable-linger "$(id -un)"

# PipeWire needs a restart to pick up the Bluetooth plugin the first time
systemctl --user restart wireplumber pipewire pipewire-pulse || true
sleep 2

echo
bluetoothctl show | grep -E "Name|Powered|Discoverable|Pairable" | sed 's/^/  /'
cat <<EOF

Done. On your phone: Settings → Bluetooth → pair with "$NAME" (no PIN).
Then play anything (Spotify, YouTube, podcasts) — it comes out of the speaker bar.
Volume: phone volume + the bar. The wall stays discoverable so other phones can pair too.
Only one phone plays at a time; the last one to connect wins.
EOF
