"""
Outside power lost: the outdoor GFCI tripped (rain / a wet bulb or plug), taking the porch lights, the exterior smart
plug, the Govee on the outdoor outlet and the Christmas display down together. Checked every minute by the house-watch
loop.

  watched   the lights that open the village (settings.villageOpenLights, else the nightly + holiday outdoor lists),
            the Christmas display plug, and any light/plug named like an outside one (porch, exterior, driveway...)
  tripped   at least 2 of them "unavailable" for 2+ minutes (1 if only one is watched), while the rest of the house's
            lights and plugs are mostly fine (so a Home Assistant restart or a Wi-Fi outage isn't called a GFCI)
  then      one push per outage naming what went dark; a "back on" push when they return
Only tells; never changes anything. settings.outdoorPowerAlert (default on). The Christmas plug's own offline push
(xmas.py) stands down for plugs watched here, so nobody gets two.
"""
from __future__ import annotations

import time

_S: dict = {"since": 0.0, "told": False, "names": [], "watched": set()}
_GRACE = 120


def _name(st: dict) -> str:
    return str((st.get("attributes") or {}).get("friendly_name") or st.get("entity_id", "")).strip()


def watched(states: list) -> list[str]:
    ids: list[str] = []
    try:
        from . import village
        ids += village.open_lights(states)
        outside = village._OUTSIDE
    except Exception:
        outside = None
    try:
        from . import xmas
        p = xmas.plug({x["entity_id"]: x for x in states})
        if p:
            ids.append(p)
    except Exception:
        pass
    if outside is not None:
        for st in states:
            eid = st.get("entity_id", "")
            if eid.split(".")[0] in ("light", "switch") and outside.search(eid.replace("_", " ") + " " + _name(st)) \
                    and "village" not in eid:
                ids.append(eid)
    seen, out = set(), []
    for e in ids:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def covers(eid: str) -> bool:
    """xmas.py asks: is this plug's offline push handled here?"""
    return eid in _S["watched"]


def tick(settings: dict, states: list, push):
    if settings.get("outdoorPowerAlert", True) is False or not states:
        _S.update(since=0.0, told=False, watched=set())
        return
    by = {x.get("entity_id"): x for x in states}
    ids = [e for e in watched(states) if e in by]
    _S["watched"] = set(ids)
    if not ids:
        return
    down = [e for e in ids if by[e].get("state") == "unavailable"]
    # the rest of the house: if lots of indoor lights/plugs are unavailable too, it's HA or the Wi-Fi, not the GFCI
    others = [x for x in states if x.get("entity_id", "").split(".")[0] in ("light", "switch") and x.get("entity_id") not in _S["watched"]]
    others_down = sum(1 for x in others if x.get("state") == "unavailable")
    house_ok = not others or others_down <= max(1, len(others) // 4)
    need = 2 if len(ids) >= 2 else 1
    now = time.time()
    if len(down) >= need and house_ok:
        _S["since"] = _S["since"] or now
        if not _S["told"] and now - _S["since"] >= _GRACE:
            _S["told"] = True
            _S["names"] = [_name(by[e]) for e in down]
            push("⚡ The outside power is off: " + _list(_S["names"]) + " went dark together. The outdoor GFCI outlet "
                 "probably tripped (water in a bulb or plug). Press Reset on it once things are dry.", "familyhub-gfci")
    elif len(down) < need:
        if _S["told"]:
            push("⚡ The outside power is back on (" + _list(_S["names"]) + ").", "familyhub-gfci")
        _S.update(since=0.0, told=False, names=[])


def _list(names: list) -> str:
    names = names[:5]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def status() -> dict:
    return {"watched": sorted(_S["watched"]), "down_since": _S["since"], "told": _S["told"]}
