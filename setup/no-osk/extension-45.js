// FamilyHub: stop GNOME Shell auto-showing its on-screen keyboard on a touchscreen.
// GNOME shows it whenever the last input came from a touchscreen, even with the
// accessibility "Screen Keyboard" setting off; this makes that check always say "not touch".
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as Keyboard from 'resource:///org/gnome/shell/ui/keyboard.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class FamilyHubNoOsk extends Extension {
    enable() {
        const proto = Keyboard.KeyboardManager.prototype;
        this._orig = proto._lastDeviceIsTouchscreen;
        proto._lastDeviceIsTouchscreen = () => false;
        Main.keyboard?._syncEnabled?.();
    }

    disable() {
        if (this._orig)
            Keyboard.KeyboardManager.prototype._lastDeviceIsTouchscreen = this._orig;
        this._orig = null;
        Main.keyboard?._syncEnabled?.();
    }
}
