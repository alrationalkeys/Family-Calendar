"""
A camera or the alarm panel dropping offline WHILE THE ALARM IS ARMED. Checked every minute by the house-watch loop.

Why: knocking Wi-Fi cameras off the network (or cutting power / internet) is what tampering looks like from the inside,
and the "Needs attention" card only helps if someone is looking at the wall. So: push the phones.

  - watched: every camera (not Blink: those sleep on battery and come and go) and the alarm panel itself
  - offline = "unavailable" for 2 checks in a row (about 2 minutes), so a blip or an HA restart doesn't page anyone
  - one push per outage per device; several at once are grouped into one push; a "back online" push when it returns
  - arming while a camera is already offline gets one heads-up too
Only tells; never changes anything. settings.offlineAlert (default on).
"""
from __future__ import annotations

import time
from datetime import datetime

from . import ha_svc

_S: dict = {"down": {}, "told": {}, "armed_at": 0.0, "was_armed": None, "panel_back": 0.0}
_GRACE = 100            # seconds unavailable before it counts
_RESTART_GRACE = 420    # after the panel itself was unavailable (Home Assistant restarting), cameras get longer to return


def _name(st: dict) -> str:
    return str((st.get("attributes") or {}).get("friendly_name") or st.get("entity_id", "")).strip()


def _watched(states: list) -> list:
    out = []
    for st in states:
        eid = st.get("entity_id", "")
        dom = eid.split(".", 1)[0]
        if dom not in ("camera", "alarm_control_panel"):
            continue
        try:
            if ha_svc.is_blink(eid, st.get("attributes") or {}):
                continue
        except Exception:
            pass
        out.append(st)
    return out


def tick(settings: dict, states: list, push):
    if settings.get("offlineAlert", True) is False or not states:
        _S["down"].clear()
        return
    now = time.time()
    panels = [s for s in states if s.get("entity_id", "").startswith("alarm_control_panel.")]
    if any(str(s.get("state", "")).startswith("armed") for s in panels):
        _S["armed_at"] = now
    # the panel itself going dark hides the armed state: trust what we saw in the last 15 minutes
    armed = now - _S["armed_at"] < 900 and (any(str(s.get("state", "")).startswith("armed") for s in panels)
                                            or all(s.get("state") in ("unavailable", "unknown") for s in panels))
    first = _S["was_armed"] is None                     # FamilyHub just started: learn the state, don't announce it
    just_armed = armed and _S["was_armed"] is False
    _S["was_armed"] = armed
    if any(s.get("state") in ("unavailable", "unknown") for s in panels):
        _S["panel_back"] = now                          # HA or the alarm link is restarting
    grace = _RESTART_GRACE if now - _S["panel_back"] < _RESTART_GRACE else _GRACE

    fresh, back = [], []
    for st in _watched(states):
        eid = st["entity_id"]
        if st.get("state") == "unavailable":
            new_here = eid not in _S["down"]
            since = _S["down"].setdefault(eid, now)
            if first and new_here:
                _S["told"][eid] = since                 # already offline when FamilyHub started: not news
                continue
            if armed and eid not in _S["told"] and (now - since >= grace or just_armed):
                _S["told"][eid] = since
                fresh.append((st, since, just_armed and now - since >= _GRACE))
        else:
            _S["down"].pop(eid, None)
            if eid in _S["told"]:
                _S["told"].pop(eid)
                back.append(st)
    if not armed:
        _S["told"].clear()                          # disarmed: the wall's "Needs attention" card takes over
    if fresh:
        t = datetime.fromtimestamp(min(s for _, s, _ in fresh)).strftime("%-I:%M %p")
        names = [_name(st) for st, _, _ in fresh]
        panel = any(st["entity_id"].startswith("alarm_control_panel.") for st, _, _ in fresh)
        if all(old for _, _, old in fresh):
            text = f"Heads up: the alarm is armed but {_join(names)} {'is' if len(names) == 1 else 'are'} offline (since {t})."
        elif len(fresh) == 1:
            text = f"{names[0]} went offline at {t} while the alarm is armed."
        else:
            text = (f"{len(fresh)} devices went offline together at {t} while the alarm is armed: {_join(names)}. "
                    "That can be the Wi-Fi or power, or someone interfering. Worth a look.")
        push(("🚨 " if panel or len(fresh) > 1 else "📷 ") + text, "familyhub-offline")
    if back and armed:
        push(f"✅ Back online: {_join([_name(s) for s in back])}.", "familyhub-offline")


def _join(names: list) -> str:
    names = names[:6]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
