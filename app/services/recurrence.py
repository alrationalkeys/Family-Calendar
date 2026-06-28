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


def _parse_rec(rec: str):
    """Split a recurrence string into (base, modifiers).
    Format: '<base>[;count=N][;until=YYYY-MM-DD][;exmonths=6,7]'
    e.g. 'weekly;count=3'  ·  'monthly;until=2026-12-31'  ·  'daily;exmonths=6,7,8'."""
    if not rec:
        return "", {}
    parts = rec.split(";")
    base = parts[0].strip().lower()
    mods = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            mods[k.strip().lower()] = v.strip()
    return base, mods


def next_occurrence(rec: str, from_date: dt.date) -> dt.date | None:
    if not rec:
        return None
    rec = rec.split(";")[0].strip().lower()   # ignore count/until/exmonths modifiers
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
        base, mods = _parse_rec(rec)
        count = int(mods["count"]) if mods.get("count", "").isdigit() else None
        try:
            until = dt.date.fromisoformat(mods["until"]) if mods.get("until") else None
        except ValueError:
            until = None
        exmonths = {int(x) for x in mods["exmonths"].split(",") if x.strip().isdigit()} if mods.get("exmonths") else set()
        # walk occurrences forward from the first date; idx counts cadence slots
        cursor = first
        guard = 0
        idx = 0
        while cursor.date() <= end and guard < 800:
            if count is not None and idx >= count:
                break
            if until and cursor.date() > until:
                break
            if cursor.date() >= start and cursor.month not in exmonths:
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
            nxt = next_occurrence(base, cursor.date())
            if not nxt:
                break
            cursor = dt.datetime.combine(nxt, cursor.time())
            guard += 1
            idx += 1
    return out
