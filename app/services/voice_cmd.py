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

from . import ha_svc, voice_more, voice_agent
from ..db import get_db

FHSTATE = {"open": "open", "closed": "closed", "opening": "opening", "closing": "closing", "locked": "locked",
           "unlocked": "unlocked", "on": "on", "off": "off", "unavailable": "not responding"}
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


# little words never count as a match ("add a chore…" once ran "Outdoor lights - turn a list on or off")
_STOP = {"a", "an", "the", "to", "for", "of", "on", "in", "at", "and", "or", "my", "our", "is", "it", "be", "with",
         "please", "can", "you", "i", "me", "we", "us", "this", "that", "turn", "set", "every", "each", "s"}


_GENERIC = {"light", "lights", "lamp", "lamps", "switch", "plug", "outlet", "tv", "fan", "door", "smart"}


def _sing(x: str) -> str:
    """doors -> door, lights -> light (both sides of a match), but not 'glass' or 'christmas'."""
    return x[:-1] if len(x) > 3 and x.endswith("s") and not x.endswith(("ss", "mas")) else x


def _match(words, tiles, domains):
    """Best device whose name words overlap the phrase (meaningful words only). Scenes/scripts need at least
    half of their name's words; FamilyHub's own helper scripts (script.fh_*) are never voice targets."""
    best, score, generic_hits = None, 0, 0
    want = {_sing(x) for x in words} - _STOP
    for t in tiles:
        if t["domain"] not in domains:
            continue
        if t["domain"] == "script" and t["entity_id"].startswith("script.fh_"):
            continue
        nw = {_sing(x) for x in re.findall(r"[a-z0-9]+", t["name"].lower())} - _STOP
        hit = nw & want
        # "porch" says more than "light": generic words count half, and a closer name wins a tie
        s = sum(0.5 if x in _GENERIC else 1 for x in hit)
        if t["domain"] in ("scene", "script") and nw and len(hit) * 2 < len(nw):
            continue
        if s and not (hit - _GENERIC):
            generic_hits += 1
        if s:
            s += len(hit) / (len(nw) * 10 or 1)
        if s > score:
            best, score = t, s
    # only "light"/"tv" in common: fine if there's just one, otherwise it's a guess ("the lights" -> which?)
    if best is not None and score < 1 and generic_hits > 1:
        return None
    return best if score > 0 else None


def _alarm_eid(tiles):
    for t in tiles:
        if t["domain"] == "alarm_control_panel":
            return t["entity_id"]
    return ""


def _spoken_when(start: str, all_day: bool) -> str:
    try:
        d = datetime.datetime.fromisoformat(start.replace("Z", "+00:00"))
        day = d.strftime("%A %B %-d")
        return day if all_day else f"{day} at {d.strftime('%-I:%M %p').lstrip('0')}"
    except Exception:
        return start


def _smart_add(text: str):
    """'add <anything>' with no list named -> classify like the phone's quick-add and save
    to the right place (calendar / to-do / groceries / meals). Returns what to say, or None."""
    from . import ai_route
    from .people import extract_person
    try:
        parsed = ai_route.route_text(text)
    except Exception:
        return None
    kind, items = parsed.get("kind"), parsed.get("items") or []
    if not items:
        return None
    said = []
    try:
        with get_db() as conn:
            pid, pname, _ = extract_person(conn, text)
            for it in items:
                if kind == "event":
                    conn.execute("INSERT INTO local_events (title,start,end,all_day,person_id) VALUES (?,?,?,?,?)",
                                 (it["title"], it["start"], it.get("end"), 1 if it.get("all_day") else 0, pid))
                    said.append(f"{it['title']} on {_spoken_when(it['start'], it.get('all_day'))}")
                elif kind == "todo":
                    _, _, title = extract_person(conn, it["title"])
                    conn.execute("INSERT INTO todos (title, person_id) VALUES (?,?)", (title or it["title"], pid))
                    said.append(title or it["title"])
                elif kind == "grocery":
                    conn.execute("INSERT INTO groceries (item, qty) VALUES (?,?)", (it["item"], it.get("qty")))
                    said.append(it["item"])
                elif kind == "meal":
                    conn.execute("INSERT INTO meals (date, slot, title) VALUES (?,?,?)", (it["date"], it["slot"], it["title"]))
                    said.append(f"{it['title']} for {it['slot']} on {_spoken_when(it['date'], True)}")
                else:
                    return None
    except Exception:
        return None
    joined = ", ".join(said)
    if kind == "event":
        return f"Added {joined} to the calendar" + (f" for {pname}." if pname else ".")
    if kind == "todo":
        return f"Added {joined} to {pname}'s to-do list." if pname else f"Added {joined} to your to-do list."
    if kind == "grocery":
        return f"Added {joined} to the groceries."
    return f"Planned {joined}."


_WDAYS = {"monday": "MO", "tuesday": "TU", "wednesday": "WE", "thursday": "TH", "friday": "FR", "saturday": "SA", "sunday": "SU"}
_WDNUM = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _parse_schedule(low: str, today: datetime.date):
    """Spoken schedule -> (recurrence, first due date or None, words to say). Understands every day / weekdays /
    weekends / every <day(s)> / every week|month / on <day> / today / tomorrow / next week."""
    days = [code for word, code in _WDAYS.items() if re.search(rf"\b{word}s?\b", low)]
    rec, due, when = None, None, ""
    if re.search(r"\b(every ?day|daily|each day|every night|nightly)\b", low):
        rec, due, when = "daily", today, "every day"
    elif re.search(r"\bweekdays?\b", low) and not days:
        days, rec = ["MO", "TU", "WE", "TH", "FR"], "weekly:MO,TU,WE,TH,FR"
    elif re.search(r"\bweekends?\b", low) and not days:
        days, rec = ["SA", "SU"], "weekly:SA,SU"
    elif days and re.search(r"\b(every|each|repeat|repeating|recurring|weekly|mondays|tuesdays|wednesdays|thursdays|fridays|saturdays|sundays)\b", low):
        rec = "weekly" if len(days) == 1 else "weekly:" + ",".join(days)
    elif re.search(r"\b(every week|weekly|each week)\b", low):
        rec, due, when = "weekly", today, "every week"
    elif re.search(r"\b(every month|monthly|each month)\b", low):
        rec, due, when = "monthly", today, "every month"
    if days:                                                   # first due date: the next of those days (today counts)
        due = min(today + datetime.timedelta(days=(_WDNUM[d] - today.weekday()) % 7) for d in days)
        names = [w.capitalize() for w, c in _WDAYS.items() if c in days]
        when = ("every " + (" and ".join(names) if len(names) < 3 else ", ".join(names[:-1]) + " and " + names[-1])) if rec else "on " + names[0]
        if rec == "weekly:MO,TU,WE,TH,FR":
            when = "every weekday"
        elif rec == "weekly:SA,SU":
            when = "every weekend day"
    elif not rec and re.search(r"\btomorrow\b", low):
        due, when = today + datetime.timedelta(days=1), "tomorrow"
    elif not rec and re.search(r"\btoday|tonight\b", low):
        due, when = today, "today"
    elif not rec and re.search(r"\bnext week\b", low):
        due, when = today + datetime.timedelta(days=7 - today.weekday()), "next week"
    return rec, due, when


# schedule words, list words and fillers that come out of a spoken title
_SCHED_RE = (r"\b(?:every|each|on|by|this|next)\s+(?:other\s+)?(?:(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?(?:\s*(?:,|and)\s*)?)+"
             r"|\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s\b"
             r"|\b(?:every ?day|daily|each day|every night|nightly|every week|weekly|each week|every month|monthly|each month|"
             r"on weekdays|weekdays|on weekends|weekends|today|tonight|tomorrow|next week|repeating|recurring|repeat(?:s|ing)?(?: weekly)?)\b")


def _when_say(rec, due, when, today):
    if not due:
        return ""
    first = "today" if due == today else ("tomorrow" if due == today + datetime.timedelta(days=1) else due.strftime("%A %B %-d"))
    return f", {when}, starting {first}" if rec else f", {first}"


def _add_chore(text: str):
    """'add a chore for Alex to bring in the garbage cans every Thursday' -> a chore for Alex, weekly on
    Thursdays, first due this Thursday. Also 'for 3 stars'. Returns what to say."""
    from .people import extract_person
    low = text.lower()
    today = datetime.date.today()
    rec, due, when = _parse_schedule(low, today)
    due = due or today
    m = re.search(r"\b(?:for|worth)\s+(\d|one|two|three|four|five)\s+stars?\b", low)
    stars = 0
    if m:
        stars = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}.get(m.group(1), None) or int(m.group(1))
    title = re.sub(r"^.*?\b(?:add|put|create|make)\b", "", text, flags=re.I)
    title = re.sub(r"\b(?:to|on|onto)\s+(?:the|my|our)\s+chores?\s*(?:list|chart)?\b", " ", title, flags=re.I)
    title = re.sub(r"\b(?:a|an|new)?\s*chores?\b\s*(?:list|chart)?", " ", title, flags=re.I)
    title = re.sub(r"\b(?:for|worth)\s+(?:\d|one|two|three|four|five)\s+stars?\b", " ", title, flags=re.I)
    title = re.sub(_SCHED_RE, " ", title, flags=re.I)
    try:
        with get_db() as conn:
            pid, pname, title = extract_person(conn, title)
            title = _tidy_title(title)
            if not title:
                return None
            conn.execute("INSERT INTO chores (title, person_id, due_date, recurrence, stars) VALUES (?,?,?,?,?)",
                         (title, pid, due.isoformat(), rec, stars))
    except Exception:
        return None
    s = f"Added the chore {title}" + (f" for {pname}" if pname else "")
    s += _when_say(rec, due, when, today) if (rec or due != today) else ""
    return s + (f", worth {stars} star" + ("s" if stars != 1 else "") if stars else "") + "."


def _tidy_title(title: str) -> str:
    title = re.sub(r"\s{2,}", " ", title or "").strip(" ,.:;-")
    for _ in range(3):   # leftover glue words at the front: "to finish…", "something to…", "that…"
        title = re.sub(r"^(?:to|that|which|a|an|the thing|a thing|something|an item|item|please|and)\b\s*", "", title, flags=re.I).strip(" ,.:;-")
    return (title[0].upper() + title[1:120]) if title else ""


def _add_todo(text: str):
    """Any to-do sentence, in any order: 'add to the to-do list for Alex to finish the Christmas village',
    'add a to-do for Rachell to call the vet tomorrow', 'remind Alex to take out the trash every Tuesday',
    'Rachell needs to book the dentist', 'put finish the village on Alex's to-do list'. Keeps capitals."""
    from .people import extract_person
    low = text.lower()
    today = datetime.date.today()
    rec, due, when = _parse_schedule(low, today)
    title = re.sub(r"^\s*(?:please\s+)?(?:can you\s+)?(?:add|put|create|make)\b", "", text, flags=re.I)
    # the list itself, wherever it's said: "to the to-do list", "on Alex's to do", "a to-do", "my task list", "a reminder"
    title = re.sub(r"\b(?:to|on|onto|in|into)?\s*(?:the|my|our|a|an|\w+'s)?\s*(?:to[\s-]?do|todo|task|reminder)s?(?:\s+list)?\b", " ", title, flags=re.I)
    title = re.sub(r"\b(?:to|on|onto|in|into)\s+(?:the|my|our|\w+'s)\s+list\b", " ", title, flags=re.I)
    title = re.sub(_SCHED_RE, " ", title, flags=re.I)
    try:
        with get_db() as conn:
            pid, pname, title = extract_person(conn, title)
            if not pid:                                 # "Alex's" was taken out with the list words: look again
                pid, pname, _ = extract_person(conn, text)
            title = re.sub(r"^(?:remind|tell)\b\s*(?:me|us)?\s*(?:to\b)?", "", title, flags=re.I)
            title = re.sub(r"\b(?:needs?|has|have)\s+to\b", " ", title, flags=re.I)
            title = _tidy_title(title)
            if not title:
                return None
            conn.execute("INSERT INTO todos (title, person_id, due_date, recurrence) VALUES (?,?,?,?)",
                         (title, pid, due.isoformat() if due else None, rec))
    except Exception:
        return None
    s = f"Added {title} to {pname}'s to-do list" if pname else f"Added {title} to the to-do list"
    return s + _when_say(rec, due, when, today) + "."


def _add_to_list(text):
    """'add milk to the groceries' / 'add call mom to my to-do' /
    'remind Rachell to book the dentist' / 'Ella needs to pack her bag' /
    'add take out trash for Alex to the to-do list'. Returns say or None."""
    from .people import extract_person
    low = text.lower()
    m = re.search(r"\badd\b(.*)", low)
    # "remind <name> to ..." / "<name> needs to ..." are to-dos even without "add"
    assign_only = re.search(r"\b(remind\s+\w+\s+to|\w+\s+(needs?|has|have)\s+to)\b", low)
    if assign_only and not m and not low.startswith("remind"):
        from .people import extract_person as _xp
        try:
            with get_db() as _c:
                if not _xp(_c, text)[0]:          # "I have to go" isn't a to-do; "Rachell needs to…" is
                    return None
        except Exception:
            return None
    if not m and not assign_only:
        return None
    body = m.group(1) if m else low
    if re.search(r"\b(?:chores?|shores?|chords?)\b", body):
        text = re.sub(r"\b(?:shore|chord)(s?)\b", r"chore\1", text, flags=re.I)
        return _add_chore(text) or "What's the chore? Say something like: add a chore for Alex to take out the trash every Thursday."
    todo = bool(re.search(r"to[\s-]?do|task|reminder|list of things|remind|needs? to|has to|have to", body)) or bool(assign_only and not m)
    if todo:
        said = _add_todo(text)
        if said:
            return said
    explicit_list = todo or bool(re.search(r"grocer|shopping|list", body))
    # No list named ("add nanner landing the Sunday before Thanksgiving"): let the same
    # classifier the phone's quick-add uses decide event / to-do / grocery / meal.
    if m and not explicit_list and os.getenv("ANTHROPIC_API_KEY"):
        said = _smart_add(text)
        if said:
            return said
    # a date or a time ("add dentist Thursday at 3") -> the calendar, no AI key needed
    if m and not explicit_list and voice_more.looks_like_event(body):
        said = voice_more.add_event(text)
        if said:
            return said
    # strip trailing target phrase
    item = re.sub(r"\b(to|on)?\s*(my|the|our)?\s*(grocery|groceries|shopping|to[\s-]?do|todo|task[s]?|list)\b.*$", "", body).strip(" ,.")
    if not item:     # "add groceries eggs" / "add to the shopping list: eggs"
        item = re.sub(r"^\s*(?:to|on)?\s*(?:my|the|our)?\s*(?:grocery|groceries|shopping)\s*(?:list)?\b", "", body).strip(" ,.:")
    if not item:
        return None
    try:
        with get_db() as conn:
            pid, pname, item = extract_person(conn, item) if todo else (None, None, item)
            item = item.strip(" ,.")[:120]
            if not item:
                return None
            if todo:
                conn.execute("INSERT INTO todos (title, person_id) VALUES (?,?)", (item, pid))
                return f"Added {item} to {pname}'s to-do list." if pname else f"Added {item} to your to-do list."
            conn.execute("INSERT INTO groceries (item) VALUES (?)", (item,))
            return f"Added {item} to the groceries."
    except Exception:
        return None


def _music(text: str, w: set):
    """Spotify. Prefers FamilyHub's own Spotify link (search anything, play on the wall's
    own player); falls back to Home Assistant's Spotify player. Returns what to say, or
    None if it isn't a music command."""
    from . import spotify_web
    if spotify_web.linked():
        said = spotify_web.voice(text, w)
        if said:
            return said
    sp = ha_svc.spotify_state()
    if not sp:
        return ("Spotify isn't connected yet. Link it from the phone app, Settings, Spotify."
                if spotify_web.configured() else "Spotify isn't connected to Home Assistant yet.")
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
    for m in re.finditer(r"(\d+(?:\.\d+)?|[a-z]+)(?:\s+and\s+a\s+(half))?\s*(hours?|hrs?|minutes?|mins?|seconds?|secs?)\b(?:\s+and\s+a\s+(half))?", t):
        n, half, unit = m.group(1), m.group(2) or m.group(4), m.group(3)
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


_DUR_RE = r"(?:\d+(?:\.\d+)?|[a-z]+)(?:\s+and\s+a\s+half)?\s*(?:hours?|hrs?|minutes?|mins?|seconds?|secs?)\b(?:\s+and\s+a\s+half)?"


def _timer_label(text: str):
    """'set a timer for pasta for 8 minutes' -> 'Pasta'. Strips the duration first
    so 'for an hour and a half' never becomes a label."""
    t = re.sub(r"(?:\d+\s+)*" + _DUR_RE, " ", text.lower().replace("-", " "))
    t = re.sub(r"\b(and|a|an)\s+(a\s+)?(half)?\b", " ", t)
    m = re.search(r"\bfor (?:the |my |our )?([a-z][a-z ]{1,30}?)\s*(?:timer|,|\bfor\b|$)", t)
    if not m:       # "set a pasta timer for 9 minutes"
        m = re.search(r"\b(?:a|the|my)\s+([a-z]+(?: [a-z]+)?)\s+timer\b", text.lower())
        if m and set(m.group(1).split()) & (set(_NUM_WORDS) | {"minute", "minutes", "hour", "second", "kitchen", "new"}):
            m = None
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
        return ("Sorry, I didn't get that. Try: add milk, add dentist Friday at 3, what's on the grocery list, "
                "turn on the porch light, or set a timer for 10 minutes.")
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
        from .ai_model import model as _model
        kwargs = dict(model=_model(), max_tokens=400, system=system,
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
    """Run one spoken command and remember it in the voice history (Settings > Advanced > Voice history)."""
    try:
        r = _interpret(text)
    except Exception as e:                      # never leave the wall hanging on a bug
        import traceback
        traceback.print_exc()
        r = {"ok": False, "say": "Sorry, something went wrong with that one.", "error": repr(e)}
    log_voice(text, r.get("say") or ("(spoke the briefing)" if r.get("briefing") else ""))
    return r


def log_voice(heard: str, reply: str, kind: str = "command"):
    """Last 60 things the wall heard and what it did, newest first."""
    import json
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='voice_log'").fetchone()
            log = json.loads(row["value"]) if row else []
            log.insert(0, {"at": datetime.datetime.now().isoformat(timespec="seconds"), "heard": (heard or "")[:300],
                           "reply": (reply or "")[:400], "kind": kind})
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('voice_log', ?)", (json.dumps(log[:60]),))
    except Exception:
        pass


def voice_log() -> list:
    import json
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='voice_log'").fetchone()
            return json.loads(row["value"]) if row else []
    except Exception:
        return []


def stt_prompt() -> str:
    """Words Whisper should expect on this wall: the family's names, the devices, the list words.
    (Whisper's initial_prompt nudges spelling toward these, e.g. 'Rachell' not 'Rachel', 'chore' not 'shore'.)"""
    names = []
    try:
        with get_db() as conn:
            names = [r["name"].split(" ")[0] for r in conn.execute("SELECT name FROM people") if r["name"]]
    except Exception:
        pass
    devs = []
    try:
        devs = [x["name"] for x in _tiles() if x["domain"] in ("light", "switch", "cover", "lock", "scene", "climate")
                and not x["entity_id"].startswith("script.fh_")][:25]
    except Exception:
        pass
    words = [_assistant_name()] + names + ["chore", "chores", "to-do list", "groceries", "calendar", "thermostat",
                                           "upstairs", "downstairs", "garage"] + devs
    return ("Glossary: " + ", ".join(dict.fromkeys(words)) + ".")[:600]


def _village_cmd(low: str):
    """Spoken village request -> village.COMMANDS key, or None."""
    if re.search(r"\btrain\b", low):
        if re.search(r"\b(stop|halt|park|enough)\b", low):
            return "stop"
        if re.search(r"\b(start|run|go|send|choo|all aboard|lap|ride)\b", low):
            return "train"
    if re.search(r"\btree show\b|\bshow\b.*\btree\b", low):
        return "tree"
    if re.search(r"\brach(?:el+|al+)'?s?\s+(?:village\s+|special\s+)?show\b", low):
        return "rachell"
    if re.search(r"\bcarol+ers?\b|\bcarolling\b", low):
        return "carol"
    if re.search(r"\bvillage\b", low):
        if re.search(r"\b(sleep|bed|night|off|quiet)\b", low):
            return "sleep"
        if re.search(r"\b(wake|up|on|start)\b", low):
            return "wake"
    return None


def _interpret(text: str, use_ai: bool = True) -> dict:
    """Instant rules for the obvious commands; with an Anthropic key everything else (lists, calendar,
    check-offs, thermostats, questions) goes to voice_agent, which understands loose phrasing and acts with tools.
    Without a key, or if the AI can't be reached, the rule-based helpers below do their best."""
    ai = use_ai and voice_agent.enabled()
    t = (text or "").strip()
    name = _assistant_name().lower()
    t = re.sub(r"^(?:hey|ok|okay|hi|yo)?\s*(?:" + re.escape(name) + r"|family\s*hub|hub|wall|screen)\s*[,!.]?\s*", "", t, flags=re.I).strip() or t
    if not t:
        return {"ok": False, "say": "I didn't catch that."}
    w = _words(t)
    tiles = _tiles()

    # "add …" / "remind …" / "create a chore …" are always about the lists, never a device or scene
    t = re.sub(r"^new\s+(chore|to[\s-]?do|task|reminder|event|appointment)\b[,:]?\s*", r"add a \1 ", t, flags=re.I)
    if not ai and re.match(r"^(?:please\s+)?(?:can you\s+|could you\s+)?(?:add|remind|create|put|schedule|book|make an? (?:chore|to[\s-]?do|event|appointment))\b", t, flags=re.I):
        said = _add_to_list(re.sub(r"^(?:please\s+)?(?:can you\s+|could you\s+)?(?:create|make|put|schedule|book)\b", "add", t, flags=re.I))
        if said:
            return {"ok": True, "say": said, "refresh": True}

    # "I need to call the plumber" / "we have to renew the tags" -> to-do (buy/get/pick up -> groceries, below)
    mn = None if ai else re.match(r"^(?:we|i)\s+(?:really\s+)?(?:need|have|gotta|got)\s+to\s+(?!buy\b|get\b|grab\b|pick up\b)(\w+(?:\s+\S+)+)$", t.strip(" .!"), flags=re.I)
    if mn:
        said = _add_todo("add to the to-do list " + mn.group(1))
        if said:
            return {"ok": True, "say": said, "refresh": True}
    # "we need paper towels", "we're out of coffee"
    said = None if ai else voice_more.grocery_phrase(t)
    if said:
        return {"ok": True, "say": said, "refresh": True}
    # "check off milk", "mark take out the trash as done", "remove eggs from the grocery list"
    said = None if ai else voice_more.complete(t)
    if said:
        return {"ok": True, "say": said, "refresh": True}
    # "what's on the grocery list", "what chores does Alex have"
    said = None if ai else voice_more.list_query(t)
    if said:
        return {"ok": True, "say": said}

    # weather
    if (w & {"weather", "forecast", "raining", "umbrella", "jacket", "sunny"} or ("rain" in w and not w & {"gutter", "gutters"})
            or ("outside" in w and w & {"temperature", "degrees", "hot", "cold", "warm", "chilly"})):
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

    # the Christmas village: "start the train", "stop the train", "Rachell's show", "tree show",
    # "carolers", "put the village to sleep", "wake up the village"
    vg = _village_cmd(t.lower())
    if vg:
        from . import village
        r = village.command(vg)
        done = {"train": "All aboard!", "stop": "Stopping the train.", "tree": "Starting the tree show.",
                "rachell": "Starting Rachell's show.", "carol": "Here come the carolers.",
                "sleep": "Putting the village to sleep.", "wake": "Waking up the village."}[vg]
        return {"ok": bool(r.get("ok")), "say": done if r.get("ok") else "The village isn't answering right now."}

    # music / Spotify: "play my dinner playlist in the kitchen", "pause the music",
    # "next song", "turn the music up"
    if w & {"music", "song", "spotify", "playlist", "songs", "track"} or (
            "play" in w and not _match(w, tiles, {"scene", "script"})):
        said = _music(t, w)
        if said:
            return {"ok": True, "say": said, "refresh": True}

    # "what's today / give me the rundown / morning briefing" -> the wall speaks the digest
    if w & {"tomorrow", "tomorrows"} and (w & {"what", "whats", "schedule", "plan", "happening", "briefing", "rundown", "agenda", "look", "like"}):
        return {"ok": True, "say": "", "briefing": "tomorrow"}
    if (w & {"briefing", "rundown", "summary", "agenda"}) or (w & {"today", "todays"} and w & {"what", "whats", "schedule", "plan", "happening"}):
        return {"ok": True, "say": "", "briefing": "today"}

    # "show Ella's day" / "Max's chores" -> per-person mode on the wall
    m_person = re.search(r"\b(?:show|open|pull up)\s+(\w+)'?s?\s+(?:day|chores|stuff|routine|schedule)\b", t.lower())
    if m_person:
        with get_db() as conn:
            row = conn.execute("SELECT id, name FROM people WHERE lower(name)=?", (m_person.group(1),)).fetchone()
        if row:
            return {"ok": True, "say": f"Here's {row['name']}'s day.", "person_mode": row["id"]}

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

    # house modes: "good night", "we're leaving / going out / bye", "I'm home / we're back".
    # Only as a command at the start of what was said, never inside a question ("is it bedtime yet?",
    # "the power is going out" must not lock up the house).
    tl = t.lower().strip(" .!")
    q = bool(re.match(r"^(?:is|are|did|does|do|was|were|has|have|can|could|will|would|should|what|whats|what's|when|where|who|how|why)\b", tl)) or t.strip().endswith("?")
    lead = r"^(?:ok(?:ay)?\s+|hey\s+|alright\s+|so\s+)?(?:run\s+|start\s+|do\s+)?"
    if not q and re.search(lead + r"(?:good ?night|night night|(?:it'?s\s+)?bed ?time|(?:we'?re|i'?m|we are|i am)\s+going to bed|lights out for the night)\b", tl):
        from . import house_modes
        r = house_modes.run("goodnight", close_garage=(True if ("close" in w and "garage" in w) else None))
        warn = r.get("warnings") or []            # keep it soft: only speak up if something needs attention
        return {"ok": True, "say": "Good night." + (" Heads up: " + ", ".join(warn) + "." if warn else ""), "refresh": True}
    if not q and re.search(lead + r"(?:good ?morning|morning everyone|rise and shine|wake up)\b", tl):
        from . import house_modes                  # the Good morning button's steps (voice never disarms)
        r = house_modes.run("morning")
        return {"ok": True, "say": "Good morning!", "refresh": True, "briefing": bool(r.get("briefing"))}
    if not q and re.search(lead + r"(?:we're leaving|we are leaving|were leaving|i'm leaving|i am leaving|im leaving|leaving now|(?:we're |we are |i'm |i am )?(?:going|heading) out|away mode|bye bye|see you later)\b", tl):
        from . import house_modes
        r = house_modes.run("away", close_garage=(True if ("close" in w and "garage" in w) else None))
        return {"ok": True, "say": r.get("say", "Bye for now."), "refresh": True}
    if not q and re.search(lead + r"(?:i'm home|i am home|im home|we're home|we are home|were home|we're back|we are back|were back|i'm back|i am back|im back|welcome home)\b", tl):
        from . import house_modes
        r = house_modes.run("welcome")
        return {"ok": True, "say": r.get("say", "Welcome home."), "refresh": True}

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
    explicit_run = bool(re.match(r"^(?:please\s+)?(?:run|activate|start|do|set)\b", tl)) or "scene" in w
    if scene and not explicit_run:          # "date night Friday" must not run "Good Night"
        nw = {_sing(x) for x in re.findall(r"[a-z0-9]+", scene["name"].lower())} - _STOP
        if not nw <= {_sing(x) for x in w} or len(w - _STOP) > len(nw) + 2:
            scene = None
    wants_scene = scene and (explicit_run or not (w & ON_WORDS or w & OFF_WORDS))
    if scene and wants_scene and not q:
        ha_svc.toggle(scene["entity_id"])
        return {"ok": True, "say": f"Running {scene['name']}.", "refresh": True}

    # questions about a device: "is the garage door open?", "did I lock the front door?" -> just answer
    if q:
        dev = _match(w, tiles, {"cover", "lock", "light", "switch", "binary_sensor", "media_player"})
        if dev:
            return {"ok": True, "say": f"The {dev['name']} is {FHSTATE.get(dev['state'], dev['state'])}."}

    # thermostats: "set the thermostat to 70", "turn the heat up", "turn off the AC"
    said = None if ai else voice_more.climate(t, tiles)
    if said:
        return {"ok": True, "say": said, "refresh": True}

    # on/off device control. Safety: voice can close the garage and lock doors, never open or unlock.
    # Only when it's said like a command ("turn on…", "…lights off", "close the garage") — an "on" inside
    # "vacuum the living room on Saturday" is not a request to switch the living room on.
    control = bool(re.match(r"^(?:please\s+)?(?:can you\s+|could you\s+)?(?:turn|switch|shut|power|flip|kill|open|close|lock|unlock|start|stop|dim|brighten)\b", tl)
                   or re.search(r"\b(?:on|off)$", tl)
                   or re.search(r"\b(?:lights?|lamps?|fans?|tv|plugs?)\s+(?:on|off)\b", tl))
    on, off = bool(w & ON_WORDS), bool(w & OFF_WORDS)
    if control and not q and re.match(r"^(?:please\s+)?lock\b", tl) and (w & {"doors", "up", "everything", "house"}):
        locks = [x for x in tiles if x["domain"] == "lock"]
        for x in locks:
            ha_svc.call_service("lock", "lock", x["entity_id"])
        return {"ok": True, "say": "Locking all the doors." if locks else "I don't see any locks.", "refresh": True}
    if control and not q and w & {"christmas", "xmas", "holiday"} and not any(
            re.search(r"christmas|xmas|holiday", x["name"], re.I) for x in tiles if x["domain"] in ("light", "switch")):
        ids = []
        for helper in ("input_text.fh_outdoor_window_lights", "input_text.fh_outdoor_holiday_lights"):
            ids += [x.strip() for x in (ha_svc._current_state(helper) or "").split(",") if re.match(r"^(light|switch)\.", x.strip())]
        if ids:
            for eid in ids:
                ha_svc.call_service(eid.split(".")[0], "turn_off" if off else "turn_on", eid)
            return {"ok": True, "say": f"Turning {'off' if off else 'on'} the Christmas lights.", "refresh": True}
        return {"ok": False, "say": "I don't know which plugs are the Christmas lights yet. Pick them in Settings, Automations."}
    if control and (on or off) and not q:
        dev = _match(w, tiles, {"light", "switch", "fan", "cover", "lock", "media_player"})
        if dev and ai and not ({_sing(x) for x in re.findall(r"[a-z0-9]+", dev["name"].lower())} & {_sing(x) for x in w}) - _GENERIC - _STOP:
            dev = None
        if dev and ai and re.search(r"\b(and|then|also|except|but|after|before|minutes?|percent|%|dim|bright)\b", tl):
            dev = None                      # "turn off the kitchen and the porch", "dim to 30%": let the AI do it
        if dev:
            dom = dev["domain"]
            if dom in ("light", "switch", "fan", "media_player"):
                ha_svc.call_service(dom, "turn_on" if on else "turn_off", dev["entity_id"])
                verb = "Turning on" if on else "Turning off"
            elif dom == "cover":
                if on and not off:
                    return {"ok": False, "say": f"For safety I don't open the {dev['name']} by voice. Use the phone or the I'm home button."}
                ha_svc.call_service("cover", "close_cover", dev["entity_id"])
                verb = "Closing"
            else:  # lock
                if "unlock" in w or (on and not off):
                    return {"ok": False, "say": "For safety I don't unlock doors by voice. Use the phone."}
                ha_svc.call_service("lock", "lock", dev["entity_id"])
                verb = "Locking"
            return {"ok": True, "say": f"{verb} {dev['name']}.", "refresh": True}

    if ai:
        r = voice_agent.run(t, tiles)
        if r:
            return r
        return _interpret(text, use_ai=False)

    # add to a list ("add …", "remind Rachell to …", "Ella needs to …")
    if "add" in w or "remind" in w or re.search(r"\b(needs?|has|have)\s+to\b", t.lower()):
        said = _add_to_list(t)
        if said:
            return {"ok": True, "say": said, "refresh": True}

    # fallback: AI answer (or capability hint)
    return {"ok": True, "say": _ai_answer(t)}
