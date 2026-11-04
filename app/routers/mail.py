"""Email import inbox — review events pulled from forwarded emails, approve or
dismiss. See services/mail_import.py."""
import json
from fastapi import APIRouter, HTTPException
from ..db import get_db
from ..services import mail_import

router = APIRouter()


@router.get("/status")
def status():
    return {"configured": mail_import.configured()}


@router.get("/pending")
def pending():
    with get_db() as conn:
        rows = []
        for r in conn.execute("SELECT * FROM mail_imports WHERE status='pending' ORDER BY received DESC LIMIT 50"):
            d = dict(r)
            d["events"] = json.loads(d["events"] or "[]")
            rows.append(d)
    return {"pending": rows}


@router.post("/poll")
def poll_now():
    """Check the mailbox right now (the phone's 'Check now' button)."""
    return mail_import.poll()


@router.post("/{imp_id}/approve")
def approve(imp_id: int, payload: dict | None = None):
    """Create local events from an import. Optional payload {indexes:[...]} to
    approve only some of the found events; default all."""
    with get_db() as conn:
        r = conn.execute("SELECT * FROM mail_imports WHERE id=?", (imp_id,)).fetchone()
        if not r:
            raise HTTPException(404, "no such import")
        events = json.loads(r["events"] or "[]")
        idx = (payload or {}).get("indexes")
        chosen = [e for i, e in enumerate(events) if idx is None or i in idx]
        created = 0
        for e in chosen:
            if not e.get("title") or not e.get("start"):
                continue
            conn.execute(
                "INSERT INTO local_events (title,start,end,all_day,description,recurrence) VALUES (?,?,?,?,?,?)",
                (e["title"], e["start"], e.get("end"), int(bool(e.get("all_day"))),
                 (f"From email: {r['subject']}" + (f"\n{e['location']}" if e.get("location") else "")),
                 e.get("recurrence")))
            created += 1
        conn.execute("UPDATE mail_imports SET status='approved' WHERE id=?", (imp_id,))
    return {"id": imp_id, "created": created}


@router.post("/{imp_id}/dismiss")
def dismiss(imp_id: int):
    with get_db() as conn:
        conn.execute("UPDATE mail_imports SET status='dismissed' WHERE id=?", (imp_id,))
    return {"id": imp_id, "dismissed": True}
