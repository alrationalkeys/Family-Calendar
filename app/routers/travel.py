"""Leave-by countdown: GET /api/travel/next -> upcoming events with a place, how long the
drive is, and when to leave. The wall shows the soonest one and says it out loud at leave time."""
from datetime import datetime, timedelta

from fastapi import APIRouter

from ..services import travel

router = APIRouter()
LOOKAHEAD_H = 4          # only plan drives for events starting in the next few hours


def _parse(s: str):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone().replace(tzinfo=None) if d.tzinfo else d   # naive local time, like the rest of the app


@router.get("/next")
def next_trips(limit: int = 3):
    from .calendar import events as cal_events
    from .settings import get_settings
    s = get_settings() or {}
    if s.get("leaveAlerts") is False:
        return {"trips": [], "off": True}
    buffer = int(s.get("leaveBuffer") or 0)
    now = datetime.now()
    horizon = now + timedelta(hours=LOOKAHEAD_H)
    feed = cal_events(days=1).get("events", [])
    seen, trips = set(), []
    for e in sorted(feed, key=lambda x: x.get("start") or ""):
        loc = (e.get("location") or "").strip()
        if not loc or e.get("all_day"):
            continue
        st = _parse(e.get("start") or "")
        if not st or st <= now or st > horizon:
            continue
        k = (e.get("title"), e.get("start"))
        if k in seen:
            continue
        seen.add(k)
        d = travel.drive(loc)
        if not d:
            trips.append({"title": e.get("title"), "start": st.isoformat(timespec="minutes"), "location": loc, "minutes": None})
            continue
        leave = st - timedelta(minutes=d["minutes"] + buffer)
        trips.append({"title": e.get("title"), "start": st.isoformat(timespec="minutes"), "location": loc,
                      "minutes": d["minutes"], "traffic": d["traffic"], "source": d["source"],
                      "leave_at": leave.isoformat(timespec="minutes"), "buffer": buffer})
        if len(trips) >= limit:
            break
    trips.sort(key=lambda t: t.get("leave_at") or t["start"])
    return {"trips": trips, "origin_set": bool((s.get("homeAddress") or "").strip())}
