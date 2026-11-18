"""
Monthly house report. Home Assistant only keeps about 10 days of history, so one line per day is saved as it goes
(settings row `house_days`: heat / AC minutes, heat-AC minutes inside peak hours, washer / dryer loads) and the report is
added up from those. On the 1st at 09:00 the phones get last month's summary (settings.monthlyReport);
`GET /api/ha/report?month=YYYY-MM` gives the same for any month (default: this month so far).
"""
from __future__ import annotations

import calendar
import json
import threading
from datetime import date, datetime, timedelta

from ..db import get_db

_S: dict = {"recorded": None}
_LOCK = threading.RLock()        # the daily catch-up and a laundry bump both rewrite the same row


def _load() -> dict:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key='house_days'").fetchone()
    try:
        return json.loads(row["value"]) if row and row["value"] else {}
    except Exception:
        return {}


def _save(days: dict):
    keep = (date.today() - timedelta(days=800)).isoformat()
    days = {k: v for k, v in days.items() if k >= keep}
    with get_db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('house_days', ?)", (json.dumps(days),))


def bump(key: str, n: int = 1):
    """Count something that happened today (a washer / dryer load)."""
    try:
        with _LOCK:
            days = _load()
            d = days.setdefault(date.today().isoformat(), {})
            d[key] = int(d.get(key, 0)) + n
            _save(days)
    except Exception:
        pass


def record(day: date, days: dict) -> bool:
    """Save one finished day's heat/AC numbers from the Today timeline. False when HA had nothing."""
    from . import timeline
    r = timeline.get(day.isoformat())
    if not (r and r.get("ok")):
        return False
    st = r.get("stats") or {}
    d = days.setdefault(day.isoformat(), {})
    d.update(heat=int(st.get("heat_min", 0) or 0), cool=int(st.get("cool_min", 0) or 0),
             peak=int(st.get("hvac_peak_min", 0) or 0), ok=1)
    return True


def catch_up(limit: int = 9) -> int:
    """Yesterday (and up to 8 earlier days still missing, e.g. the wall was off) into the store. A day of history is a
    heavy question for Home Assistant, so the minute-by-minute loop asks for ONE day at a time (limit=1)."""
    fresh: dict = {}                               # the slow part (asking HA) happens outside the lock
    have = _load()
    for i in range(1, 10):
        d = date.today() - timedelta(days=i)
        if not (have.get(d.isoformat()) or {}).get("ok") and d.isoformat() not in _S.setdefault("tried", set()):
            _S["tried"].add(d.isoformat())         # a day HA no longer has is asked for once, not every minute
            try:
                record(d, fresh)
            except Exception:
                pass
            if len(_S["tried"]) and limit <= 1:
                break
    if fresh:
        with _LOCK:
            days = _load()                         # re-read: a laundry count may have landed meanwhile
            for k, v in fresh.items():
                days.setdefault(k, {}).update(v)
            _save(days)
    return len(fresh)


def _month_of(m: str | None) -> str:
    try:
        return datetime.strptime(m or "", "%Y-%m").strftime("%Y-%m")
    except ValueError:
        return date.today().strftime("%Y-%m")


def _prev(m: str) -> str:
    y, mo = int(m[:4]), int(m[5:7])
    return f"{y - 1}-12" if mo == 1 else f"{y}-{mo - 1:02d}"


def _sum(days: dict, m: str) -> dict:
    rows = {k: v for k, v in days.items() if k.startswith(m)}
    counted = [v for v in rows.values() if v.get("ok")]
    t = lambda key, src=None: sum(int(v.get(key, 0) or 0) for v in (src if src is not None else rows.values()))
    out = {"days": len(counted), "heat_h": round(t("heat", counted) / 60, 1), "cool_h": round(t("cool", counted) / 60, 1),
           "peak_min": t("peak", counted), "washer": t("washer"), "dryer": t("dryer")}
    busiest = max(((k, int(v.get("heat", 0)) + int(v.get("cool", 0))) for k, v in rows.items() if v.get("ok")), key=lambda x: x[1], default=None)
    out["busiest"] = {"day": busiest[0], "hours": round(busiest[1] / 60, 1)} if busiest and busiest[1] else None
    return out


def _ai_cost(m: str) -> float:
    try:
        with get_db() as conn:
            return float(conn.execute("SELECT COALESCE(SUM(cost),0) c FROM ai_usage WHERE at LIKE ?", (m + "%",)).fetchone()["c"])
    except Exception:
        return 0.0


def _peak_slips(m: str) -> list:
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='peak_log'").fetchone()
        return [x for x in (json.loads(row["value"]) if row and row["value"] else []) if str(x.get("day", "")).startswith(m)]
    except Exception:
        return []


def _vs(now: float, before: float, unit: str = "h") -> str:
    if not before:
        return ""
    diff = now - before
    if abs(diff) < max(1.0, before * 0.05):
        return " (about the same as the month before)"
    return f" ({abs(diff):.0f} {unit} {'more' if diff > 0 else 'less'} than the month before)"


def report(month: str | None = None) -> dict:
    m = _month_of(month)
    days = _load()
    cur, prev = _sum(days, m), _sum(days, _prev(m))
    y, mo = int(m[:4]), int(m[5:7])
    in_month = calendar.monthrange(y, mo)[1]
    name = date(y, mo, 1).strftime("%B %Y")
    slips = _peak_slips(m)
    cost = _ai_cost(m)
    lines = []
    if not cur["days"]:
        lines.append("Nothing counted for this month yet. The first day is saved just after midnight.")
    else:
        part = "" if cur["days"] >= in_month else f" ({cur['days']} of {in_month} days counted)"
        full = prev["days"] >= 25 and cur["days"] >= 25                    # only compare two whole months
        lines.append(f"Heat ran about {cur['heat_h']:.0f} h{_vs(cur['heat_h'], prev['heat_h']) if full else ''}, "
                     f"AC about {cur['cool_h']:.0f} h{_vs(cur['cool_h'], prev['cool_h']) if full else ''}{part}.")
        if cur["busiest"]:
            b = date.fromisoformat(cur["busiest"]["day"])
            lines.append(f"Busiest day: {b.strftime('%a %b')} {b.day}, {cur['busiest']['hours']:.0f} h of heat/AC.")
        lines.append("No heat or AC during peak hours." if not cur["peak_min"]
                     else f"Heat/AC ran {cur['peak_min']} min during peak hours.")
    if slips:
        names = {}
        for x in slips:
            names[x.get("name", "?")] = names.get(x.get("name", "?"), 0) + 1
        lines.append("Peak alerts: " + ", ".join(f"{k} ×{v}" for k, v in names.items()) + ".")
    if cur["washer"] or cur["dryer"]:
        lines.append(f"Laundry: {cur['washer']} washer load{'s' if cur['washer'] != 1 else ''}, {cur['dryer']} dryer load{'s' if cur['dryer'] != 1 else ''}.")
    if cost:
        lines.append(f"AI questions cost about ${cost:.2f}." if cost >= 0.995 else f"AI questions cost about {cost * 100:.0f}¢.")
    return {"month": m, "name": name, "days": cur["days"], "days_in_month": in_month, "now": cur, "before": prev,
            "peak_alerts": slips, "ai_cost": round(cost, 4), "lines": lines, "text": f"🏠 {name}: " + " ".join(lines)}


def _sent_month(set_to: str | None = None) -> str:
    with get_db() as conn:
        if set_to:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('house_report_sent', ?)", (json.dumps(set_to),))
            return set_to
        row = conn.execute("SELECT value FROM settings WHERE key='house_report_sent'").fetchone()
    try:
        return json.loads(row["value"]) if row and row["value"] else ""
    except Exception:
        return ""


def tick(s: dict, now: datetime, push):
    """From the house-watch loop, every minute."""
    # one missing day per minute, starting five minutes after start-up, never all nine at once: that many history
    # questions in a row made Home Assistant too slow to answer the wall (Nov 18)
    _S["ticks"] = _S.get("ticks", 0) + 1
    if _S.get("day") != now.date():
        _S["day"], _S["tried"] = now.date(), set()
    if _S["ticks"] > 5 and not (now.hour == 0 and now.minute < 20) and len(_S.get("tried", ())) < 9:
        catch_up(limit=1)
    # from 9 AM on the 1st, and for two more days if the wall was off or the push failed; remembered across restarts
    month = _prev(now.strftime("%Y-%m"))
    if now.day <= 3 and 9 <= now.hour < 21 and s.get("monthlyReport", True) and _sent_month() != month:
        push(report(month)["text"], "familyhub-month")       # raises if it could not be sent: try again next minute
        _sent_month(month)
