"""Intercom: a phone types a message, the wall says it out loud.
    POST /api/announce {text}  -> queued as a notification the wall speaks + shows."""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..db import get_db

router = APIRouter()


class Announce(BaseModel):
    text: str
    who: str | None = None     # optional sender name shown on the banner


@router.post("")
def announce(a: Announce):
    text = (a.text or "").strip()[:300]
    if not text:
        raise HTTPException(400, "text required")
    title = f"\U0001F4E2 From {a.who.strip()}" if a.who and a.who.strip() else "\U0001F4E2 Announcement"
    with get_db() as conn:
        cur = conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                           (title, text, "announce", datetime.now().isoformat()))
    return {"id": cur.lastrowid, "ok": True}
