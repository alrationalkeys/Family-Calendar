"""Home Assistant endpoints — the FamilyHub "Home" tab.

    GET  /api/ha/status      lightweight: connected? demo? alarm state, open doors
    GET  /api/ha/home        full grouped tile list for the Home tab
    POST /api/ha/toggle      {entity_id}            flip a light/switch/cover/lock, run a scene
    POST /api/ha/service     {domain, service, entity_id?, data?}  escape hatch
    POST /api/ha/alarm       {action: arm_home|arm_away|disarm, code}  alarm w/ PIN

FamilyHub talks only to Home Assistant (separate Pi); HA talks to the gear. See
app/services/ha_svc.py and docs/home-assistant-setup.md. Works in demo mode out
of the box so the Home tab is explorable before real HA exists.
"""
import json
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from ..services import doorbell, ha_svc, ha_live, house_modes

router = APIRouter()


@router.get("/status")
def status():
    return ha_svc.status()


@router.get("/home")
def home():
    return ha_svc.get_home()


@router.post("/toggle")
def toggle(payload: dict):
    eid = (payload or {}).get("entity_id", "")
    if not eid:
        raise HTTPException(400, "entity_id required")
    return ha_svc.toggle(eid)


@router.post("/service")
def service(payload: dict):
    p = payload or {}
    domain, svc = p.get("domain"), p.get("service")
    if not domain or not svc:
        raise HTTPException(400, "domain and service required")
    return ha_svc.call_service(domain, svc, p.get("entity_id", ""), p.get("data") or {})


@router.post("/media")
def media(payload: dict):
    """On-screen Roku remote. {entity_id, action, value?} where action is
    power|vol_up|vol_down|mute|play_pause|app|up|down|left|right|ok|back|home."""
    p = payload or {}
    eid, action = p.get("entity_id", ""), p.get("action", "")
    if not eid or not action:
        raise HTTPException(400, "entity_id and action required")
    return ha_svc.media(eid, action, p.get("value", ""))


@router.get("/media_info")
def media_info(entity_id: str):
    """The TV's installed channels + current source/power/mute, for the remote."""
    if not entity_id:
        raise HTTPException(400, "entity_id required")
    return ha_svc.media_info(entity_id)


@router.get("/version")
def version():
    """Monotonic counter that bumps on every HA state change (live WebSocket
    mirror, or demo toggles). Cheap to poll if SSE isn't available."""
    return {"version": ha_live.version(), "live": ha_live.connected(), "demo": ha_svc.demo_mode()}


@router.get("/events")
async def events():
    """Server-Sent Events: one line per HA state change (plus a heartbeat every
    25 s). The wall re-renders the Home tab / status bar the moment something flips."""
    async def gen():
        v = ha_live.version()
        yield f"data: {json.dumps({'version': v, 'live': ha_live.connected(), 'ring': doorbell.last_at()})}\n\n"
        while True:
            nv = await ha_live.wait_for_change(v, timeout=25.0)
            if nv != v:
                v = nv
                yield f"data: {json.dumps({'version': v, 'live': ha_live.connected(), 'ring': doorbell.last_at()})}\n\n"
            else:
                yield ": keepalive\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/spotify")
def spotify():
    """Now-playing + devices for the Home tab's Spotify card (null if HA has no
    Spotify player)."""
    return {"spotify": ha_svc.spotify_state()}


@router.post("/spotify")
def spotify_cmd(payload: dict):
    """{action: play_pause|next|prev|volume|source|shuffle|play, value?, kind?}
    play's value is a Spotify URI (spotify:playlist:...); kind overrides the
    media_content_type guessed from the URI (browse results supply it)."""
    p = payload or {}
    if not p.get("action"):
        raise HTTPException(400, "action required")
    return ha_svc.spotify_cmd(p["action"], str(p.get("value", "") or ""), str(p.get("kind", "") or ""))


@router.get("/spotify/browse")
def spotify_browse(id: str = "", type: str = ""):
    """Browse the Spotify library through HA (playlists, recently played, albums…).
    No args = root. Returns {title, children:[{title, id, type, can_play, can_expand, thumb}]}."""
    return ha_svc.spotify_browse(id or None, type or None)


@router.get("/camera/{entity_id}")
def camera(entity_id: str):
    """Current snapshot from a camera, proxied through HA with the server-side token
    (cached ~4 s). The phone, the wall, the 3D pins and the Roku flash all load this."""
    got = ha_svc.camera_snapshot(entity_id)
    if not got:
        raise HTTPException(404, "no snapshot")
    data, ctype = got
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "no-store"})


@router.get("/webrtc/{entity_id}")
def camera_webrtc(entity_id: str):
    """Live-stream credentials for an Alarm.com camera (short-lived; never cached)."""
    cfg = ha_svc.camera_webrtc_config(entity_id)
    if not cfg:
        raise HTTPException(404, "no live stream for this camera")
    return cfg


@router.get("/doorbell")
def doorbell_state():
    """Last ring/motion: {at, kind, camera, name, where}. at=0 means never."""
    return doorbell.last()


@router.post("/doorbell/test")
def doorbell_test(payload: dict | None = None):
    """Simulate a ring to check the wall pop-up, phone push and TV flash."""
    return doorbell.test_ring((payload or {}).get("kind", "doorbell"))


@router.post("/mode")
def mode(payload: dict):
    """One-tap house modes: {mode: goodnight|away|welcome, who?, close_garage?, arm?, source?}.
    Returns what was done + warnings + a sentence the wall speaks."""
    p = payload or {}
    return house_modes.run(p.get("mode", ""), who=p.get("who"), close_garage=(None if p.get("close_garage") is None else bool(p.get("close_garage"))),
                           arm=p.get("arm", True) is not False, source=p.get("source", "wall"),
                           code=(str(p["code"]) if p.get("code") else None), open_garage=bool(p.get("open_garage")))


@router.get("/presence")
def presence():
    """Who's home (HA person.* from the companion app)."""
    return {"people": house_modes.presence()}


@router.get("/art")
def art(entity_id: str):
    """Album art proxied through HA with the server-side token."""
    got = ha_svc.entity_picture(entity_id)
    if not got:
        raise HTTPException(404, "no picture")
    data, ctype = got
    return Response(content=data, media_type=ctype, headers={"Cache-Control": "max-age=30"})


@router.post("/alarm")
def alarm(payload: dict):
    """Arm/disarm the Qolsys IQ Panel. Disarm (and typically arm) need the panel
    code — the frontend collects it on a PIN pad and sends it here; the code is
    passed straight to HA and never stored."""
    p = payload or {}
    action = p.get("action")
    code = str(p.get("code", "") or "")
    svc = {"arm_home": "alarm_arm_home", "arm_away": "alarm_arm_away",
           "arm_night": "alarm_arm_night", "disarm": "alarm_disarm"}.get(action)
    if not svc:
        raise HTTPException(400, "action must be arm_home|arm_away|arm_night|disarm")
    if action == "disarm" and not code:
        raise HTTPException(400, "code required to disarm")
    # find the alarm entity (there's normally just one)
    eid = p.get("entity_id", "")
    if not eid:
        for grp in ha_svc.get_home().get("groups", []):
            for t in grp["tiles"]:
                if t["domain"] == "alarm_control_panel":
                    eid = t["entity_id"]; break
            if eid: break
    if not eid:
        raise HTTPException(404, "no alarm panel found")
    extra = {"code": code} if code else {}
    return ha_svc.call_service("alarm_control_panel", svc, eid, extra)


# ---- Automations page (phone + wall): see, switch and tune the Home Assistant routines -------------
@router.get("/automations")
def automations_list():
    from ..services import automations
    return automations.list_all()


@router.post("/automations/toggle")
def automations_toggle(payload: dict):
    from ..services import automations
    return automations.set_automation(str((payload or {}).get("entity_id", "")), bool((payload or {}).get("on")))


@router.get("/automations/routine/{rid}")
def routine_get(rid: str):
    from ..services import automations
    return automations.get_routine(rid)


@router.post("/automations/routine")
def routine_save(payload: dict):
    from ..services import automations
    p = payload or {}
    return automations.save_routine(p.get("spec") or {}, p.get("id"))


@router.delete("/automations/routine/{rid}")
def routine_delete(rid: str):
    from ..services import automations
    return automations.delete_routine(rid)


@router.post("/automations/setting")
def automations_setting(payload: dict):
    from ..services import automations
    p = payload or {}
    return automations.set_helper(str(p.get("entity_id", "")), p.get("value"))
