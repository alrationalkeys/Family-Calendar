#!/bin/bash
# ============================================================================
# FamilyHub — one-shot kiosk installer for the SCREEN box (the C3 mini PC).
#
# Run this ONCE on a fresh Ubuntu Desktop 24.04 install, logged in as the
# user that will own the wall (we suggest the username "hub"):
#
#     git clone https://github.com/alrationalkeys/Family-Calendar ~/familyhub
#     cd ~/familyhub && bash setup/install-kiosk.sh
#
# It is safe to re-run. What it does, in order:
#   1. apt packages: chromium, python3-venv, unclutter, alsa-utils, git, curl
#   2. python venv + requirements
#   3. .env from .env.example (if missing) with x86 screen-off commands set
#   4. familyhub.service (+ daily backup timer) as systemd units
#   5. auto-login to this user, Xorg session, no screen blanking / lock
#   6. kiosk.sh in the desktop autostart -> Chromium full-screen on boot
# Full walkthrough: docs/first-boot.md
# ============================================================================
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
  echo "Run this as the normal kiosk user (not root/sudo); it will sudo when needed." >&2; exit 1
fi
REPO="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
HOME_DIR="$HOME"
if [ "$REPO" != "$HOME_DIR/familyhub" ]; then
  echo "Expected the repo at $HOME_DIR/familyhub (it's at $REPO)."
  echo "   mv \"$REPO\" \"$HOME_DIR/familyhub\" && cd ~/familyhub && bash setup/install-kiosk.sh"; exit 1
fi

say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "1/6  apt packages"
sudo apt-get update -qq
# Ubuntu's chromium is a snap; Debian's is a deb. Either is fine for kiosk.sh.
sudo apt-get install -y -qq chromium-browser git curl python3 python3-venv python3-pip \
  unclutter alsa-utils x11-xserver-utils >/dev/null 2>&1 || \
sudo apt-get install -y -qq chromium git curl python3 python3-venv python3-pip \
  unclutter alsa-utils x11-xserver-utils

say "2/6  python venv"
cd "$REPO"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

say "3/6  .env"
if [ ! -f .env ]; then
  cp .env.example .env
  cat >> .env <<'EOF'

# --- set by setup/install-kiosk.sh (x86 kiosk on Xorg) ----------------------
FAMILYHUB_SCREEN_OFF_CMD=xset dpms force off
FAMILYHUB_SCREEN_ON_CMD=xset dpms force on
EOF
  echo "   wrote .env — add ANTHROPIC_API_KEY / HA_URL / HA_TOKEN later with: nano ~/familyhub/.env"
else
  echo "   .env already exists, leaving it alone"
fi
mkdir -p static/photos backups

say "4/6  systemd services"
for u in familyhub.service familyhub-backup.service familyhub-backup.timer; do
  sed "s|__USER__|$USER_NAME|g; s|__HOME__|$HOME_DIR|g" "$u" | sudo tee /etc/systemd/system/$u >/dev/null
done
sudo systemctl daemon-reload
sudo systemctl enable --now familyhub.service familyhub-backup.timer
sleep 2
if curl -fs http://localhost:8000/api/auth/status >/dev/null; then
  echo "   FamilyHub server is up on http://localhost:8000"
else
  echo "   server not answering yet — check: journalctl -u familyhub -n 50"
fi

# time zone — the night screen-off window, reminders and "today" all run on local time
TZONE="${FAMILYHUB_TZ:-America/New_York}"
sudo timedatectl set-timezone "$TZONE" 2>/dev/null && echo "   time zone: $TZONE (override with FAMILYHUB_TZ=Region/City)"
sudo timedatectl set-ntp true 2>/dev/null || true

say "5/6  desktop: auto-login, Xorg session, never blank or lock"
# GDM auto-login + force the Xorg session (xset needs X; Wayland can't cut the HDMI signal)
sudo mkdir -p /etc/gdm3
if [ -f /etc/gdm3/custom.conf ]; then
  sudo sed -i '/^\[daemon\]/,/^\[/{/AutomaticLogin/d;/WaylandEnable/d}' /etc/gdm3/custom.conf
  sudo sed -i "s/^\[daemon\]/[daemon]\nAutomaticLoginEnable=true\nAutomaticLogin=$USER_NAME\nWaylandEnable=false/" /etc/gdm3/custom.conf
else
  printf '[daemon]\nAutomaticLoginEnable=true\nAutomaticLogin=%s\nWaylandEnable=false\n' "$USER_NAME" | sudo tee /etc/gdm3/custom.conf >/dev/null
fi
sudo mkdir -p /var/lib/AccountsService/users
printf '[User]\nSession=ubuntu-xorg\nXSession=ubuntu-xorg\n' | sudo tee /var/lib/AccountsService/users/$USER_NAME >/dev/null
# GNOME: no idle dim, no screensaver, no lock, no auto-suspend, no notifications banner
if command -v gsettings >/dev/null; then
  gsettings set org.gnome.desktop.session idle-delay 0 || true
  gsettings set org.gnome.desktop.screensaver lock-enabled false || true
  gsettings set org.gnome.desktop.screensaver idle-activation-enabled false || true
  gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing' || true
  gsettings set org.gnome.settings-daemon.plugins.power idle-dim false || true
  gsettings set org.gnome.desktop.notifications show-banners false || true
  gsettings set org.gnome.desktop.interface enable-hot-corners false || true
fi
# don't let a power blip's "software updater" popup cover the calendar
sudo systemctl disable --now apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
gsettings set com.ubuntu.update-notifier no-show-notifications true 2>/dev/null || true

say "6/6  kiosk autostart"
chmod +x "$REPO/kiosk.sh"
mkdir -p "$HOME_DIR/.config/autostart"
cat > "$HOME_DIR/.config/autostart/familyhub-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=FamilyHub kiosk
Exec=$REPO/kiosk.sh
X-GNOME-Autostart-enabled=true
EOF

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
cat <<EOF

Done.
  Wall:   http://localhost:8000      (opens full-screen on next boot)
  Phone:  http://${IP:-<this-ip>}:8000/phone.html
  Logs:   journalctl -u familyhub -f
  Audio:  bash setup/audio-check.sh   (after the USB speaker/mic is plugged in)

Reboot now to see the kiosk come up:  sudo reboot
EOF
