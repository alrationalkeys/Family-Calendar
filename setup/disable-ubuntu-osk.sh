#!/bin/bash
# Stop Ubuntu (GNOME) popping up its own on-screen keyboard on the touch wall.
# GNOME ignores the "Screen Keyboard" setting on touchscreens, so this installs a tiny
# GNOME Shell extension (setup/no-osk) that switches the touch auto-show off.
# Run as the kiosk user (FamilyHub's phone button does this). Takes effect after a restart
# of the wall computer (or logging out and back in).   Undo: bash setup/disable-ubuntu-osk.sh --undo
set -e
UUID="familyhub-no-osk@familyhub"
HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"

add_enabled() {   # add/remove $UUID in org.gnome.shell enabled-extensions
  python3 - "$1" "$UUID" <<'PY'
import ast, subprocess, sys
mode, uuid = sys.argv[1], sys.argv[2]
cur = subprocess.run(["gsettings", "get", "org.gnome.shell", "enabled-extensions"], capture_output=True, text=True).stdout.strip()
cur = cur.replace("@as ", "")
try:
    lst = ast.literal_eval(cur) if cur else []
except Exception:
    lst = []
lst = [x for x in lst if x != uuid] + ([uuid] if mode == "on" else [])
subprocess.run(["gsettings", "set", "org.gnome.shell", "enabled-extensions", str(lst)], check=True)
PY
}

if [ "$1" = "--undo" ]; then
  add_enabled off || true
  rm -rf "$DEST"
  gsettings set org.gnome.desktop.a11y.applications screen-keyboard-enabled true 2>/dev/null || true
  echo "Removed. Restart the wall computer to get Ubuntu's keyboard back."; exit 0
fi

VER=$(gnome-shell --version 2>/dev/null | grep -oE '[0-9]+' | head -1)
[ -z "$VER" ] && { echo "gnome-shell not found — is this the Ubuntu desktop?" >&2; exit 1; }
mkdir -p "$DEST"
if [ "$VER" -ge 45 ]; then
  cp "$HERE/no-osk/extension-45.js" "$DEST/extension.js"; cp "$HERE/no-osk/metadata-45.json" "$DEST/metadata.json"
else
  cp "$HERE/no-osk/extension-legacy.js" "$DEST/extension.js"; cp "$HERE/no-osk/metadata-legacy.json" "$DEST/metadata.json"
fi
gsettings set org.gnome.shell disable-user-extensions false 2>/dev/null || true
gsettings set org.gnome.desktop.a11y.applications screen-keyboard-enabled false 2>/dev/null || true
add_enabled on
gnome-extensions enable "$UUID" 2>/dev/null || true   # works at once if the shell already sees it; otherwise after restart
echo "OK: GNOME $VER. Restart the wall computer once to finish."
