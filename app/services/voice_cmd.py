"""
Voice/text command interpreter for the wall screen.

Takes a spoken phrase (already transcribed by the browser) and decides what to do:
  - control smart-home devices  ("turn on the kitchen lights", "lock the front door")
  - run a scene                 ("movie time", "run good night")
  - arm the alarm               ("arm the alarm")   (disarm stays on the PIN pad)
  - answer quick questions       ("what's the weather", "what time is it")
  - add to a list                ("add milk to the groceries", "add call mom to my to-do")
  - anything else -> a short AI answer if ANTHROPIC_API_KEY is set, else a hint

Rule-based first so it works with NO AI key and in demo mode; the AI is only a
fallback for open-ended questions. Returns {ok, say, ...} — `say` is spoken aloud
by the browser.
"""
from __future__ import annotations
import os
import re
import datetime

from . import ha_svc
from ..db import get_db

ON_WORDS = {"on", "up", "start", "open", "unlock", "enable", "brighten", "resume"}
OFF_WORDS = {"off", "down", "stop", "close", "lock", "disable", "shut", "kill"}
_STOP = {"the", "a", "an", "to", "please", "my", "our", "turn", "switch", "set",
         "hey", "wall", "screen", "family", "hub", "can", "you", "could", "would",
         "in", "and", "all", "of", "is", "it", "that", "this"}


def _words(t: str):
    return set(re.findall(r"[a-z0-9]+", t.lower()))


def _tiles():
    home = ha_svc.get_home()
    if not home.get("connected"):
        return []
    return [tile for g in home.get("groups", []) for tile in g["tiles"]]


def _match(words, tiles, domains):
    """Best device whose name words overlap the phrase."""
    best, score = None, 0
    for t in tiles:
        if t["domain"] not in domains:
            continue
        nw = set(re.findall(r"[a-z0-9]+", t["name"].lower()))
        s = len(nw & words)
        if s > score:
            best, score = t, s
    return best if score > 0 else None


def _alarm_eid(tiles):
    for t in tiles:
        if t["domain"] == "alarm_control_panel":
            return t["entity_id"]
    return ""


def _add_to_list(text):
    """'add milk to the groceries' / 'add call mom to my to-do'. Returns say or None."""
    m = re.search(r"\badd\b(.*)", text.lower())
    if not m:
        return None
    body = m.group(1)
    todo = bool(re.search(r"to[\s-]?do|task|reminder|list of things", body))
    # strip trailing target phrase
    item = re.sub(r"\b(to|on)?\s*(my|the)?\s*(grocery|groceries|shopping|to[\s-]?do|todo|task[s]?|list)\b.*$", "", body).strip(" ,.")
    if not item:
        return None
    item = item[:120]
    try:
        with get_db() as conn:
            if todo:
                conn.execute("INSERT INTO todos (title) VALUES (?)", (item,))
                return f"Added {item} to your to-do list."
            conn.execute("INSERT INTO groceries (item) VALUES (?)", (item,))
            return f"Added {item} to the groceries."
    except Exception:
        return None


_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
              "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
              "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45, "sixty": 60, "ninety": 90,
              "half": 0.5, "a": 1, "an": 1}


def _timer_seconds(text: str) -> int:
    """'10 minutes', 'an hour and a half', 'ninety seconds', '1 hour 20 minutes' -> seconds."""
    t = text.lower().replace("-", " ")
    total = 0.0
    for m in re.finditer(r"(\d+(?:\.\d+)?|[a-z]+)(?:\s+and\s+a\s+(half))?\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b", t):
        n, half, unit = m.group(1), m.group(2), m.group(3)
        try:
            val = float(n)
        except ValueError:
            val = _NUM_WORDS.get(n)
            if val is None:
                continue
        if half:
            val += 0.5
        if unit.startswith("h"):
            total += val * 3600
        elif unit.startswith("m"):
            total += val * 60
        else:
            total += val
    return int(round(total))


_DUR_RE = r"(?:\d+(?:\.\d+)?|[a-z]+)(?:\s+and\s+a\s+half)?\s*(?:hours?|hrs?|minutes?|mins?|seconds?|secs?)\b"


def _timer_label(text: str):
    """'set a timer for pasta for 8 minutes' -> 'Pasta'. Strips the duration first
    so 'for an hour and a half' never becomes a label."""
    t = re.sub(r"(?:\d+\s+)*" + _DUR_RE, " ", text.lower().replace("-", " "))
    t = re.sub(r"\b(and|a|an)\s+(a\s+)?(half)?\b", " ", t)
    m = re.search(r"\bfor (?:the |my |our )?([a-z][a-z ]{1,30}?)\s*(?:timer|,|\bfor\b|$)", t)
    if not m:
        return None
    lbl = m.group(1).strip()
    if not lbl or lbl in ("me", "us", "it", "a", "an", "the") or lbl in _NUM_WORDS:
        return None
    return lbl.title()


def _say_duration(secs: int) -> str:
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h: parts.append(f"{h} hour{'s' if h != 1 else ''}")
    if m: parts.append(f"{m} minute{'s' if m != 1 else ''}")
    if s and not h: parts.append(f"{s} second{'s' if s != 1 else ''}")
    return " and ".join(parts) or "0 seconds"


def _ai_answer(text):
    """Open-ended Q&A, only if an API key is configured."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ("I can turn devices on or off, run scenes, arm the alarm, add to "
                "your lists, and tell you the time or weather.")
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model="claude-opus-4-8", max_tokens=160,
            system=("You are a friendly family hub on a kitchen wall screen. Answer in "
                    "one or two short spoken sentences. Today is "
                    + datetime.date.today().isoformat() + "."),
            messages=[{"role": "user", "content": text}],
        )
        return "".join(b.text for b in resp.content if b.type == "text").strip() or "I'm not sure."
    except Exception:
        return "I couldn't reach my brain for that one."


def interpret(text: str) -> dict:
    t = (text or "").strip()
    if not t:
        return {"ok": False, "say": "I didn't catch that."}
    w = _words(t)
    tiles = _tiles()

    # weather
    if "weather" in w or "raining" in w or ("outside" in w and ("temperature" in w or "degrees" in w)):
        try:
            from . import weather_svc
            wx = weather_svc.get_weather()
            if wx.get("temp") is not None:
                desc = (wx.get("desc") or "clear").lower()
                return {"ok": True, "say": f"It's {wx['temp']} degrees and {desc}, with a high of {wx.get('high','?')}."}
        except Exception:
            pass
        return {"ok": True, "say": "I couldn't get the weather right now."}

    # kitchen timer: "set a timer for 10 minutes", "5 minute timer", "cancel the timer"
    if "timer" in w or "timers" in w:
        if w & {"cancel", "stop", "clear", "kill"}:
            return {"ok": True, "say": "Timer cancelled.", "timer": {"cancel": True}}
        secs = _timer_seconds(t)
        if secs:
            label = _timer_label(t)
            return {"ok": True, "say": f"Timer set for {_say_duration(secs)}" + (f" for {label}" if label else "") + ".",
                    "timer": {"seconds": secs, "label": label}}
        return {"ok": False, "say": "How long? Say something like: set a timer for ten minutes."}

    # time
    if ("time" in w and ("what" in w or "whats" in w)) or "clock" in w:
        return {"ok": True, "say": "It's " + datetime.datetime.now().strftime("%I:%M %p").lstrip("0") + "."}

    # alarm (arm by voice; disarm stays behind the PIN pad)
    if "disarm" in w or ("off" in w and "alarm" in w):
        return {"ok": False, "say": "For safety, please disarm at the screen with your PIN.", "focus": "alarm"}
    if "arm" in w and "alarm" in w:
        eid = _alarm_eid(tiles)
        if eid:
            svc = "alarm_arm_home" if ("home" in w or "stay" in w) else "alarm_arm_away"
            ha_svc.call_service("alarm_control_panel", svc, eid)
            return {"ok": True, "say": "Arming the alarm.", "refresh": True}

    # scene by name ("movie time", "run good night")
    scene = _match(w, tiles, {"scene", "script"})
    wants_scene = scene and (("run" in w or "activate" in w or "start" in w or "scene" in w)
                             or not (w & ON_WORDS or w & OFF_WORDS))
    if scene and wants_scene:
        ha_svc.toggle(scene["entity_id"])
        return {"ok": True, "say": f"Running {scene['name']}.", "refresh": True}

    # on/off device control
    on, off = bool(w & ON_WORDS), bool(w & OFF_WORDS)
    if on or off:
        dev = _match(w, tiles, {"light", "switch", "fan", "cover", "lock", "media_player"})
        if dev:
            dom = dev["domain"]
            if dom in ("light", "switch", "fan", "media_player"):
                ha_svc.call_service(dom, "turn_on" if on else "turn_off", dev["entity_id"])
                verb = "Turning on" if on else "Turning off"
            elif dom == "cover":
                ha_svc.call_service("cover", "open_cover" if on else "close_cover", dev["entity_id"])
                verb = "Opening" if on else "Closing"
            else:  # lock
                ha_svc.call_service("lock", "unlock" if on else "lock", dev["entity_id"])
                verb = "Unlocking" if on else "Locking"
            return {"ok": True, "say": f"{verb} {dev['name']}.", "refresh": True}

    # add to a list
    if "add" in w:
        said = _add_to_list(t)
        if said:
            return {"ok": True, "say": said, "refresh": True}

    # fallback: AI answer (or capability hint)
    return {"ok": True, "say": _ai_answer(t)}
