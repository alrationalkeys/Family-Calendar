// FamilyHub: stop GNOME Shell auto-showing its on-screen keyboard on a touchscreen (GNOME 40-44).
const Main = imports.ui.main;
const Keyboard = imports.ui.keyboard;

let _orig = null;

function init() {}

function enable() {
    const proto = Keyboard.KeyboardManager.prototype;
    _orig = proto._lastDeviceIsTouchscreen;
    proto._lastDeviceIsTouchscreen = function () { return false; };
    if (Main.keyboard && Main.keyboard._syncEnabled) Main.keyboard._syncEnabled();
}

function disable() {
    if (_orig) Keyboard.KeyboardManager.prototype._lastDeviceIsTouchscreen = _orig;
    _orig = null;
    if (Main.keyboard && Main.keyboard._syncEnabled) Main.keyboard._syncEnabled();
}
