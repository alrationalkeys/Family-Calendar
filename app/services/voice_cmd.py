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


def _music(text: str, w: set):
    """Spotify through HA. Returns what to say, or None if it isn't a music command."""
    sp = ha_svc.spotify_state()
    if not sp:
        return "Spotify isn't connected to Home Assistant yet."
    tl = text.lower()
    if w & {"pause", "stop"}:
        if sp["state"] == "playing":
            ha_svc.spotify_cmd("play_pause")
        return "Pausing the music."
    if w & {"next", "skip"}:
        ha_svc.spotify_cmd("next"); return "Skipping."
    if w & {"previous", "back", "last"} and w & {"song", "track"}:
        ha_svc.spotify_cmd("prev"); return "Going back a track."
    if w & {"up", "louder", "louder"} and not ("play" in w):
        ha_svc.spotify_cmd("volume", str(min(1.0, (sp.get("volume") or 0.5) + 0.15))); return "Turning it up."
    if w & {"down", "quieter", "lower", "softer"} and not ("play" in w):
        ha_svc.spotify_cmd("volume", str(max(0.0, (sp.get("volume") or 0.5) - 0.15))); return "Turning it down."
    # pick a Spotify Connect device if one is named ("... in the kitchen", "... on the living room tv")
    device, best = None, 0
    for src in sp.get("sources") or []:
        sw = set(re.findall(r"[a-z0-9]+", src.lower())) - {"the", "tv", "speaker", "wall", "s"}
        n = len(sw & w)
        if n > best:
            device, best = src, n
    # pinned playlist by name
    try:
        from ..routers.settings import get_settings
        pls = get_settings().get("spotifyPlaylists") or []
    except Exception:
        pls = []
    chosen = None
    for pl in pls:
        pw = set(re.findall(r"[a-z0-9]+", str(pl.get("name", "")).lower())) - {"the", "playlist", "my"}
        if pw and pw <= w:
            chosen = pl
    if "play" in w or "resume" in w or "start" in w:
        if device:
            ha_svc.spotify_cmd("source", device)
        if chosen and chosen.get("uri"):
            ha_svc.spotify_cmd("play", chosen["uri"])
            return f"Playing {chosen['name']}" + (f" in the {device}" if device else "") + "."
        if sp["state"] != "playing":
            ha_svc.spotify_cmd("play_pause")
        if chosen is None and (w & {"playlist"} or re.search(r"\bplay (?!the music|music|some music|it)", tl)):
            names = ", ".join(p.get("name", "") for p in pls[:4])
            return "Resuming. " + (f"Your pinned playlists are {names}." if names else "Pin playlists in the phone app to play them by name.")
        return "Playing" + (f" in the {device}" if device else "") + "."
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


def _family_context() -> str:
    """What the assistant should know about THIS family today, so questions like
    'when is Ella's dentist', 'what's for dinner', 'what chores are left' and
    'how many days until Disney' get real answers. Cheap: a few small queries."""
    lines = []
    today = datetime.date.today()
    try:
        from ..routers.calendar import events as cal_events
        evs = cal_events(days=7, back=0).get("events", [])
        upcoming = []
        for e in evs:
            st = e.get("start") or ""
            if not st or str(e.get("title", "")).startswith("[sync error"):
                continue
            who = ""
            upcoming.append(f"- {st[:16].replace('T', ' ')} {e.get('title')}{who}")
            if len(upcoming) >= 20:
                break
        if upcoming:
            lines.append("Calendar, next 7 days:\n" + "\n".join(upcoming))
    except Exception:
        pass
    try:
        with get_db() as conn:
            meals = [f"{r['date']} {r['slot']}: {r['title']}" for r in conn.execute(
                "SELECT date, slot, title FROM meals WHERE date>=? ORDER BY date, slot LIMIT 10", (today.isoformat(),))]
            chores = [f"{r['title']}" + (f" ({r['name']})" if r['name'] else "") for r in conn.execute(
                "SELECT c.title, p.name FROM chores c LEFT JOIN people p ON p.id=c.person_id "
                "WHERE c.done=0 AND (c.due_date IS NULL OR c.due_date<=?) LIMIT 12", (today.isoformat(),))]
            todos = [r["title"] for r in conn.execute("SELECT title FROM todos WHERE done=0 LIMIT 10")]
            groc = [r["item"] for r in conn.execute("SELECT item FROM groceries WHERE got=0 LIMIT 15")]
            people = [r["name"] for r in conn.execute("SELECT name FROM people")]
            cds = []
            for r in conn.execute("SELECT title, date FROM countdowns ORDER BY date LIMIT 6"):
                try:
                    cds.append(f"{r['title']}: {(datetime.date.fromisoformat(r['date']) - today).days} days")
                except ValueError:
                    pass
        if people: lines.append("Family members: " + ", ".join(people))
        if meals: lines.append("Meal plan: " + "; ".join(meals))
        if chores: lines.append("Chores still to do today: " + "; ".join(chores))
        if todos: lines.append("To-do list: " + "; ".join(todos))
        if groc: lines.append("Grocery list: " + ", ".join(groc))
        if cds: lines.append("Countdowns: " + "; ".join(cds))
    except Exception:
        pass
    try:
        from . import weather_svc
        wx = weather_svc.get_weather()
        if wx.get("temp") is not None:
            lines.append(f"Weather now: {wx['temp']}°F, {wx.get('desc', '')}, high {wx.get('high', '?')}, low {wx.get('low', '?')}")
    except Exception:
        pass
    return "\n".join(lines)


# Where the wall lives — steers "is Target open", local news, weather-adjacent lookups.
_HOME_LOCATION = {"type": "approximate", "city": os.environ.get("FAMILYHUB_CITY", "Myrtle Beach"),
                  "region": os.environ.get("FAMILYHUB_REGION", "South Carolina"),
                  "country": "US", "timezone": os.environ.get("FAMILYHUB_TZ", "America/New_York")}


def _assistant_name() -> str:
    try:
        from ..routers.settings import get_settings
        return (get_settings().get("assistantName") or "Hub").strip()[:30] or "Hub"
    except Exception:
        return "Hub"


def _web_enabled() -> bool:
    return os.environ.get("FAMILYHUB_VOICE_WEB", "1").lower() not in ("0", "false", "no", "off")


def _ai_answer(text):
    """Open-ended Q&A, only if an API key is configured. The model gets today's
    family context (calendar, meals, chores, lists, weather) so it answers like
    a household assistant, and can search the web for live facts (news, scores,
    store hours, prices) — Anthropic's server-side web search, no extra key."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ("I can turn devices on or off, run scenes, arm the alarm, set timers, play music, add to "
                "your lists, and tell you the time or weather. Add an Anthropic key for everything else.")
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], timeout=40.0, max_retries=1)
        now = datetime.datetime.now()
        web = _web_enabled()
        system = (
            f"You are {_assistant_name()}, the voice of a family's kitchen wall display. Everyone in the house — "
            "including young kids — talks to you. Answer in one to three short, natural SPOKEN sentences: "
            "no lists, no markdown, no emoji, no links, no preamble, and never read out URLs or source names. "
            "Be warm, plain and practical. For cooking, math, homework, definitions, conversions and general "
            "knowledge, just answer from what you know. If asked about the family's schedule, meals, chores "
            "or lists, use the context below and be specific; if it isn't there, say you don't see it. "
            + ("You have a web search tool: use it ONLY when the question needs current information — news, "
               "sports scores and schedules, store or restaurant hours, prices, traffic, whether something is "
               "open, who won, what happened today. Search at most twice, then answer in plain spoken words. "
               if web else
               "You cannot browse the internet, so for live news, scores or store hours say you can't check that right now. ")
            + "Keep kid-facing answers age-appropriate.\n\n"
            f"Now: {now.strftime('%A %B %d %Y, %I:%M %p').replace(' 0', ' ')}. The family lives near "
            f"{_HOME_LOCATION['city']}, {_HOME_LOCATION['region']}.\n\n" + _family_context()
        )
        kwargs = dict(model="claude-opus-4-8", max_tokens=400, system=system,
                      messages=[{"role": "user", "content": text}])
        if web:
            kwargs["tools"] = [{"type": "web_search_20260209", "name": "web_search",
                                "max_uses": 2, "user_location": _HOME_LOCATION}]
        resp = client.messages.create(**kwargs)
        # a search turn can pause; let it finish (bounded)
        for _ in range(2):
            if resp.stop_reason != "pause_turn":
                break
            kwargs["messages"] = kwargs["messages"] + [{"role": "assistant", "content": resp.content},
                                                       {"role": "user", "content": "Continue."}]
            resp = client.messages.create(**kwargs)
        # the spoken answer is the text AFTER any searching (earlier text blocks are "let me look that up")
        texts = [b.text for b in resp.content if b.type == "text" and b.text.strip()]
        answer = (texts[-1] if texts else "").strip()
        answer = re.sub(r"https?://\S+", "", answer).strip()
        return answer or "I'm not sure."
    except Exception:
        return "I couldn't reach my brain for that one."


def interpret(text: str) -> dict:
    t = (text or "").strip()
    name = _assistant_name().lower()
    t = re.sub(r"^(?:hey|ok|okay|hi|yo)?\s*(?:" + re.escape(name) + r"|wall|screen)\s*[,!.]?\s*", "", t, flags=re.I).strip() or t
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

    # music / Spotify: "play my dinner playlist in the kitchen", "pause the music",
    # "next song", "turn the music up"
    if w & {"music", "song", "spotify", "playlist", "songs", "track"} or (
            "play" in w and not _match(w, tiles, {"scene", "script"})):
        said = _music(t, w)
        if said:
            return {"ok": True, "say": said, "refresh": True}

    # "what's for dinner / lunch tonight?" — no key needed
    if w & {"dinner", "lunch", "breakfast", "supper"} and w & {"what", "whats", "tonight", "today"} and not (w & ON_WORDS | w & OFF_WORDS):
        slot = "breakfast" if "breakfast" in w else "lunch" if "lunch" in w else "dinner"
        with get_db() as conn:
            r = conn.execute("SELECT title FROM meals WHERE date=? AND slot=?",
                             (datetime.date.today().isoformat(), slot)).fetchone()
        return {"ok": True, "say": f"{slot.capitalize()} today is {r['title']}." if r else f"Nothing's planned for {slot} yet."}

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
