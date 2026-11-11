"""
Live Home Assistant state via its WebSocket API.

Polling /api/states every time the Home tab opens is fine for a demo; a wall
that's always on wants the lights/doors/alarm to change the instant they
change. This keeps one WebSocket open to HA, mirrors every entity state in
memory, and bumps a version counter on each `state_changed`. ha_svc reads the
mirror instead of making a REST call when it's fresh, and /api/ha/events is a
Server-Sent-Events stream the wall subscribes to, so it re-renders within
~100 ms of a light flipping.

Never raises; if HA is unreachable it just retries with backoff and ha_svc
falls back to REST (or demo).
"""
from __future__ import annotations

import asyncio
import json
import os
import time

_states: dict[str, dict] = {}
_version = 0
_updated = 0.0
_connected = False
_cond: asyncio.Condition | None = None
_loop: asyncio.AbstractEventLoop | None = None


def states() -> list[dict] | None:
    """Mirror of HA's /api/states, or None if we aren't live (caller falls back)."""
    if not _connected or time.time() - _updated > 120:
        return None
    return list(_states.values())


def version() -> int:
    return _version


def connected() -> bool:
    return _connected


def bump():
    """Signal a change (used by demo-mode toggles so the wall refreshes too)."""
    global _version
    _version += 1
    if _loop and _cond:
        def _notify():
            async def go():
                async with _cond:
                    _cond.notify_all()
            asyncio.ensure_future(go())
        _loop.call_soon_threadsafe(_notify)


async def wait_for_change(since: int, timeout: float = 25.0) -> int:
    """Block until version > since (or timeout). Returns the current version."""
    if _cond is None:
        await asyncio.sleep(min(timeout, 2.0))
        return _version
    try:
        async with _cond:
            await asyncio.wait_for(_cond.wait_for(lambda: _version > since), timeout)
    except asyncio.TimeoutError:
        pass
    return _version


def _on_familyhub(data: dict):
    """A FamilyHub routine asked the wall to say something: queue it like a phone announcement."""
    if data.get("kind") != "say":
        return
    text = str(data.get("message") or "").strip()[:300]
    if not text:
        return
    try:
        from datetime import datetime
        from ..db import get_db
        with get_db() as conn:
            conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                         ("\U0001F3E0 Home", text, "announce", datetime.now().isoformat()))
    except Exception:
        pass


async def _run_once(ws_url: str, token: str):
    global _connected, _updated, _version
    import websockets
    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024, open_timeout=10) as ws:
        hello = json.loads(await ws.recv())
        if hello.get("type") != "auth_required":
            return
        await ws.send(json.dumps({"type": "auth", "access_token": token}))
        auth = json.loads(await ws.recv())
        if auth.get("type") != "auth_ok":
            await asyncio.sleep(60)      # bad token: don't hammer
            return
        await ws.send(json.dumps({"id": 1, "type": "get_states"}))
        await ws.send(json.dumps({"id": 2, "type": "subscribe_events", "event_type": "state_changed"}))
        # routines made in FamilyHub fire a "familyhub" event to make the wall speak
        await ws.send(json.dumps({"id": 3, "type": "subscribe_events", "event_type": "familyhub"}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=90))
            if msg.get("id") == 1 and msg.get("type") == "result":
                _states.clear()
                for s in msg.get("result") or []:
                    _states[s["entity_id"]] = s
                _connected = True
                _updated = time.time()
                _version += 1
                if _cond:
                    async with _cond:
                        _cond.notify_all()
            elif msg.get("type") == "event" and (msg.get("event") or {}).get("event_type") == "familyhub":
                _on_familyhub((msg.get("event") or {}).get("data") or {})
            elif msg.get("type") == "event":
                data = (msg.get("event") or {}).get("data") or {}
                new = data.get("new_state")
                eid = data.get("entity_id")
                if eid:
                    if new:
                        _states[eid] = new
                    else:
                        _states.pop(eid, None)
                    try:
                        from . import doorbell
                        doorbell.on_state(eid, data.get("old_state"), new, _states)
                    except Exception:
                        pass
                    if eid.startswith("alarm_control_panel."):
                        try:
                            from . import display_svc
                            display_svc.on_alarm((new or {}).get("state"), ((data.get("old_state") or {}).get("state")))
                        except Exception:
                            pass
                _updated = time.time()
                _version += 1
                if _cond:
                    async with _cond:
                        _cond.notify_all()
            elif msg.get("type") == "ping":
                await ws.send(json.dumps({"id": msg.get("id", 0), "type": "pong"}))


async def run_forever():
    """Background task started from the app lifespan."""
    global _cond, _loop, _connected
    _loop = asyncio.get_running_loop()
    _cond = asyncio.Condition()
    from . import ha_svc
    delay = 3
    while True:
        if ha_svc.demo_mode():
            _connected = False
            await asyncio.sleep(30)
            continue
        url = ha_svc.ha_url()
        ws_url = url.replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + "/api/websocket"
        try:
            await _run_once(ws_url, ha_svc.ha_token())
            delay = 3
        except Exception:
            pass
        _connected = False
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)
