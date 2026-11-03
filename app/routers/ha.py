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
from fastapi import APIRouter, HTTPException
from ..services import ha_svc

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
