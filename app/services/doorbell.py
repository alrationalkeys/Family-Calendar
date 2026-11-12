"""
Doorbell + camera-motion events -> the wall, the phones and the TVs.

Fed by ha_live (every HA state change passes through on_state). A "ring" is any
binary_sensor / event entity whose name or id mentions doorbell|ring|chime|button
turning on (or, for `event` entities, changing at all). "Motion" is a camera's own
motion sensor (name shares the camera's name) turning on — quieter: banner only.

What happens on a ring (all optional, settings.ui):
  - the wall learns about it on the next SSE message (ring timestamp rides along) and
    pops the snapshot full-screen with a chime; doorbellSpeak (default on) says it
  - every phone gets a push with the picture (pushAdds channel)
  - doorbellTv (default on): every Roku that's switched on shows the snapshot via
    HA's media_player.play_media for ~20 s
Snapshots are served by FamilyHub (/api/ha/camera/<eid>) so phones/TVs never need the
HA token. FAMILYHUB_URL (env) is the LAN address they load it from; default = this box.
"""
from __future__ import annotations

import os
import re
import socket
import threading
import time

_last = {"at": 0.0, "kind": "", "camera": "", "name": "", "where": "", "source": ""}
_cooldown = {}        # entity_id -> last fire time


def last() -> dict:
    return {**_last, "tv_flashes": _TV_LOG[-10:]}


def last_at() -> float:
    return _last["at"]


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def base_url() -> str:
    u = os.getenv("FAMILYHUB_URL", "").rstrip("/")
    if u:
        return u
    ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close()
    except Exception:
        pass
    return f"http://{ip}:{os.getenv('PORT', '8000')}"


# whole words only: plain "ring" used to match names like "monitoring", so any such sensor flipping
# fired a fake ring (and switched every Roku that was on to the doorbell picture)
_RING = re.compile(r"doorbell|door_bell|door bell|door.{0,12}button|(?<![a-z])(ring|chime)(?![a-z])", re.I)
_TV_LOG: list = []        # last Roku flashes: [{at, tv, source}]  -> GET /api/ha/doorbell
_lc = lambda s: str(s or "").lower()


def _find_camera(states: dict, hint_name: str, hint_id: str) -> tuple[str, str]:
    """Pick the camera that belongs with a ring/motion sensor: same name stem, else
    anything 'front'/'door'/'bell' in its name, else the first camera."""
    cams = [(eid, (st.get("attributes") or {}).get("friendly_name", eid)) for eid, st in states.items() if eid.startswith("camera.")]
    if not cams:
        return "", ""
    stem = re.sub(r"(doorbell|door bell|button|ring|chime|motion|sensor)", "", _lc(hint_name)).strip()
    for eid, nm in cams:
        if stem and (stem in _lc(nm) or _lc(nm) in stem or _lc(nm).split()[0] in stem):
            return eid, nm
    for eid, nm in cams:
        if re.search(r"front|door|bell|entry|porch", _lc(nm) + " " + eid):
            return eid, nm
    return cams[0]


def on_state(eid: str, old: dict | None, new: dict | None, states: dict):
    """Called by ha_live for every state change. Never raises."""
    try:
        if not new or not eid:
            return
        dom = eid.split(".", 1)[0]
        attrs = new.get("attributes") or {}
        from . import ha_svc
        if ha_svc.is_blink(eid, attrs):      # Blink is view-only: no pop-ups on motion
            return
        name = attrs.get("friendly_name", eid)
        ns, os_ = _lc(new.get("state")), _lc((old or {}).get("state"))
        kind = None
        if dom in ("binary_sensor", "event") and _RING.search(name + " " + eid) and not re.search(r"motion", _lc(name)):
            if dom == "event":
                if old and ns != os_:
                    kind = "doorbell"
            elif ns == "on" and os_ != "on":
                kind = "doorbell"
        elif dom == "binary_sensor" and attrs.get("device_class") in ("motion", "occupancy") and ns == "on" and os_ != "on":
            # only motion that belongs to a camera (name stem matches one)
            cam, _ = _find_camera(states, name, eid)
            stem = re.sub(r"(motion|sensor|occupancy)", "", _lc(name)).strip()
            if cam and stem and stem in _lc((states.get(cam) or {}).get("attributes", {}).get("friendly_name", "")):
                kind = "motion"
        if not kind:
            return
        now = time.time()
        if now - _cooldown.get(eid, 0) < (8 if kind == "doorbell" else 90):
            return
        _cooldown[eid] = now
        cam, cam_name = _find_camera(states, name, eid)
        where = re.sub(r"(doorbell|door bell|button|ring|chime|motion|sensor|camera)", "", name, flags=re.I).strip() or "the door"
        _last.update({"at": now, "kind": kind, "camera": cam, "name": cam_name or name, "where": where, "source": eid})
        threading.Thread(target=_fanout, args=(kind, cam, where), daemon=True).start()
    except Exception:
        pass


def _fanout(kind: str, cam: str, where: str):
    """Queue the wall banner, push the phones, flash the TVs."""
    from datetime import datetime
    from ..db import get_db
    from . import ha_svc, ha_live
    s = _settings()
    title = "🔔 Doorbell" if kind == "doorbell" else f"🎥 Motion at {where}"
    body = f"Someone's at the {where}." if kind == "doorbell" else f"Motion at the {where}."
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                         (title, body, kind, datetime.now().isoformat()))
    except Exception:
        pass
    img = f"{base_url()}/api/ha/camera/{cam}?t={int(time.time())}" if cam else None
    if kind == "doorbell" and s.get("pushAdds", True):
        try:
            services = ha_svc._request("/api/services") or []
            for dom in services:
                if dom.get("domain") != "notify":
                    continue
                for svc in (dom.get("services") or {}):
                    if svc.startswith("mobile_app_"):
                        data = {"tag": "familyhub-doorbell", "group": "familyhub", "push": {"interruption-level": "time-sensitive"}}
                        if img:
                            data["image"] = img; data["attachment"] = {"url": img, "content-type": "jpeg"}
                        try:
                            ha_svc.call_service("notify", svc, "", {"title": "Doorbell", "message": body, "data": data})
                        except Exception:
                            continue
        except Exception:
            pass
    if kind == "doorbell" and s.get("doorbellTv", True) and img:
        try:
            for st in (ha_live.states() or []):
                eid = st.get("entity_id", "")
                if not eid.startswith("media_player."):
                    continue
                a = st.get("attributes") or {}
                if "roku" not in _lc(eid) + _lc(a.get("friendly_name")) + _lc(a.get("manufacturer")):
                    continue
                if st.get("state") in ("off", "unavailable", "standby", None):
                    continue           # don't wake a TV that's off
                _TV_LOG.append({"at": time.time(), "tv": a.get("friendly_name") or eid, "source": _last.get("source", "")})
                del _TV_LOG[:-20]
                try:
                    ha_svc.call_service("media_player", "play_media", eid,
                                        {"media_content_type": "url", "media_content_id": img,
                                         "extra": {"format": "jpg", "name": "Doorbell"}})
                except Exception:
                    continue
        except Exception:
            pass


def test_ring(kind: str = "doorbell"):
    """Simulate a ring (phone Settings button / demo)."""
    from . import ha_live, ha_svc
    states = {s["entity_id"]: s for s in (ha_live.states() or [])}
    if not states and ha_svc.demo_mode():
        states = {k: {"entity_id": k, **v} for k, v in ha_svc._DEMO.items()}
    cam, cam_name = _find_camera(states, "front door doorbell", "binary_sensor.front_door_doorbell")
    now = time.time()
    _last.update({"at": now, "kind": kind, "camera": cam, "name": cam_name or "Front door", "where": "front door"})
    threading.Thread(target=_fanout, args=(kind, cam, "front door"), daemon=True).start()
    ha_live.bump()
    return last()
