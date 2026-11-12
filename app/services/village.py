"""
North Pole Village (the Christmas village) — talks straight to the two ESP32 boards over the LAN
(docs/village/README.md). No firmware changes: the same /cmd, /go, /stop and /status endpoints the
phone pages use.

  Board A  village-fx     settings.villageFx     effects hub: shows, sounds, rink, lamps, manual mode
  Board B  village-train  settings.villageTrain  train laps / stop

The village runs its own clock (open 16:00-23:00) and motion wake. FamilyHub only adds buttons, voice,
and "quiet for the night": Good night / Leaving put it to sleep, lights off and in the board's manual
mode (otherwise motion — the dogs — wakes it right back up). FamilyHub remembers that it did that and
puts the board back on automatic the next morning (06:00-15:59) or at "I'm home". If someone put the
board in manual mode themselves, FamilyHub leaves it there.
"""
from __future__ import annotations

import ipaddress
import json
import re
import threading
import time
import urllib.parse
import urllib.request

from ..db import get_db

DEFAULT_FX, DEFAULT_TRAIN = "192.168.1.200", "192.168.1.121"
_cache = {"at": 0.0, "data": None}
_lock = threading.Lock()

# what the wall/phone/voice may ask for -> (board, path)
COMMANDS = {
    "wake": ("fx", "/cmd?do=wake"),
    "sleep": ("fx", "/cmd?do=sleep"),
    "tree": ("fx", "/cmd?do=tree"),
    "rachell": ("fx", "/cmd?do=rachell"),
    "carol": ("fx", "/cmd?do=carol"),
    "train": ("fx", "/cmd?do=train"),           # whistle, then the button laps
    "stop": ("train", "/stop"),
    "laps1": ("train", "/go?laps=1"),
    "laps3": ("train", "/go?laps=3"),
    "rinkon": ("fx", "/cmd?do=rinkon"),
    "rinkoff": ("fx", "/cmd?do=rinkoff"),
}


def _settings() -> dict:
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='ui'").fetchone()
            return json.loads(row["value"]) if row else {}
    except Exception:
        return {}


def _host(kind: str) -> str:
    s = _settings()
    raw = str(s.get("villageFx" if kind == "fx" else "villageTrain") or (DEFAULT_FX if kind == "fx" else DEFAULT_TRAIN)).strip()
    try:                                    # only private LAN addresses (no proxying FamilyHub to the internet)
        if ipaddress.ip_address(raw).is_private:
            return raw
    except ValueError:
        pass
    return DEFAULT_FX if kind == "fx" else DEFAULT_TRAIN


def _get(kind: str, path: str, timeout: float = 2.0) -> str:
    with urllib.request.urlopen(f"http://{_host(kind)}{path}", timeout=timeout) as r:
        return r.read(4096).decode("utf-8", "replace")


def _flag(value=None):
    """'village_paused' = FamilyHub put the board in manual mode for the night."""
    with get_db() as conn:
        if value is None:
            row = conn.execute("SELECT value FROM settings WHERE key='village_paused'").fetchone()
            return bool(row and row["value"] == "1")
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('village_paused', ?)", ("1" if value else "0",))


def _parse(fx: str | None, tr: str | None) -> dict:
    d = {"reachable": fx is not None}
    if fx is not None:
        m = re.search(r"Mode: ([^\n(]+)", fx)
        d["mode"] = (m.group(1).strip() if m else "unknown")
        d["manual"] = fx.startswith("MANUAL")
        d["motion"] = bool(re.search(r"Motion: *\S", fx))
        d["lamps"] = "Street lamps: on" in fx
    if tr is not None:
        m = re.search(r"State: ([^\n]+)", tr)
        d["train"] = m.group(1).strip() if m else "unknown"
        m = re.search(r"Laps left: (\d+)", tr)
        d["laps_left"] = int(m.group(1)) if m else 0
    d["paused_by_hub"] = _flag() if fx is not None else False
    return d


def status(max_age: float = 8.0) -> dict:
    """Both boards' status. Unreachable (packed away / unplugged) is cached for a minute so the wall's
    Home page doesn't wait on dead IPs every refresh."""
    now = time.time()
    with _lock:
        c = _cache["data"]
        if c is not None and now - _cache["at"] < (max_age if c.get("reachable") else 60.0):
            return c
    fx = tr = None
    try:
        fx = _get("fx", "/status", 1.5)
    except Exception:
        pass
    if fx is not None:
        try:
            tr = _get("train", "/status", 1.5)
        except Exception:
            pass
    data = _parse(fx, tr)
    data["said"] = _say(data)
    with _lock:
        _cache.update(at=now, data=data)
    return data


def _say(d: dict) -> str:
    if not d.get("reachable"):
        return "The village isn't answering."
    mode = d.get("mode", "")
    parts = [{"awake": "Awake", "sleepy": "Sleepy", "closed": "Closed for the night", "tree show": "Tree show",
              "Rachell show": "Rachell's show"}.get(mode, mode.capitalize())]
    if d.get("manual"):
        parts.append("resting for the night" if d.get("paused_by_hub") else "manual mode")
    if d.get("train"):
        t = d["train"]
        parts.append("train " + ("at the station" if t.startswith("stopped") else t))
    return " · ".join(parts)


def command(name: str) -> dict:
    if name not in COMMANDS:
        return {"ok": False, "reason": "unknown village command"}
    board, path = COMMANDS[name]
    try:
        _get(board, path, 3.0)
    except Exception:
        return {"ok": False, "reason": "the village isn't answering"}
    if name in ("wake", "tree", "rachell", "carol", "train") and _flag():
        # someone wants a show: FamilyHub's night pause is over
        resume()
    with _lock:
        _cache["at"] = 0.0
    return {"ok": True}


def pause_for_night() -> str | None:
    """Good night / Leaving. Returns a phrase for the spoken summary, or None if there's no village."""
    try:
        fx = _get("fx", "/status", 1.5)
    except Exception:
        return None
    try:
        _get("fx", "/cmd?do=sleep", 3.0)
        try:
            _get("train", "/stop", 2.0)
        except Exception:
            pass
        if not fx.startswith("MANUAL"):          # automatic -> manual, so motion can't wake it tonight
            _get("fx", "/cmd?do=manual", 3.0)
            _flag(True)
        _get("fx", "/cmd?do=light:1", 3.0)       # WLED preset 1 = Off
        _get("fx", "/cmd?do=rinkoff", 3.0)
    except Exception:
        return None
    with _lock:
        _cache["at"] = 0.0
    return "put the village to sleep"


def resume() -> bool:
    """Back to automatic — only if FamilyHub paused it (and it's still in manual mode)."""
    if not _flag():
        return False
    try:
        fx = _get("fx", "/status", 1.5)
        if fx.startswith("MANUAL"):
            _get("fx", "/cmd?do=manual", 3.0)    # toggle -> automatic; the board picks sleepy/closed by its clock
        _flag(False)
    except Exception:
        return False
    with _lock:
        _cache["at"] = 0.0
    return True


def _morning_loop():
    while True:
        time.sleep(300)
        try:
            if 6 <= time.localtime().tm_hour < 16 and _flag():
                resume()
        except Exception:
            pass


def start():
    threading.Thread(target=_morning_loop, daemon=True, name="village-morning").start()
