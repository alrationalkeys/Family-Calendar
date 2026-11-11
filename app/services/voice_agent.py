"""
The wall's voice brain when an Anthropic key is set: Claude reads what was said and DOES it with tools
(calendar, to-dos, chores, groceries, checking things off, lights/switches/scenes, thermostats, timers,
Good night / Leaving), or answers it (with web search for live facts). The rule-based interpreter in
voice_cmd stays as the instant path for the obvious commands and the fallback when the AI can't be reached.

Safety lives HERE in code, not in the prompt: no disarming, no opening covers, no unlocking, heat/air never
turned on during Santee Cooper peak, FamilyHub's own fh_* scripts aren't exposed.
"""
from __future__ import annotations

import datetime
import json
import os
import re

from ..db import get_db

_REPEAT = {"type": ["string", "null"],
           "description": "null, or 'daily', 'weekly' (same weekday as the date), 'weekly:MO,TH' (2-letter days), 'monthly'"}
_PERSON = {"type": ["string", "null"], "description": "family member's first name exactly as listed, or null"}

TOOLS = [
    {"name": "add_event", "description": "Put something on the family calendar (appointments, plans, parties, games, trips).",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string", "description": "short title, without the date/time words or the person's name"},
         "date": {"type": "string", "description": "YYYY-MM-DD"},
         "time": {"type": ["string", "null"], "description": "HH:MM 24-hour, or null for all day"},
         "duration_minutes": {"type": ["integer", "null"]},
         "person": _PERSON, "repeat": _REPEAT}, "required": ["title", "date"]}},
    {"name": "add_todo", "description": "Add to the to-do list (one-off jobs, errands, reminders).",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string"}, "person": _PERSON,
         "due_date": {"type": ["string", "null"], "description": "YYYY-MM-DD or null"}, "repeat": _REPEAT},
         "required": ["title"]}},
    {"name": "add_chore", "description": "Add a household chore to the chore chart (usually repeating: trash, dogs, vacuuming).",
     "input_schema": {"type": "object", "properties": {
         "title": {"type": "string"}, "person": _PERSON,
         "first_date": {"type": ["string", "null"], "description": "YYYY-MM-DD it's first due; null = today"},
         "repeat": _REPEAT, "stars": {"type": ["integer", "null"]}}, "required": ["title"]}},
    {"name": "add_groceries", "description": "Add items to the grocery list. One entry per item.",
     "input_schema": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "string"}}},
                      "required": ["items"]}},
    {"name": "complete_item", "description": "Check off (or remove) a grocery item, to-do or chore, by its id from the lists in the context.",
     "input_schema": {"type": "object", "properties": {
         "list": {"type": "string", "enum": ["grocery", "todo", "chore"]}, "id": {"type": "integer"},
         "remove": {"type": "boolean", "description": "true = delete it instead of checking it off"}},
         "required": ["list", "id"]}},
    {"name": "control_device", "description": "Turn a light/switch/fan/TV on or off, dim a light, run a scene, close a garage door or lock a lock.",
     "input_schema": {"type": "object", "properties": {
         "entity_ids": {"type": "array", "items": {"type": "string"}, "description": "entity ids from the device list"},
         "action": {"type": "string", "enum": ["on", "off", "close", "lock", "brightness"]},
         "brightness_pct": {"type": ["integer", "null"]}}, "required": ["entity_ids", "action"]}},
    {"name": "set_thermostat", "description": "Change a thermostat: target temperature and/or mode.",
     "input_schema": {"type": "object", "properties": {
         "entity_ids": {"type": "array", "items": {"type": "string"}, "description": "climate entity ids; all of them if the room wasn't said"},
         "temperature": {"type": ["number", "null"]},
         "mode": {"type": ["string", "null"], "enum": ["heat", "cool", "off", None]}}, "required": ["entity_ids"]}},
    {"name": "set_timer", "description": "Start a kitchen timer on the wall, or cancel all timers (seconds = 0).",
     "input_schema": {"type": "object", "properties": {
         "seconds": {"type": "integer"}, "label": {"type": ["string", "null"]}}, "required": ["seconds"]}},
    {"name": "house_mode", "description": "Run a whole-house routine: 'goodnight' (lock up, arm Stay, close garage) or 'away' (leaving).",
     "input_schema": {"type": "object", "properties": {"mode": {"type": "string", "enum": ["goodnight", "away"]}},
                      "required": ["mode"]}},
]


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _people(conn):
    return {r["name"].split(" ")[0].lower(): (r["id"], r["name"]) for r in conn.execute("SELECT id, name FROM people") if r["name"]}


def _pid(conn, name):
    if not name:
        return None, None
    from .people import _similar
    first = name.strip().split(" ")[0].lower()
    for k, v in _people(conn).items():
        if _similar(first, k):
            return v
    return None, None


def _rec(repeat):
    r = (repeat or "").strip().lower()
    if r in ("daily", "weekly", "monthly"):
        return r
    m = re.match(r"^weekly:([a-z]{2}(?:,[a-z]{2})*)$", r)
    return "weekly:" + m.group(1).upper() if m else None


def _date(s, default=None):
    try:
        return datetime.date.fromisoformat((s or "")[:10])
    except ValueError:
        return default


def _devices(tiles):
    out = []
    for t in tiles:
        d = t["domain"]
        if d not in ("light", "switch", "fan", "media_player", "cover", "lock", "scene", "climate", "binary_sensor", "sensor"):
            continue
        if t["entity_id"].startswith("script.fh_"):
            continue
        extra = ""
        if d == "climate":
            extra = f" now {t.get('current_temperature')}°, set {t.get('target_temperature')}"
        elif d == "sensor" and t.get("unit"):
            extra = f" {t.get('unit')}"
        area = f" [{t['area']}]" if t.get("area") else ""
        out.append(f"{t['entity_id']} | {t['name']}{area} | {t['state']}{extra}")
    return "\n".join(out[:180])


def _lists(conn, today):
    lines = []
    g = [f"#{r['id']} {r['item']}" for r in conn.execute("SELECT id, item FROM groceries WHERE got=0 ORDER BY id LIMIT 40")]
    t = [f"#{r['id']} {r['title']}" + (f" ({r['name']})" if r["name"] else "") + (f" due {r['due_date']}" if r["due_date"] else "")
         for r in conn.execute("SELECT t.id, t.title, t.due_date, p.name FROM todos t LEFT JOIN people p ON p.id=t.person_id "
                               "WHERE t.done=0 ORDER BY t.due_date IS NULL, t.due_date LIMIT 40")]
    c = [f"#{r['id']} {r['title']}" + (f" ({r['name']})" if r["name"] else "") + (f" due {r['due_date']}" if r["due_date"] else "")
         + (f" repeats {r['recurrence']}" if r["recurrence"] else "")
         for r in conn.execute("SELECT c.id, c.title, c.due_date, c.recurrence, p.name FROM chores c LEFT JOIN people p ON p.id=c.person_id "
                               "WHERE c.done=0 ORDER BY c.due_date LIMIT 40")]
    lines.append("Grocery list: " + ("; ".join(g) or "empty"))
    lines.append("To-do list: " + ("; ".join(t) or "empty"))
    lines.append("Chores: " + ("; ".join(c) or "none"))
    return "\n".join(lines)


def _run_tool(name, a, tiles, out):
    """Execute one tool call. Returns a short result string for the model."""
    from . import ha_svc
    today = datetime.date.today()
    if name == "add_event":
        day = _date(a.get("date"))
        if not day:
            return "error: date must be YYYY-MM-DD"
        with get_db() as conn:
            pid, pname = _pid(conn, a.get("person"))
            tm = a.get("time")
            if tm and re.match(r"^\d{1,2}:\d{2}$", tm):
                h, mi = map(int, tm.split(":"))
                start = datetime.datetime.combine(day, datetime.time(h % 24, mi % 60))
                end = start + datetime.timedelta(minutes=int(a.get("duration_minutes") or 60))
                conn.execute("INSERT INTO local_events (title,start,end,all_day,person_id,recurrence) VALUES (?,?,?,?,?,?)",
                             (a["title"][:120], start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes"), 0, pid, _rec(a.get("repeat"))))
            else:
                conn.execute("INSERT INTO local_events (title,start,end,all_day,person_id,recurrence) VALUES (?,?,?,?,?,?)",
                             (a["title"][:120], day.isoformat(), None, 1, pid, _rec(a.get("repeat"))))
        out["refresh"] = True
        return f"added to calendar {day.isoformat()} {tm or 'all day'}" + (f" for {pname}" if pname else "")
    if name == "add_todo":
        with get_db() as conn:
            pid, pname = _pid(conn, a.get("person"))
            due = _date(a.get("due_date"))
            rec = _rec(a.get("repeat"))
            if rec and not due:
                due = today
            conn.execute("INSERT INTO todos (title, person_id, due_date, recurrence) VALUES (?,?,?,?)",
                         (a["title"][:120], pid, due.isoformat() if due else None, rec))
        out["refresh"] = True
        return "added to-do" + (f" for {pname}" if pname else "")
    if name == "add_chore":
        with get_db() as conn:
            pid, pname = _pid(conn, a.get("person"))
            due = _date(a.get("first_date"), today)
            conn.execute("INSERT INTO chores (title, person_id, due_date, recurrence, stars) VALUES (?,?,?,?,?)",
                         (a["title"][:120], pid, due.isoformat(), _rec(a.get("repeat")), int(a.get("stars") or 0)))
        out["refresh"] = True
        return "added chore" + (f" for {pname}" if pname else "") + f", first due {due.isoformat()}"
    if name == "add_groceries":
        items = [str(x).strip()[:80] for x in (a.get("items") or []) if str(x).strip()][:20]
        with get_db() as conn:
            for it in items:
                conn.execute("INSERT INTO groceries (item) VALUES (?)", (it,))
        out["refresh"] = True
        return f"added {len(items)} grocery item(s)"
    if name == "complete_item":
        kind, iid, remove = a.get("list"), int(a.get("id") or 0), bool(a.get("remove"))
        with get_db() as conn:
            if kind == "grocery":
                if remove:
                    conn.execute("DELETE FROM groceries WHERE id=?", (iid,))
                else:
                    conn.execute("UPDATE groceries SET got=1, got_at=datetime('now') WHERE id=?", (iid,))
                out["refresh"] = True
                return "done"
            if kind == "todo" and remove:
                row = conn.execute("SELECT recurrence FROM todos WHERE id=?", (iid,)).fetchone()
                if row and row["recurrence"]:
                    return "refused: it repeats; tell them to hold it on the screen and pick Delete"
                conn.execute("DELETE FROM todos WHERE id=?", (iid,))
                out["refresh"] = True
                return "deleted"
        if kind == "chore" and remove:
            return "refused: chores are deleted on the screen (hold it, pick Delete)"
        try:
            if kind == "todo":
                from ..routers.todos import toggle
                r = toggle(iid)
            else:
                from ..routers.chores import toggle
                r = toggle(iid)
        except Exception:
            return "error: no such item"
        out["refresh"] = True
        return "checked off" + (f", {r.get('stars_earned')} stars earned" if r.get("stars_earned") else "") + (", it repeats" if r.get("recurred") else "")
    if name == "control_device":
        known = {t["entity_id"]: t for t in tiles}
        act, done, refused = a.get("action"), [], []
        for eid in a.get("entity_ids") or []:
            t = known.get(eid)
            if not t or eid.startswith("script.fh_"):
                refused.append(f"{eid}: unknown")
                continue
            d = t["domain"]
            if d == "lock":
                if act != "lock":
                    refused.append(f"{t['name']}: unlocking by voice is not allowed")
                    continue
                ha_svc.call_service("lock", "lock", eid)
            elif d == "cover":
                if act not in ("close", "off"):
                    refused.append(f"{t['name']}: opening by voice is not allowed; use the phone or the I'm home button")
                    continue
                ha_svc.call_service("cover", "close_cover", eid)
            elif d == "scene":
                ha_svc.call_service("scene", "turn_on", eid)
            elif d in ("light", "switch", "fan", "media_player"):
                if act == "brightness" and d == "light":
                    ha_svc.call_service("light", "turn_on", eid, {"brightness_pct": max(1, min(100, int(a.get("brightness_pct") or 50)))})
                else:
                    ha_svc.call_service(d, "turn_off" if act == "off" else "turn_on", eid)
            else:
                refused.append(f"{t['name']}: can't control {d}")
                continue
            done.append(t["name"])
        out["refresh"] = True
        return ("done: " + ", ".join(done) if done else "") + (" | " + "; ".join(refused) if refused else "")
    if name == "set_thermostat":
        known = {t["entity_id"]: t for t in tiles if t["domain"] == "climate"}
        peak = next((t for t in tiles if t["entity_id"] == "binary_sensor.santee_cooper_peak_now"), None)
        mode, temp, res = a.get("mode"), a.get("temperature"), []
        if mode in ("heat", "cool") and peak and peak.get("on"):
            return "refused: it's Santee Cooper peak hours; heat and air stay off until peak ends"
        for eid in a.get("entity_ids") or list(known):
            t = known.get(eid)
            if not t:
                continue
            if mode:
                ha_svc.call_service("climate", "set_hvac_mode", eid, {"hvac_mode": mode})
            if temp is not None:
                lo, hi = float(t.get("min_temp") or 50), float(t.get("max_temp") or 90)
                ha_svc.call_service("climate", "set_temperature", eid, {"temperature": max(lo, min(hi, float(temp)))})
            res.append(t["name"])
        out["refresh"] = True
        return "set: " + ", ".join(res) if res else "error: no such thermostat"
    if name == "set_timer":
        secs = int(a.get("seconds") or 0)
        out["timer"] = {"cancel": True} if secs <= 0 else {"seconds": min(secs, 24 * 3600), "label": a.get("label")}
        return "timer cancelled" if secs <= 0 else "timer started"
    if name == "house_mode":
        from . import house_modes
        r = house_modes.run(a.get("mode") if a.get("mode") in ("goodnight", "away") else "goodnight")
        out["refresh"] = True
        return r.get("say", "done")
    return "error: unknown tool"


def run(text: str, tiles: list) -> dict | None:
    """Returns {say, refresh?, timer?} or None if the AI couldn't be reached (caller falls back to rules)."""
    if not enabled():
        return None
    try:
        import anthropic
    except Exception:
        return None
    from .ai_model import model as _model
    from .voice_cmd import _assistant_name, _web_enabled, _HOME_LOCATION
    now = datetime.datetime.now()
    today = now.date()
    with get_db() as conn:
        people = ", ".join(v[1] for v in _people(conn).values()) or "(none)"
        lists = _lists(conn, today)
    try:
        from .voice_cmd import _family_context
        fam = _family_context()
    except Exception:
        fam = ""
    week = ", ".join(f"{(today + datetime.timedelta(days=i)).strftime('%a %b %-d')}={(today + datetime.timedelta(days=i)).isoformat()}" for i in range(0, 14))
    system = (
        f"You are {_assistant_name()}, the voice of a family's wall display in their kitchen. What you get was spoken and "
        "transcribed by speech recognition, so expect mishearings (e.g. 'shore' = chore, 'Rachel' = Rachell, 'to do' / "
        "'today' confusion) and read it for what they most likely meant.\n"
        "If it's a request, DO it with the tools — don't describe what you would do. Pick the right list: calendar for "
        "things happening at a time/place, to-do for one-off jobs and reminders, chores for household jobs (usually "
        "repeating), groceries for things to buy. Assign to a person only when one is named ('for Alex', 'Rachell needs "
        "to', 'remind Alex'); 'me'/'I' = leave unassigned. When a weekday is said with no 'every', it's the next one. "
        "If something essential is missing (no date for an appointment), ask one short question instead of guessing. "
        "Questions about the family's lists, calendar, devices or the house: answer from the context. Live facts (news, "
        "scores, hours, prices): use web search if you have it.\n"
        "You can't disarm the alarm, unlock doors or open the garage — if asked, say to use the phone or the I'm home "
        "button. During Santee Cooper peak hours the heat and air stay off.\n"
        "Reply in ONE or two short spoken sentences confirming what you did or answering (it's read aloud): no lists, "
        "markdown, emoji or URLs. Don't repeat dates as ISO.\n\n"
        f"Now: {now.strftime('%A %B %-d %Y, %-I:%M %p')}. Dates: {week}.\n"
        f"Family: {people}. Home near {_HOME_LOCATION['city']}, {_HOME_LOCATION['region']}.\n\n"
        f"{lists}\n\n{fam}\n\nDevices (entity_id | name [area] | state):\n{_devices(tiles)}"
    )
    tools = list(TOOLS)
    if _web_enabled():
        tools.append({"type": "web_search_20260209", "name": "web_search", "max_uses": 2, "user_location": _HOME_LOCATION})
    client = anthropic.Anthropic(timeout=30.0, max_retries=1)
    mdl = _model()
    kw = dict(model=mdl, max_tokens=2048, system=system, tools=tools)
    if re.search(r"opus-4-[678]|opus-5|sonnet-5|haiku-5|fable|mythos", mdl):
        kw["output_config"] = {"effort": "low"}       # quick, decisive turns for voice
    messages = [{"role": "user", "content": text}]
    out = {"ok": True}
    try:
        for _ in range(6):
            resp = client.messages.create(messages=messages, **kw)
            if resp.stop_reason == "refusal":
                return {"ok": True, "say": "Sorry, I can't help with that one."}
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason == "pause_turn":
                continue
            if resp.stop_reason != "tool_use":
                break
            results = []
            for b in resp.content:
                if b.type != "tool_use":
                    continue
                try:
                    r = _run_tool(b.name, b.input if isinstance(b.input, dict) else json.loads(b.input or "{}"), tiles, out)
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": r or "ok"})
                except Exception as e:
                    results.append({"type": "tool_result", "tool_use_id": b.id, "content": f"error: {e!r}", "is_error": True})
            messages.append({"role": "user", "content": results})
        texts = [b.text for b in resp.content if getattr(b, "type", "") == "text" and b.text.strip()]
        say = re.sub(r"https?://\S+", "", (texts[-1] if texts else "")).strip()
        out["say"] = say or ("Done." if out.get("refresh") or out.get("timer") else "I'm not sure.")
        return out
    except anthropic.APIConnectionError:
        return None
    except anthropic.APIStatusError as e:
        import sys
        print(f"[voice_agent] {e.status_code} {getattr(e, 'message', e)}", file=sys.stderr)
        return None
