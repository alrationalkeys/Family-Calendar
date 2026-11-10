#!/bin/bash
# Switch the wall's kiosk browser from Ubuntu's snap Chromium to Google Chrome (.deb).
# Why: the snap has no Widevine DRM module, so Spotify's Web Playback SDK registers the
# wall as a device but can't decode audio ("Widevine not available"). Chrome ships
# Widevine built in. kiosk.sh already prefers google-chrome when it's installed.
#   cd ~/familyhub && bash setup/install-chrome.sh
set -e
say(){ printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "Google Chrome (stable .deb)"
TMP=$(mktemp -d)
curl -fsSL -o "$TMP/chrome.deb" https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y -qq "$TMP/chrome.deb" >/dev/null 2>&1 || sudo apt-get install -y -qq -f
rm -rf "$TMP"
google-chrome --version

say "Widevine present?"
if ls /opt/google/chrome/WidevineCdm/_platform_specific/linux_x64/libwidevinecdm.so >/dev/null 2>&1; then
  echo "  yes: /opt/google/chrome/WidevineCdm"
else
  echo "  not bundled — Chrome fetches it on first DRM use (chrome://components → Widevine)"
fi

say "restart the kiosk on Chrome (kiosk.sh picks google-chrome over chromium when present)"
pkill -f familyhub-kiosk-profile 2>/dev/null || true
sleep 1
# make sure the snap isn't what relaunches
if command -v chromium >/dev/null && snap list chromium >/dev/null 2>&1; then
  echo "  (snap chromium left installed but kiosk.sh now prefers google-chrome; remove later with: sudo snap remove chromium)"
fi
echo
echo "Done. kiosk.sh relaunches the wall in Chrome within a few seconds."
echo "Then: phone app → Settings → Spotify → refresh. The player log should show 'drm: widevine ok'."
