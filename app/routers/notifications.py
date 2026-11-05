"""Notifications — reminders before events + a morning 'today' digest.

Design: notifications are queued in the DB with a fire time. The frontend polls
/api/notifications/due, shows anything ready (browser Notification API on the wall,
in-app toast on phone), and marks it seen. No external push service needed — works
entirely on your LAN. A morning digest is generated on demand for 'today'."""
from datetime import date, datetime, timedelta
from .routines import _runs_today
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import get_db

router = APIRouter()


@router.get("/due")
def due_notifications():
    """Return unfired notifications whose time has passed; caller marks them seen."""
    now = datetime.now().isoformat()
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM notifications WHERE fired=0 AND at<=? ORDER BY at", (now,))]
    return {"notifications": rows}


@router.post("/{notif_id}/seen")
def mark_seen(notif_id: int):
    with get_db() as conn:
        conn.execute("UPDATE notifications SET fired=1 WHERE id=?", (notif_id,))
        return {"id": notif_id, "seen": True}


def _say_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    return dt.strftime("%I:%M %p").lstrip("0").replace(":00 ", " ")


def build_digest(day: str = "today") -> dict:
    """Today, as the wall should say it out loud: every calendar source (Google,
    iCloud, ICS, local), weather, routines, chores due, dinner, countdowns."""
    tomorrow = (day or "today").lower() == "tomorrow"
    today = date.today() + timedelta(days=1 if tomorrow else 0)
    tiso = today.isoformat()
    hour = datetime.now().hour
    greet = ("Tomorrow, " + today.strftime("%A") + ".") if tomorrow else ("Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening")
    events = []
    try:
        from .calendar import events as cal_events
        for e in cal_events(days=2, back=0).get("events", []):
            st = e.get("start") or ""
            if not st.startswith(tiso) or str(e.get("title", "")).startswith("[sync error"):
                continue
            events.append(e)
    except Exception:
        pass
    with get_db() as conn:
        chores = [dict(r) for r in conn.execute(
            "SELECT c.title, p.name FROM chores c LEFT JOIN people p ON p.id=c.person_id "
            "WHERE c.done=0 AND (c.due_date IS NULL OR c.due_date<=?)", (tiso,))]
        dinner = conn.execute("SELECT title FROM meals WHERE date=? AND slot='dinner'", (tiso,)).fetchone()
        cds = [dict(r) for r in conn.execute("SELECT title, date FROM countdowns ORDER BY date")]
        from .routines import list_routines
        routines = [r for r in list_routines(conn) if _runs_today(r["days"], today)] if tomorrow else list_routines(conn, only_today=True)
    wx = {}
    try:
        from ..services import weather_svc
        if tomorrow:
            dayfc = (weather_svc.get_forecast(days=3) or {}).get("days", {}).get(tiso)
            if dayfc:
                wx = {"temp": None, "high": dayfc.get("high"), "low": dayfc.get("low"), "desc": dayfc.get("desc")}
        else:
            wx = weather_svc.get_weather() or {}
    except Exception:
        pass

    spoken, lines = [greet if greet.endswith(".") else greet + "."], []
    if tomorrow and wx.get("high") is not None:
        spoken.append(f"High of {wx['high']}, {str(wx.get('desc') or '').lower()}.".replace(", .", "."))
        lines.append(f"🌡 high {wx.get('high')}° · low {wx.get('low', '?')}° · {wx.get('desc', '')}")
    if wx.get("temp") is not None:
        spoken.append(f"It's {wx['temp']} degrees and {str(wx.get('desc') or 'clear').lower()}, with a high of {wx.get('high', '?')}.")
        lines.append(f"🌡 {wx['temp']}° now · high {wx.get('high', '?')}° · {wx.get('desc', '')}")
    timed = [e for e in events if not e.get("all_day")]
    allday = [e for e in events if e.get("all_day")]
    if allday:
        lines += [f"📅 {e['title']}" for e in allday]
    if timed:
        bits = [f"{e['title']} at {_say_time(e['start'])}" for e in timed[:4]]
        more = f", and {len(timed) - 4} more" if len(timed) > 4 else ""
        when = "Tomorrow" if tomorrow else "Today"
        spoken.append((f"{when}: " if not allday else f"It's {', '.join(e['title'] for e in allday[:2])}. Also {when.lower()}: ") + ", ".join(bits) + more + ".")
        lines += [f"🕘 {_say_time(e['start'])} {e['title']}" for e in timed]
    elif allday:
        spoken.append(f"{'Tomorrow' if tomorrow else 'Today'} is {', '.join(e['title'] for e in allday[:3])}. Nothing else on the calendar.")
    else:
        spoken.append(f"Nothing on the calendar {'tomorrow' if tomorrow else 'today'}.")
    if routines:
        names = [r["name"] + (f" for {r['person']}" if r.get("person") else "") for r in routines if not r["complete"]]
        if names:
            spoken.append(("Routines: " if tomorrow else "Routines to do: ") + ", ".join(names[:3]) + ".")
    if chores:
        by = {}
        for c in chores:
            by.setdefault(c["name"] or "someone", 0)
            by[c["name"] or "someone"] += 1
        spoken.append("Chores: " + ", ".join(f"{n} has {k}" for n, k in list(by.items())[:3]) + ".")
        lines.append("⭐ " + ", ".join(f"{n}: {k}" for n, k in by.items()))
    if dinner:
        spoken.append(f"Dinner {'tomorrow' if tomorrow else 'tonight'} is {dinner['title']}.")
        lines.append(f"🍽 Dinner: {dinner['title']}")
    for c in cds[:1]:
        try:
            left = (date.fromisoformat(c["date"]) - today).days
            if 0 < left <= 30:
                spoken.append(f"{left} day{'s' if left != 1 else ''} until {c['title']}.")
            elif left == 0:
                spoken.append(f"And it's {c['title']} today!")
        except ValueError:
            pass
    summary = f"{'Tomorrow' if tomorrow else greet} — {len(events)} event{'s' if len(events) != 1 else ''}" + (f", {len(chores)} chore{'s' if len(chores) != 1 else ''}" if chores else "") + (f", {dinner['title']} tonight" if dinner else "")
    return {"summary": summary, "details": lines, "spoken": " ".join(spoken)}


@router.get("/digest")
def get_digest(day: str = "today"):
    """Today's (or ?day=tomorrow's) briefing without queueing anything — the wall speaks it."""
    return build_digest(day)


@router.post("/digest")
def make_digest():
    """Build the briefing and queue it as a banner notification."""
    d = build_digest()
    with get_db() as conn:
        conn.execute("INSERT INTO notifications (title, body, kind, at, fired) VALUES (?,?,?,?,0)",
                     (d["summary"], "\n".join(d["details"]), "digest", datetime.now().isoformat()))
    return d
