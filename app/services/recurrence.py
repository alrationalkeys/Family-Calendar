"""
Lightweight recurrence for chores/todos. We store a simple recurrence string and,
when an item is completed, roll its due_date forward to the next occurrence instead
of just marking it done. Supported formats:
    "daily"
    "weekly"              (same weekday next week)
    "weekly:MO,WE,FR"     (next listed weekday)
    "monthly"             (same day-of-month next month)
This avoids a heavy rrule dependency while covering what a family actually uses.
"""
import datetime as dt

WD = {"MO":0,"TU":1,"WE":2,"TH":3,"FR":4,"SA":5,"SU":6}


def next_occurrence(rec: str, from_date: dt.date) -> dt.date | None:
    if not rec:
        return None
    rec = rec.strip().lower()
    if rec == "daily":
        return from_date + dt.timedelta(days=1)
    if rec == "weekly":
        return from_date + dt.timedelta(days=7)
    if rec.startswith("weekly:"):
        days = sorted(WD[d.strip().upper()] for d in rec.split(":",1)[1].split(",") if d.strip().upper() in WD)
        if not days:
            return from_date + dt.timedelta(days=7)
        for i in range(1, 8):
            cand = from_date + dt.timedelta(days=i)
            if cand.weekday() in days:
                return cand
        return from_date + dt.timedelta(days=7)
    if rec == "monthly":
        m = from_date.month + 1; y = from_date.year + (m > 12); m = (m - 1) % 12 + 1
        # clamp day to month length
        import calendar
        day = min(from_date.day, calendar.monthrange(y, m)[1])
        return dt.date(y, m, day)
    return None


def expand_events(base_events, start, end):
    """Expand recurring local events into individual occurrences within [start, end].
    base_events: list of dicts with 'start' (ISO), optional 'recurrence'.
    Non-recurring events pass through unchanged if in range."""
    import datetime as dt
    out = []
    for ev in base_events:
        rec = ev.get("recurrence")
        try:
            first = dt.datetime.fromisoformat(ev["start"])
        except (ValueError, KeyError, TypeError):
            continue
        if not rec:
            if start <= first.date() <= end:
                out.append(ev)
            continue
        # walk occurrences forward from the first date until past `end`
        cursor = first
        guard = 0
        while cursor.date() <= end and guard < 800:
            if cursor.date() >= start:
                occ = dict(ev)
                occ["start"] = cursor.isoformat()
                if ev.get("end"):
                    try:
                        dur = dt.datetime.fromisoformat(ev["end"]) - first
                        occ["end"] = (cursor + dur).isoformat()
                    except ValueError:
                        pass
                occ["recurring_instance"] = True
                out.append(occ)
            nxt = next_occurrence(rec, cursor.date())
            if not nxt:
                break
            cursor = dt.datetime.combine(nxt, cursor.time())
            guard += 1
    return out
