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
    "sleep": ("fx", "/cmd?do=sleep"),       # sent as "close" (lights off, train stopped) to boards that follow FamilyHub
    "open": ("fx", "/cmd?do=open"),
    "close": ("fx", "/cmd?do=close"),
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


# Spectrum's router can't reserve addresses, so a board can come back on a new one after a power blip. When the
# saved address stops answering FamilyHub finds the board again: the train from Board A's /links (Board A hears the
# train's own announcements), Board A from its village-fx.local name. The found address is remembered until it fails.
_found: dict = {}
_FIND_NAMES = {"fx": "village-fx.local", "train": "village-train.local"}


def _private(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def _fetch(host: str, path: str, timeout: float) -> str:
    with urllib.request.urlopen(f"http://{host}{path}", timeout=timeout) as r:
        return r.read(4096).decode("utf-8", "replace")


def _find(kind: str) -> str | None:
    """Where the board is now, or None. Only private LAN addresses."""
    cand = []
    if kind == "train":
        try:
            lines = _get("fx", "/links", 1.5).splitlines()
            if len(lines) > 1 and _private(lines[1].strip()):
                cand.append(lines[1].strip())
        except Exception:
            pass
    try:
        import socket
        ip = socket.gethostbyname(_FIND_NAMES[kind])
        if _private(ip):
            cand.append(ip)
    except Exception:
        pass
    return cand[0] if cand else None


def _get(kind: str, path: str, timeout: float = 2.0) -> str:
    saved = _host(kind)
    host = _found.get(kind) or saved
    try:
        return _fetch(host, path, timeout)
    except Exception:
        _found.pop(kind, None)
        new = _find(kind)
        if not new or new == host:
            raise
        out = _fetch(new, path, timeout)
        _found[kind] = new
        return out


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
    try:
        data["tonight"] = _auto()
    except Exception:
        pass
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
    if name == "sleep" and _follows():
        ok = close_for_night("asked")           # "put the village to sleep" = closed for the night, not sleepy
        return {"ok": True} if ok else {"ok": False, "reason": "the village isn't answering"}
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


def pause_for_night(mode: str = "goodnight") -> str | None:
    """Good night / Leaving. Returns a phrase for the spoken summary, or None if there's no village.
    Good night = closed until morning. Leaving = closed while we're out; I'm home in the evening opens it again."""
    try:
        fx = _get("fx", "/status", 1.5)
    except Exception:
        return None
    if "follows FamilyHub" in fx:                # A-2026.11.18b and later: one "close" does it all, no manual mode
        if mode == "away":
            return "put the village to sleep until you're back" if close_for_night("left the house", night=False) else None
        return "put the village to sleep" if close_for_night("good night") else None
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


def back_home() -> str | None:
    """I'm home: in the evening (and not closed for the night), open the village again."""
    a = _auto()
    if a.get("closed") or a.get("opened") or not _evening_now() or _bedtime_now():
        return None
    return "opened the village" if open_for_evening("home again") else None


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


# ---------------------------------------------------------------- follow the house (A-2026.11.18b+)
# Open when the outside lights come on in the evening; closed for the night at bedtime (Good night, the alarm set
# for the night, or a Home Assistant scene / script called "go to sleep", "good night" or "bedtime"). Once closed,
# it stays closed until the next evening, even if the outside lights are still on. settings.villageAuto (default on).

_NIGHT_NAME = re.compile(r"go to sleep|good ?night|bed ?time|night ?night", re.I)
_OUTSIDE = re.compile(r"exterior|outdoor|outside|porch|driveway|landscape|soffit|eave|front yard|back yard|yard light|flood", re.I)


def _follows() -> bool:
    try:
        return "follows FamilyHub" in _get("fx", "/status", 1.5)
    except Exception:
        return False


def _night() -> str:
    """The evening this moment belongs to: 1 AM still counts as last night; a new one starts at 6 AM."""
    return time.strftime("%Y-%m-%d", time.localtime(time.time() - 6 * 3600))


def _auto(update: dict | None = None) -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='village_auto'").fetchone()
        try:
            d = json.loads(row["value"]) if row and row["value"] else {}
        except Exception:
            d = {}
        if d.get("night") != _night():
            d = {"night": _night()}
        if update:
            d.update(update)
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('village_auto', ?)", (json.dumps(d),))
    return d


def open_lights(states: list) -> list:
    """The outside lights that open the village: settings.villageOpenLights if picked on the phone, else the
    nightly + holiday outdoor lights lists (outdoor_lights.yaml), else lights/plugs named like outside lights. Never the
    Christmas display plug (it blinks for walk-ups) or the village itself."""
    s = _settings()
    pick = [e for e in (s.get("villageOpenLights") or []) if isinstance(e, str)]
    if pick:
        return pick
    # the nightly lights AND the holiday lights: in holiday season sunset turns on only the holiday plug (the nightly
    # lights wait for the 11:50 PM switch-over), so watching the nightly list alone opened the village near midnight
    ids = []
    for key in ("input_text.fh_outdoor_night_lights", "input_text.fh_outdoor_holiday_lights"):
        for st in states:
            if st.get("entity_id") == key:
                ids += [x.strip() for x in str(st.get("state") or "").split(",")
                        if x.strip().startswith(("light.", "switch.")) and x.strip() not in ids]
    if ids:
        return ids
    xplug = ""
    try:
        from . import xmas
        xplug = xmas.plug({x["entity_id"]: x for x in states}) or ""
    except Exception:
        pass
    out = []
    for st in states:
        eid = st.get("entity_id", "")
        name = eid + " " + str((st.get("attributes") or {}).get("friendly_name", ""))
        if eid.split(".")[0] in ("light", "switch") and _OUTSIDE.search(name) and not re.search(r"village|christmas|xmas", name, re.I) and eid != xplug:
            out.append(eid)
    return out


def _evening_now() -> bool:
    h = time.localtime().tm_hour
    return h >= 15 or h < 2


def _daytime() -> bool:
    return 6 <= time.localtime().tm_hour < 15


def _bedtime_now() -> bool:
    try:
        from . import display_svc
        return bool(display_svc._state.get("sleep_mode"))
    except Exception:
        return False


def open_for_evening(why: str) -> bool:
    if _settings().get("villageAuto", True) is False:
        return False
    a = _auto()
    if a.get("closed") or a.get("opened") or not _evening_now() or _bedtime_now():
        return False
    try:
        _get("fx", "/cmd?do=open", 3.0)
    except Exception:
        return False
    _auto({"opened": time.strftime("%H:%M"), "why_open": why})
    with _lock:
        _cache["at"] = 0.0
    return True


def close_for_night(why: str, night: bool = True) -> bool:
    """night=False (Leaving): close now, but coming home this evening opens it again (I'm home -> back_home)."""
    try:
        _get("fx", "/cmd?do=close", 3.0)          # lights off, rink off, train stopped (the board does it all)
    except Exception:
        return False
    if not night:
        _auto({"opened": None, "away": time.strftime("%H:%M")})
    elif not _daytime():
        _auto({"closed": time.strftime("%H:%M"), "why_closed": why})
    else:                                           # a daytime close never keeps tonight shut; kept only for Diagnostics
        _auto({"day_close": time.strftime("%H:%M") + " " + why})
    with _lock:
        _cache["at"] = 0.0
    return True


def on_state(eid: str, old: dict | None, new: dict | None, states: dict):
    """From ha_live: outside lights coming on, or a bedtime scene / script being run in Home Assistant."""
    if not new or _settings().get("villageAuto", True) is False:
        return
    dom = eid.split(".", 1)[0]
    name = eid.replace("_", " ") + " " + str((new.get("attributes") or {}).get("friendly_name", ""))
    try:
        if dom in ("scene", "script") and _NIGHT_NAME.search(name):
            # a scene "ran" only when its timestamp changes from a real earlier one: Home Assistant restarting (or the
            # live link reconnecting) takes it unavailable -> timestamp, which is not anyone saying good night
            was = (old or {}).get("state")
            ran = (dom == "scene" and old is not None and was not in (None, "", "unavailable", "unknown")
                   and new.get("state") != was and new.get("state") not in ("unavailable", "unknown")) \
                or (dom == "script" and new.get("state") == "on" and (old or {}).get("state") == "off")
            if ran and _settings().get("villageWithHouse", True) is not False:
                threading.Thread(target=close_for_night, args=("Home Assistant: " + name.strip(),), daemon=True).start()
            return
        if dom in ("light", "switch") and new.get("state") == "on" and (old or {}).get("state") == "off":
            try:
                from . import gameday
                if eid in (gameday._S.get("flashing") or ()):
                    return                           # a touchdown flash, not the evening
            except Exception:
                pass
            if eid in open_lights(list(states.values()) if isinstance(states, dict) else states):
                threading.Thread(target=open_for_evening, args=("outside lights on",), daemon=True).start()
    except Exception:
        pass


def _catch_up():
    """Every 5 minutes: outside lights already on in the evening and not opened yet (FamilyHub was restarted, or the
    lights came on while the link was down) -> open. Never after bedtime."""
    if _settings().get("villageAuto", True) is False or not _evening_now() or _bedtime_now():
        return
    a = _auto()
    if a.get("opened") or a.get("closed"):
        return
    try:
        from . import ha_live
        states = ha_live.states() or []
    except Exception:
        return
    on = {x["entity_id"] for x in states if x.get("state") == "on"}
    if any(e in on for e in open_lights(states)) and _follows():
        open_for_evening("outside lights already on")


def _morning_loop():
    while True:
        time.sleep(300)
        try:
            if 6 <= time.localtime().tm_hour < 16 and _flag():
                resume()
        except Exception:
            pass
        try:
            _catch_up()
        except Exception:
            pass


DISC_PORT = 4210            # each board broadcasts its own name here every 5 s (that's how Board A finds the train)


def heard(name: str, ip: str) -> bool:
    """A board said "I'm here" from `ip`: use that address from now on (new router, new address, no setup needed)."""
    kind = {"village-fx": "fx", "village-train": "train"}.get(str(name).strip())
    if not kind or not _private(ip):
        return False
    if _found.get(kind) != ip:
        _found[kind] = ip
        with _lock:
            _cache["at"] = 0.0
    return True


def _listen():
    """Hear the boards' announcements, so a board on a new address (router change, power cut) is found within seconds.
    Silently does nothing if the port can't be opened."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.bind(("", DISC_PORT))
    except OSError:
        return
    while True:
        try:
            data, (ip, _port) = s.recvfrom(256)
            heard(data.decode("utf-8", "replace"), ip)
        except Exception:
            time.sleep(1)


def start():
    threading.Thread(target=_morning_loop, daemon=True, name="village-morning").start()
    threading.Thread(target=_listen, daemon=True, name="village-listen").start()
