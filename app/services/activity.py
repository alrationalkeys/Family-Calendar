"""
"Rachell added Dentist for Ella, Thursday at 3" — tell the household when someone adds
something from a phone.

Two channels, both optional and both settings-driven (settings.ui):
  announceAdds   (default True)  the wall speaks it + shows a banner (via the existing
                                 notifications queue, kind=announce)
  pushAdds       (default True)  Home Assistant pushes it to the family's phones through
                                 the HA Companion app: every `notify.mobile_app_*` service
                                 except the sender's own phone (matched by name).

Who added it comes from the phone app's X-FH-Who header (Settings → "Your name on this
phone"). Nothing here ever raises into the request that created the item.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime

from ..db import get_db


def _settings() -> dict:
    try:
        from ..routers.settings import get_settings
        return get_settings() or {}
    except Exception:
        return {}


def _when(iso: str | None, all_day: bool = False) -> str:
    if not iso:
        return ""
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except Exception:
        return str(iso)
    today = datetime.now().date()
    day = "today" if d.date() == today else ("tomorrow" if (d.date() - today).days == 1 else d.strftime("%A %B %-d"))
    if all_day or (d.hour == 0 and d.minute == 0 and "T" not in str(iso)):
        return day
    return f"{day} at {d.strftime('%-I:%M %p').replace(':00 ', ' ')}"


def describe(kind: str, item: dict, person_name: str | None = None) -> str:
    """One spoken-friendly sentence fragment for the thing that was added."""
    t = (item.get("title") or item.get("item") or "").strip()
    who = f" for {person_name}" if person_name else ""
    if kind == "event":
        w = _when(item.get("start"), bool(item.get("all_day")))
        return f"{t}{who} to the calendar" + (f", {w}" if w else "")
    if kind == "todo":
        return f"{t} to {person_name + chr(39) + 's' if person_name else 'the'} to-do list"
    if kind == "grocery":
        q = item.get("qty")
        return f"{t}{' (' + str(q) + ')' if q else ''} to the groceries"
    if kind == "chore":
        return f"the chore {t}{who}"
    if kind == "meal":
        return f"{t} for {item.get('slot', 'dinner')} {_when(item.get('date'), True)}"
    return t


def _quiet_now(s: dict) -> bool:
    """Spoken announcements pause during quiet hours. Default = the screen-off night
    window (settings announceQuietStart/End override it, "" disables quiet hours)."""
    try:
        from . import display_svc
        cfg = display_svc.get_config()
        start = s.get("announceQuietStart") if s.get("announceQuietStart") is not None else cfg.get("off_start", "22:00")
        end = s.get("announceQuietEnd") if s.get("announceQuietEnd") is not None else cfg.get("off_end", "06:30")
        if not start or not end:
            return False
        return display_svc._in_night_window(datetime.now(), {"off_start": start, "off_end": end})
    except Exception:
        return False


def _person_name(conn, pid) -> str | None:
    if not pid:
        return None
    try:
        r = conn.execute("SELECT name FROM people WHERE id=?", (pid,)).fetchone()
        return (r["name"].split(" ")[0] if r and r["name"] else None)
    except Exception:
        return None


def record(kind: str, item: dict, who: str | None = None, source: str = "phone"):
    """Fire-and-forget. Call after the INSERT commits."""
    threading.Thread(target=_record, args=(kind, dict(item or {}), who, source), daemon=True).start()


def _record(kind: str, item: dict, who: str | None, source: str):
    try:
        s = _settings()
        with get_db() as conn:
            pname = _person_name(conn, item.get("person_id"))
            what = describe(kind, item, pname)
            if not what.strip():
                return
            who_clean = (who or "").strip()[:40]
            sentence = f"{who_clean} added {what}." if who_clean else f"Added {what}."
            if s.get("announceAdds", True) and source != "wall" and not _quiet_now(s):
                # the wall speaks announcements; don't echo back something typed on the wall itself
                conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                             (f"➕ {who_clean or 'Someone'} added", sentence, "announce", datetime.now().isoformat()))
        if s.get("pushAdds", True):
            _push(sentence, who_clean)
    except Exception:
        pass


def _push(text: str, sender: str):
    """Push through every HA mobile_app notifier except the sender's phone."""
    try:
        from . import ha_svc
        if ha_svc.demo_mode() or not ha_svc.ha_url():
            return
        services = ha_svc._request("/api/services") or []
        targets = []
        for dom in services:
            if dom.get("domain") != "notify":
                continue
            for name in (dom.get("services") or {}):
                if name.startswith("mobile_app_"):
                    targets.append(name)
        snd = re.sub(r"[^a-z0-9]", "", sender.lower())
        for svc in targets:
            owner = re.sub(r"[^a-z0-9]", "", svc.replace("mobile_app_", ""))
            if snd and (snd in owner or owner in snd):
                continue            # don't buzz the person who just added it
            try:
                ha_svc.call_service("notify", svc, "", {"title": "FamilyHub", "message": text,
                                                         "data": {"tag": "familyhub-add", "group": "familyhub"}})
            except Exception:
                continue
    except Exception:
        pass
