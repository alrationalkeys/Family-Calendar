"""
More things the wall's voice understands, all rule-based (no AI key needed):

  - calendar events      "add dentist Thursday at 3", "put soccer on the calendar tomorrow at 5:30",
                         "schedule date night Friday at 7", "Rachell's hair appointment November 20th at 10 am"
  - grocery phrasing     "we need paper towels", "we're out of coffee", "we're low on dog food"
  - reading lists        "what's on the grocery list", "what's on my to-do list", "what chores does Alex have"
  - checking things off  "check off milk", "cross off eggs", "mark take out the trash as done",
                         "remove milk from the grocery list", "I finished the Christmas village"
  - thermostats          "what's the temperature inside", "set the thermostat to 70", "set upstairs to 68",
                         "turn the heat up", "turn off the AC"  (heat/air never turned ON during peak)

Each helper returns a sentence to say, or None when the phrase isn't for it.
"""
from __future__ import annotations

import datetime
import re

from ..db import get_db

_WD = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                          "august", "september", "october", "november", "december"])}
_MONTHS.update({"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9,
                "oct": 10, "nov": 11, "dec": 12})
_ORD_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
              "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
              "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
              "twentieth": 20, "thirtieth": 30}
_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12}
_EVENING = re.compile(r"\b(night|dinner|supper|party|movie|show|concert|game|date|drinks|tonight|evening|bowling)\b")
_MON_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))

_STOPW = {"a", "an", "the", "to", "for", "of", "on", "in", "at", "and", "or", "my", "our", "is", "it", "off", "as",
          "list", "grocery", "groceries", "shopping", "todo", "do", "chore", "chores", "done", "complete", "from",
          "mark", "check", "cross", "tick", "remove", "delete", "take", "i", "we", "finished", "did", "got", "bought",
          "please", "s", "that", "this", "with", "be"}


def _sing(x: str) -> str:
    return x[:-1] if len(x) > 3 and x.endswith("s") and not x.endswith("ss") else x


def _wset(s: str) -> set:
    return {_sing(x) for x in re.findall(r"[a-z0-9]+", (s or "").lower())} - _STOPW


def _say_list(xs, limit=10):
    xs = [x for x in xs if x]
    if not xs:
        return ""
    more = len(xs) - limit
    xs = xs[:limit]
    s = xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]
    return s + (f", plus {more} more" if more > 0 else "")


# ------------------------------------------------------------------ dates + times
def parse_when(low: str, today: datetime.date | None = None, now: datetime.datetime | None = None):
    """Spoken date/time -> (date or None, (hour, minute) or None, [spans to cut from the title]).
    Today/tonight/tomorrow/day after tomorrow, (this|next) <weekday>, November 20th / Nov 20 / the 20th /
    20th of November / 11/20, at 3 / at 3:30 pm / 5:30 / 10 am / noon / midnight."""
    today = today or datetime.date.today()
    now = now or datetime.datetime.now()
    spans, day, tm = [], None, None

    def cut(m):
        spans.append((m.start(), m.end()))

    # time first ("at 3", "3:30 pm", "10 am", "noon")
    m = (re.search(r"\b(?:at|@)\s+(\d{1,2})(?::(\d{2}))?\s*(a\.?\s?m\.?|p\.?\s?m\.?|o'?clock)?(?=\W|$)", low)
         or re.search(r"\b(\d{1,2}):(\d{2})\s*(a\.?\s?m\.?|p\.?\s?m\.?)?(?=\W|$)", low)
         or re.search(r"\b(\d{1,2})()\s*(a\.?\s?m\.?|p\.?\s?m\.?)(?=\W|$)", low)
         or re.search(r"\b(?:at\s+)?(" + "|".join(_NUM) + r")()\s*(a\.?\s?m\.?|p\.?\s?m\.?|o'?clock)(?=\W|$)", low))
    if m:
        h = int(m.group(1)) if m.group(1).isdigit() else _NUM[m.group(1)]
        mi = int(m.group(2)) if m.group(2) else 0
        ap = (m.group(3) or "").replace(".", "").replace(" ", "")
        if h <= 23 and mi <= 59:
            if ap.startswith("p") and h < 12:
                h += 12
            elif ap.startswith("a") and h == 12:
                h = 0
            elif not ap.startswith(("a", "p")) and h < 12:
                # no am/pm: 1-6 is afternoon, 7-11 is morning unless it sounds like an evening thing
                if 1 <= h <= 6 or (7 <= h <= 11 and _EVENING.search(low)):
                    h += 12
            tm = (h, mi)
            cut(m)
    else:
        m = re.search(r"\b(?:at\s+)?(noon|midday|midnight)\b", low)
        if m:
            tm = (12, 0) if m.group(1) != "midnight" else (0, 0)
            cut(m)
    if tm and re.search(r"\btonight\b", low) and tm[0] < 12:
        tm = (tm[0] + 12, tm[1])

    # date
    m = re.search(r"\b(?:on\s+)?(?:the\s+)?day after tomorrow\b", low)
    if m:
        day = today + datetime.timedelta(days=2); cut(m)
    if not day:
        m = re.search(r"\b(?:for\s+|on\s+)?(today|tonight|this (?:morning|afternoon|evening)|tomorrow(?: (?:morning|afternoon|night|evening))?)\b", low)
        if m:
            w = m.group(1)
            day = today + datetime.timedelta(days=1) if w.startswith("tomorrow") else today
            if tm is None and re.search(r"evening|night", w):
                pass
            cut(m)
    if not day:
        m = re.search(r"\b(?:on\s+)?(?:(this|next|this coming|coming)\s+)?(" + "|".join(_WD) + r")\b", low)
        if m:
            wd = _WD.index(m.group(2))
            ahead = (wd - today.weekday()) % 7
            if ahead == 0:
                if m.group(1) == "next" or (tm and (tm[0], tm[1]) <= (now.hour, now.minute)) or not tm:
                    ahead = 7
            elif m.group(1) == "next" and today.weekday() + ahead <= 6 and wd > today.weekday():
                ahead += 7      # "next Friday" said on a Wednesday = the Friday after this one
            day = today + datetime.timedelta(days=ahead)
            cut(m)
    if not day:
        ordw = "|".join(_ORD_WORDS)
        pats = [
            (rf"\b(?:on\s+)?(?:the\s+)?({_MON_RE})\.?\s+(?:the\s+)?(\d{{1,2}}|{ordw})(?:st|nd|rd|th)?\b", "md"),
            (rf"\b(?:on\s+)?(?:the\s+)?(\d{{1,2}}|{ordw})(?:st|nd|rd|th)?\s+of\s+({_MON_RE})\b", "dm"),
            (r"\b(?:on\s+)?(\d{1,2})/(\d{1,2})(?:/\d{2,4})?\b", "nn"),
            (rf"\b(?:on\s+)?the\s+(\d{{1,2}}|{ordw})(?:st|nd|rd|th)?\b", "d"),
        ]
        for p, kind in pats:
            m = re.search(p, low)
            if not m:
                continue
            g = [x for x in m.groups()]
            num = lambda s: int(s) if s.isdigit() else _ORD_WORDS.get(s, 0)
            try:
                if kind == "md":
                    mo, d = _MONTHS[g[0]], num(g[1])
                elif kind == "dm":
                    d, mo = num(g[0]), _MONTHS[g[1]]
                elif kind == "nn":
                    mo, d = int(g[0]), int(g[1])
                else:
                    d = num(g[0])
                    mo = today.month if d >= today.day else (today.month % 12) + 1
                y = today.year
                cand = datetime.date(y, mo, d)
                if cand < today:
                    cand = datetime.date(y + 1, mo, d) if kind != "d" else cand
                day = cand
                cut(m)
                break
            except (ValueError, KeyError):
                continue
    return day, tm, spans


def _cut(text: str, spans):
    for a, b in sorted(spans, reverse=True):
        text = text[:a] + " " + text[b:]
    return text


def looks_like_event(low: str) -> bool:
    """A date or a clock time in an 'add …' sentence, or calendar words."""
    if re.search(r"\b(calendar|appointment|appt|schedule|meeting|reservation|party|practice|game|recital|birthday)\b", low):
        return True
    day, tm, _ = parse_when(low)
    if tm:
        return True
    # a date alone ("add dentist on Thursday") is an event; repeating words belong to chores/to-dos
    return bool(day) and not re.search(r"\b(every|each|daily|weekly|monthly|weekdays?|weekends?)\b", low)


def add_event(text: str):
    """'add dentist appointment Thursday at 3 pm for Rachell' -> a FamilyHub calendar event."""
    from .people import extract_person
    low = text.lower()
    today = datetime.date.today()
    day, tm, spans = parse_when(low, today)
    title = _cut(text, spans)
    title = re.sub(r"^\s*(?:please\s+)?(?:can you\s+)?(?:add|put|create|make|schedule|book|new)\b\s*(?:an?\s+)?(?:event|appointment)?\s*(?:for\s+)?", "", title, flags=re.I)
    title = re.sub(r"\b(?:to|on|onto|in|into)\s+(?:the|my|our|\w+'s)\s+(?:calendar|schedule)\b", " ", title, flags=re.I)
    title = re.sub(r"\b(?:the\s+)?(?:calendar|schedule)\b", " ", title, flags=re.I)
    try:
        with get_db() as conn:
            pid, pname, title = extract_person(conn, title)
            title = re.sub(r"^'s\b\s*", "", title)
            title = re.sub(r"\s+(?:on|at|for|from|this|next)\s*$", "", title.strip(" ,.:;-"), flags=re.I)
            title = re.sub(r"^(?:an?|the)\s+", "", title.strip(" ,.:;-"), flags=re.I)
            title = re.sub(r"\s{2,}", " ", title).strip(" ,.:;-")
            if not title:
                return None
            title = title[0].upper() + title[1:120]
            if not day and not tm:
                return f"When is {title}? Say something like: add {title} on Friday at 3."
            if not day:
                day = today if (tm[0], tm[1]) > (datetime.datetime.now().hour, datetime.datetime.now().minute) else today + datetime.timedelta(days=1)
            if tm:
                start = datetime.datetime.combine(day, datetime.time(tm[0], tm[1]))
                end = start + datetime.timedelta(hours=1)
                conn.execute("INSERT INTO local_events (title,start,end,all_day,person_id) VALUES (?,?,?,?,?)",
                             (title, start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes"), 0, pid))
            else:
                conn.execute("INSERT INTO local_events (title,start,end,all_day,person_id) VALUES (?,?,?,?,?)",
                             (title, day.isoformat(), None, 1, pid))
    except Exception:
        return None
    rel = "today" if day == today else "tomorrow" if day == today + datetime.timedelta(days=1) else day.strftime("%A %B %-d")
    at = (" at " + datetime.time(tm[0], tm[1]).strftime("%-I:%M %p").replace(":00", "")) if tm else ""
    return f"Added {title} to the calendar {rel}{at}" + (f" for {pname}." if pname else ".")


# ------------------------------------------------------------------ groceries said naturally
def grocery_phrase(text: str):
    """'we need paper towels' / 'we're out of coffee' / 'we're low on dog food' / 'we need to buy eggs'."""
    low = text.lower().strip(" .!")
    m = (re.match(r"^(?:we|i)(?:'re| are|'m| am|re)?\s+(?:all\s+|almost\s+|running\s+|getting\s+)?(?:out of|low on)\s+(.+)$", low)
         or re.match(r"^(?:we|i)\s+need\s+to\s+(?:buy|get|grab|pick up)\s+(.+)$", low)
         or re.match(r"^(?:we|i)\s+(?:need|want)\s+(?:more\s+|some\s+|a\s+|an\s+)?(?!to\b)(.+)$", low)
         or re.match(r"^(?:we|i)\s+ran out of\s+(.+)$", low))
    if not m:
        return None
    item = re.sub(r"\b(?:on|to)\s+(?:the|my|our)\s+(?:grocery|shopping)?\s*list\b.*$", "", m.group(1)).strip(" ,.")
    item = re.sub(r"^(?:more|some)\s+", "", item)
    if not item or len(item) > 60:
        return None
    with get_db() as conn:
        conn.execute("INSERT INTO groceries (item) VALUES (?)", (item,))
    return f"Added {item} to the groceries."


# ------------------------------------------------------------------ reading lists
def _week_end(today):
    return today + datetime.timedelta(days=6 - today.weekday())


def list_query(text: str):
    low = text.lower()
    ask = re.search(r"\b(what'?s|what is|what are|what do|what does|whats|read|tell me|list|any|how many|do we|do i|does)\b", low)
    if not ask:
        return None
    from .people import extract_person
    today = datetime.date.today()
    with get_db() as conn:
        pid, pname, _ = extract_person(conn, text)
        if re.search(r"\b(grocer\w*|shopping)\b", low) or re.search(r"\bwhat do we need\b", low):
            rows = [r["item"] for r in conn.execute("SELECT item FROM groceries WHERE got=0 ORDER BY id")]
            if not rows:
                return "The grocery list is empty."
            return f"{len(rows)} thing{'s' if len(rows) != 1 else ''} on the grocery list: {_say_list(rows, 12)}."
        if re.search(r"\b(to[\s-]?dos?|todos?|tasks?)\b", low) and not re.search(r"\bchores?\b", low):
            q = "SELECT title FROM todos WHERE done=0 AND (due_date IS NULL OR due_date<=?)"
            args = [_week_end(today).isoformat()]
            if pid:
                q += " AND (person_id=? OR person_id IS NULL)"; args.append(pid)
            rows = [r["title"] for r in conn.execute(q + " ORDER BY due_date IS NULL, due_date, id", args)]
            who = f"{pname}'s" if pid else "the"
            if not rows:
                return f"Nothing on {who} to-do list this week."
            return f"On {who} to-do list: {_say_list(rows)}."
        if re.search(r"\bchores?\b", low):
            q = "SELECT c.title, p.name FROM chores c LEFT JOIN people p ON p.id=c.person_id WHERE c.done=0 AND (c.due_date IS NULL OR c.due_date<=?)"
            args = [today.isoformat()]
            if pid:
                q += " AND (c.person_id=? OR c.person_id IS NULL)"; args.append(pid)
            rows = list(conn.execute(q + " ORDER BY c.due_date, c.id", args))
            if not rows:
                return f"{pname} has no chores left today." if pid else "No chores left today."
            items = [r["title"] + (f" for {r['name'].split(' ')[0]}" if (r["name"] and not pid) else "") for r in rows]
            return (f"{pname}'s chores today: " if pid else "Chores left today: ") + _say_list(items) + "."
    return None


# ------------------------------------------------------------------ checking things off
def complete(text: str):
    low = text.lower().strip(" .!?")
    remove = bool(re.match(r"^(?:please\s+)?(?:remove|delete|take)\b", low))
    pat = (r"^(?:please\s+)?(?:check|cross|tick|mark)\s+(?:off\s+)?(.+?)(?:\s+(?:off|as\s+(?:done|complete|completed|finished)|done|complete|completed))?$"
           r"|^(?:please\s+)?(?:remove|delete)\s+(.+?)(?:\s+(?:off|from)\s+(?:the|my|our)\s+.*)?$"
           r"|^(?:please\s+)?take\s+(.+?)\s+off\s+(?:the|my|our)\s+.*list$"
           r"|^(?:i|we)\s+(?:just\s+)?(?:finished|did|completed|bought|picked up)\s+(.+)$"
           r"|^(.+?)\s+(?:is|are)\s+(?:done|finished|complete|completed)$")
    m = re.match(pat, low)
    if not m:
        return None
    phrase = next(g for g in m.groups() if g)
    phrase = re.sub(r"\b(?:off|from|on)\s+(?:the|my|our|\w+'s)\s+(?:grocery|shopping|to[\s-]?do|todo|chore)?\s*(?:list|chart)?\b.*$", "", phrase).strip(" ,.")
    want = _wset(phrase)
    if not want:
        return None
    only = ("grocery" if re.search(r"grocer|shopping|bought|picked up", low) else
            "todo" if re.search(r"to[\s-]?do|task", low) else
            "chore" if re.search(r"\bchore", low) else None)
    today = datetime.date.today()
    best, score = None, 0.0
    with get_db() as conn:
        cands = []
        if only in (None, "grocery"):
            cands += [("grocery", r["id"], r["item"]) for r in conn.execute("SELECT id, item FROM groceries WHERE got=0")]
        if only in (None, "todo"):
            cands += [("todo", r["id"], r["title"]) for r in conn.execute("SELECT id, title FROM todos WHERE done=0")]
        if only in (None, "chore"):
            cands += [("chore", r["id"], r["title"]) for r in conn.execute(
                "SELECT id, title FROM chores WHERE done=0 AND (due_date IS NULL OR due_date<=?)", (_week_end(today).isoformat(),))]
        for kind, iid, title in cands:
            tw = _wset(title)
            if not tw:
                continue
            hit = len(tw & want)
            s = hit / max(len(tw), len(want))
            if hit and hit * 2 >= len(tw) and s > score:
                best, score = (kind, iid, title), s
    if not best:
        return "I couldn't find that on your lists."
    kind, iid, title = best
    if kind == "grocery":
        with get_db() as conn:
            if remove:
                conn.execute("DELETE FROM groceries WHERE id=?", (iid,))
                return f"Removed {title} from the groceries."
            conn.execute("UPDATE groceries SET got=1, got_at=datetime('now') WHERE id=?", (iid,))
        return f"Checked off {title}."
    if kind == "todo":
        if remove:
            with get_db() as conn:
                row = conn.execute("SELECT recurrence FROM todos WHERE id=?", (iid,)).fetchone()
                if row and row["recurrence"]:
                    return f"{title} repeats. To delete it, hold it on the screen and pick Delete."
                conn.execute("DELETE FROM todos WHERE id=?", (iid,))
            return f"Removed {title} from the to-do list."
        from ..routers.todos import toggle as todo_toggle
        r = todo_toggle(iid)
        return f"Marked {title} done." + (" It'll come back next time." if r.get("recurred") else "")
    if remove:
        return f"To delete the chore {title}, hold it on the screen and pick Delete."
    from ..routers.chores import toggle as chore_toggle
    r = chore_toggle(iid)
    stars = r.get("stars_earned") or 0
    return f"Nice, {title} is done." + (f" {stars} star{'s' if stars != 1 else ''} earned." if stars else "")


# ------------------------------------------------------------------ thermostats
_CLIMATE_W = {"thermostat", "thermostats", "heat", "heater", "heating", "ac", "a", "air", "conditioning", "conditioner",
              "cooling", "temperature", "temp", "warmer", "cooler", "colder", "hotter", "degrees", "furnace"}


def climate(text: str, tiles: list):
    from . import ha_svc
    low = text.lower().strip(" .!?")
    low = re.sub(r"\ba\.?\s?c\.?\b", "ac", low)
    w = set(re.findall(r"[a-z0-9]+", low))
    stats = [t for t in tiles if t["domain"] == "climate"]
    room = lambda t: set(re.findall(r"[a-z]+", t["name"].lower())) - {"thermostat", "the", "climate", "hvac"}
    said_room = any(room(t) and room(t) <= w for t in stats)
    if not (w & (_CLIMATE_W - {"a", "degrees", "temperature", "temp"})
            or ((said_room or re.search(r"\b(inside|in here|indoors|in the house)\b", low))
                and re.search(r"\b(warm|cold|hot|chilly|temperature|temp)\b", low) and re.match(r"^(?:how|what|whats|what's|is)\b", low))
            or (said_room and re.search(r"\b(\d{2}|warmer|cooler|up|down)\b", low) and re.match(r"^(?:set|make|turn|put|bump|raise|lower)\b", low))
            or (w & {"temperature", "temp", "degrees"} and re.search(r"\b(inside|in here|house|indoors|upstairs|downstairs)\b", low))):
        return None
    if "outside" in w or "weather" in w:
        return None
    if not stats:
        return None
    named = [t for t in stats if room(t) and room(t) <= w]
    targets = named or stats
    # "the AC" means the ones cooling, "the heat" the ones heating (when that narrows it down)
    if w & {"ac", "air", "cooling", "conditioning", "conditioner"} and not w & {"heat", "heater", "heating"}:
        targets = [t for t in targets if t.get("state") in ("cool", "heat_cool", "auto")] or targets
    elif w & {"heat", "heater", "heating", "furnace"} and not w & {"ac", "air"}:
        targets = [t for t in targets if t.get("state") in ("heat", "heat_cool", "auto")] or targets
    short = lambda t: re.sub(r"\s*thermostat\s*", "", t["name"], flags=re.I).strip() or t["name"]
    peak = next((t for t in tiles if t["entity_id"] == "binary_sensor.santee_cooper_peak_now"), None)
    in_peak = bool(peak and peak.get("on"))
    fmt = lambda v: str(int(round(float(v)))) if v is not None else "?"

    question = bool(re.match(r"^(?:what|whats|what's|how|is|are|tell me)\b", low))
    if question:
        parts = []
        for t in targets:
            mode = t.get("state") or "off"
            s = f"{short(t)} is {fmt(t.get('current_temperature'))}"
            if mode == "off":
                s += ", heat and air off"
            elif t.get("target_temperature") is not None:
                s += f", set to {mode.replace('_', ' ')} {fmt(t.get('target_temperature'))}"
            parts.append(s)
        return ". ".join(parts) + "." + (" It's peak hours right now." if in_peak else "")

    # mode: "turn off the heat / AC / thermostat", "turn on the heat", "turn the AC on"
    off = bool(re.search(r"\b(off|disable|shut)\b", low))
    on = bool(re.search(r"\bturn\b.*\bon\b|\bon$|\bstart\b", low)) and not off
    if off and not re.search(r"\d", low):
        for t in targets:
            ha_svc.call_service("climate", "set_hvac_mode", t["entity_id"], {"hvac_mode": "off"})
        one = short(targets[0]) if len(targets) == 1 else ""
        what = "air" if w & {"ac", "air"} else "heat" if w & {"heat", "heater", "heating"} else "heat and air"
        return f"Turned off the {what}" + (f" {one.lower()}." if one and one.lower() != "thermostat" and len(stats) > 1 else ".")
    if on and not re.search(r"\d", low):
        mode = "cool" if w & {"ac", "air", "cooling", "conditioning", "conditioner"} else "heat"
        if in_peak:
            return "It's Santee Cooper peak hours, so the heat and air stay off until peak ends."
        for t in targets:
            if mode in (t.get("hvac_modes") or [mode]):
                ha_svc.call_service("climate", "set_hvac_mode", t["entity_id"], {"hvac_mode": mode})
        return f"Turned on the {'air' if mode == 'cool' else 'heat'}."

    # setpoint: "set the thermostat to 70", "make it 68 upstairs", "turn the heat up", "a little warmer"
    m = re.search(r"\b(\d{2})\b", low)
    up = bool(re.search(r"\b(up|warmer|hotter|raise|increase|higher)\b", low))
    down = bool(re.search(r"\b(down|cooler|colder|lower|decrease)\b", low))
    if not (m or up or down):
        return None
    done = []
    for t in targets:
        if (t.get("state") or "off") == "off":
            continue
        cur = t.get("target_temperature")
        if cur is None:            # auto (heat/cool range) — leave it to the phone
            continue
        new = float(m.group(1)) if m else float(cur) + (2 if up else -2)
        lo, hi = float(t.get("min_temp") or 50), float(t.get("max_temp") or 90)
        new = max(lo, min(hi, new))
        ha_svc.call_service("climate", "set_temperature", t["entity_id"], {"temperature": new})
        done.append(f"{short(t)} to {fmt(new)}")
    if not done:
        if in_peak:
            return "It's peak hours, so the heat and air are off until peak ends."
        return "The thermostat is off or on auto. Use the thermostat button on the screen to change it."
    return "Set " + _say_list(done) + "."
