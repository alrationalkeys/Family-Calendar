#!/usr/bin/env bash
# FamilyHub — keep the wall PC on the network (Nov 2026).
#
# Why: the wall's Wi-Fi dropped one day and never came back until the power was pulled. Ubuntu on small PCs does
# this after a router or extender blip, or when Wi-Fi power saving puts the card to sleep.
#
# What it installs:
#   1. Wi-Fi power saving OFF (NetworkManager setting).
#   2. A check every 2 minutes: can the wall reach the router? If not 3 times in a row, it turns networking off and
#      on again; if that hasn't helped 3 checks later, it restarts NetworkManager. It never reboots the PC.
#      Every action is written to the system log:  journalctl -t familyhub-net
#
# Run once on the wall PC:   cd ~/familyhub && sudo bash setup/install-net-watchdog.sh
# Undo:  sudo systemctl disable --now familyhub-net.timer && sudo rm /etc/systemd/system/familyhub-net.* \
#          /usr/local/bin/familyhub-net-check /etc/NetworkManager/conf.d/99-familyhub-wifi-powersave.conf
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run with sudo:  sudo bash setup/install-net-watchdog.sh"; exit 1; }
command -v nmcli >/dev/null || { echo "This needs NetworkManager (nmcli), which Ubuntu desktop has."; exit 1; }

echo "1/3  Wi-Fi power saving off"
mkdir -p /etc/NetworkManager/conf.d
cat > /etc/NetworkManager/conf.d/99-familyhub-wifi-powersave.conf <<'CONF'
[connection]
# 2 = disable. Power saving lets the Wi-Fi card doze, and some cards never wake up properly.
wifi.powersave = 2
CONF

echo "2/3  the network check"
cat > /usr/local/bin/familyhub-net-check <<'CHECK'
#!/usr/bin/env bash
# Called every 2 minutes by familyhub-net.timer. Counts failed checks in a small state file.
STATE=/run/familyhub-net.fails
log(){ logger -t familyhub-net "$*"; }
gw=$(ip route show default 2>/dev/null | awk '/default/ {print $3; exit}')
target=${gw:-192.168.1.1}
if ping -c 2 -W 3 "$target" >/dev/null 2>&1; then
  if [ -s "$STATE" ] && [ "$(cat "$STATE")" -gt 0 ]; then log "network back (router $target answers)"; fi
  echo 0 > "$STATE"; exit 0
fi
n=$(( $(cat "$STATE" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$STATE"
log "router ${target} not answering (check $n)"
if [ "$n" -eq 3 ]; then
  log "turning networking off and on"
  nmcli networking off; sleep 5; nmcli networking on
elif [ "$n" -eq 6 ]; then
  log "still down: restarting NetworkManager"
  systemctl restart NetworkManager
elif [ "$n" -gt 6 ] && [ $(( n % 15 )) -eq 0 ]; then
  log "still down after $n checks: trying networking off/on again"
  nmcli networking off; sleep 5; nmcli networking on
fi
exit 0
CHECK
chmod 755 /usr/local/bin/familyhub-net-check

cat > /etc/systemd/system/familyhub-net.service <<'UNIT'
[Unit]
Description=FamilyHub: reconnect the network if it dropped
[Service]
Type=oneshot
ExecStart=/usr/local/bin/familyhub-net-check
UNIT
cat > /etc/systemd/system/familyhub-net.timer <<'UNIT'
[Unit]
Description=FamilyHub: check the network every 2 minutes
[Timer]
OnBootSec=3min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
UNIT

echo "3/3  turning it on"
systemctl daemon-reload
systemctl enable --now familyhub-net.timer
nmcli general reload conf 2>/dev/null || systemctl reload NetworkManager || true
echo
echo "Done. It checks every 2 minutes and logs what it does:  journalctl -t familyhub-net"
