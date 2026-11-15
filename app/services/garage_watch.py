"""
Garage left open. Checked every minute by the house-watch loop.

  after dark (sun below the horizon): open for settings.garageOpenMin (15) minutes  -> push
  daytime:                            open for settings.garageOpenDayMin (0 = don't) -> push
  still open: one reminder every settings.garageRemindMin (30) minutes, then every time it would be the night check's job.

The push carries a "Close it" button (HA actionable notification, action FH_CLOSE_GARAGE). Tapping it comes back over
the WebSocket (ha_live -> on_action) and FamilyHub CLOSES the door. Closing only: nothing here can ever open it.
Settings: garageAlert (bool), garageOpenMin, garageOpenDayMin, garageRemindMin.
"""
from __future__ import annotations

import re
import threading
import time

from . import ha_svc

ACTION = "FH_CLOSE_GARAGE"
_GARAGE = re.compile(r"garage", re.I)
_S: dict = {"open_since": {}, "told_at": {}}


def _covers(states: list) -> list:
    """Garage door covers (the real door, e.g. MyQ through Alarm.com)."""
    out = []
    for st in states:
        eid, a = st.get("entity_id", ""), st.get("attributes") or {}
        if eid.startswith("cover.") and (a.get("device_class") == "garage" or _GARAGE.search(eid + " " + str(a.get("friendly_name", "")))):
            if not ha_svc.is_blink(eid, a):
                out.append(st)
    return out


def _dark(states: list) -> bool:
    sun = next((s for s in states if s.get("entity_id") == "sun.sun"), None)
    if sun:
        return sun.get("state") == "below_horizon"
    from datetime import datetime
    h = datetime.now().hour
    return h >= 18 or h < 6


def _push(text: str, with_button: bool):
    data = {"tag": "familyhub-garage"}
    if with_button:
        data["actions"] = [{"action": ACTION, "title": "Close it"}]
    try:
        for dom in ha_svc._request("/api/services") or []:
            if dom.get("domain") == "notify":
                for name in (dom.get("services") or {}):
                    if name.startswith("mobile_app_"):
                        ha_svc.call_service("notify", name, "", {"title": "FamilyHub", "message": text, "data": data})
    except Exception:
        pass


def tick(settings: dict, states: list):
    if settings.get("garageAlert", True) is False:
        _S["open_since"].clear()
        return
    now = time.time()
    night_min = max(1, int(settings.get("garageOpenMin") or 15))
    day_min = max(0, int(settings.get("garageOpenDayMin") or 0))
    again = max(10, int(settings.get("garageRemindMin") or 30))
    dark = _dark(states)
    for st in _covers(states):
        eid = st["entity_id"]
        if st.get("state") not in ("open", "opening"):
            if eid in _S["told_at"] and st.get("state") == "closed":
                pass
            _S["open_since"].pop(eid, None)
            _S["told_at"].pop(eid, None)
            continue
        since = _S["open_since"].setdefault(eid, now)
        limit = night_min if dark else day_min
        if not limit:
            continue
        mins = (now - since) / 60
        last = _S["told_at"].get(eid, 0)
        if mins >= limit and now - last >= again * 60:
            _S["told_at"][eid] = now
            name = (st.get("attributes") or {}).get("friendly_name") or "The garage door"
            _push(f"🚗 {name} has been open for {int(mins)} minutes" + (" and it's dark out." if dark else "."), True)


def on_action(event_data: dict):
    """A phone tapped a notification button (HA event mobile_app_notification_action). Close only."""
    if (event_data or {}).get("action") != ACTION:
        return
    threading.Thread(target=_close, daemon=True).start()


def _close():
    try:
        states = ha_svc._request("/api/states") or []
        doors = [s for s in _covers(states) if s.get("state") in ("open", "opening")]
        if not doors:
            _push("The garage door is already closed.", False)
            return
        for s in doors:
            ha_svc.call_service("cover", "close_cover", s["entity_id"])
        time.sleep(25)
        states = ha_svc._request("/api/states") or []
        still = [s for s in _covers(states) if s.get("state") in ("open", "opening")]
        _push("⚠️ The garage door didn't close. Something may be in the way: check it." if still else "✅ Garage door closed.", bool(still))
    except Exception:
        pass
