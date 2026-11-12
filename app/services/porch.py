"""
Package on the porch: when a front camera sees motion (or the doorbell rings), wait for the visitor to
leave, grab a snapshot and ask a small, cheap Claude vision model whether a parcel is sitting there.

  new package      -> push to the phones with the picture + a wall banner ("📦 Package at the front door")
  still there 2 h  -> one reminder push
  gone             -> quietly cleared (someone brought it in)

Cameras: any camera whose name has front/porch/door/doorbell/entry/driveway in it (settings.packageCameras
can list entity ids instead). Needs ANTHROPIC_API_KEY; without it this does nothing. settings.packageAlerts
turns it off. Model: FAMILYHUB_PACKAGE_MODEL (default claude-haiku-5-5, a fraction of a cent per check).
"""
from __future__ import annotations

import base64
import json
import os
import re
import threading
import time

_STATE: dict = {}      # cam -> {"present": bool, "since": t, "last_check": t, "reminded": bool}
_LOCK = threading.Lock()
_NAMES = re.compile(r"front|porch|door|doorbell|entry|driveway|walkway", re.I)
_PROMPT = ("This is a still from a home security camera. Is there a delivered package, parcel, box, padded envelope "
           "or delivery bag left on the ground, porch, step or doormat? Ignore cars, bins, furniture, decorations "
           "and anything a person is still holding. Reply with JSON only: {\"package\": true|false, \"what\": \"short "
           "description or empty\"}")


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def watches(cam: str, cam_name: str) -> bool:
    s = _settings()
    if s.get("packageAlerts", True) is False or not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    listed = s.get("packageCameras") or []
    if listed:
        return cam in listed
    return bool(cam and _NAMES.search(f"{cam} {cam_name}"))


def _ask(cam: str):
    """True / False from the vision model, or None when it couldn't tell."""
    from . import ha_svc
    snap = ha_svc.camera_snapshot(cam, max_age=0)
    if not snap or not snap[1].startswith("image/") or "svg" in snap[1]:
        return None, ""
    data, ctype = snap
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=os.environ.get("FAMILYHUB_PACKAGE_MODEL") or "claude-haiku-5-5", max_tokens=120,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": ctype.split(";")[0],
                                             "data": base64.b64encode(data).decode()}},
                {"type": "text", "text": _PROMPT}]}])
        raw = "".join(b.text for b in resp.content if b.type == "text")
        m = re.search(r"\{.*\}", raw, re.S)
        j = json.loads(m.group(0)) if m else {}
        return bool(j.get("package")), str(j.get("what") or "")[:80]
    except Exception:
        return None, ""


def _where(cam_name: str) -> str:
    w = re.sub(r"(camera|cam|doorbell|video)", "", cam_name or "", flags=re.I).strip()
    return "front door" if w.lower() in ("", "front", "door", "front door", "porch") else w


def check(cam: str, cam_name: str, delay: float = 25):
    """Run in a thread after motion: wait, look, notify on a change."""
    time.sleep(delay)                              # let the driver walk away
    with _LOCK:
        st = _STATE.setdefault(cam, {"present": False, "since": 0, "last_check": 0, "reminded": False})
        if time.time() - st["last_check"] < 90:
            return
        st["last_check"] = time.time()
    found, what = _ask(cam)
    if found is None:
        return
    with _LOCK:
        was = st["present"]
        st["present"] = found
        if found and not was:
            st["since"], st["reminded"] = time.time(), False
    if found and not was:
        _notify(cam, f"📦 Package at the {_where(cam_name)}" + (f": {what}" if what else "") + ".", "familyhub-package")
        threading.Thread(target=_reminder, args=(cam, cam_name, st["since"]), daemon=True).start()


def _reminder(cam: str, cam_name: str, since: float):
    time.sleep(2 * 3600)
    st = _STATE.get(cam) or {}
    if not st.get("present") or st.get("since") != since or st.get("reminded"):
        return
    found, _ = _ask(cam)                           # look again before nagging
    if found:
        st["reminded"] = True
        _notify(cam, f"📦 The package is still at the {_where(cam_name)}.", "familyhub-package")
    elif found is False:
        st["present"] = False


def _notify(cam: str, text: str, tag: str):
    from datetime import datetime
    from ..db import get_db
    from . import ha_svc
    from .doorbell import base_url
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                         ("📦 Package", text, "package", datetime.now().isoformat()))
    except Exception:
        pass
    img = f"{base_url()}/api/ha/camera/{cam}?t={int(time.time())}"
    try:
        for dom in ha_svc._request("/api/services") or []:
            if dom.get("domain") == "notify":
                for svc in (dom.get("services") or {}):
                    if svc.startswith("mobile_app_"):
                        ha_svc.call_service("notify", svc, "", {"title": "FamilyHub", "message": text, "data": {
                            "tag": tag, "image": img, "attachment": {"url": img, "content-type": "jpeg"}}})
    except Exception:
        pass


def status() -> dict:
    return {cam: {"present": v["present"], "since": v["since"]} for cam, v in _STATE.items()}
