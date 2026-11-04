"""
Email import — Skylight's "magic email" without the subscription.

Give the family a mailbox (a free Gmail like familyhub.smiths@gmail.com works
great), forward school newsletters / practice schedules / invites to it, and
FamilyHub turns them into events you approve with one tap on the phone.

Config (server-side only, in .env):
    FAMILYHUB_MAIL_HOST    imap.gmail.com | imap.mail.me.com | outlook.office365.com
    FAMILYHUB_MAIL_USER    the mailbox address
    FAMILYHUB_MAIL_PASS    an APP PASSWORD (Gmail: Google Account -> Security -> App passwords)
    FAMILYHUB_MAIL_FOLDER  INBOX (default)

Every 5 minutes: fetch UNSEEN mail, pull events out of it, store them as a
pending import, mark the mail seen. Two extractors:
  1. .ics attachments (calendar invites from Outlook/Google/TeamSnap) — parsed
     exactly with the icalendar lib, no AI needed.
  2. the message text — through ai_parse (needs ANTHROPIC_API_KEY); skipped
     silently without a key.
Nothing is added to the calendar until someone approves it in the phone app.
"""
from __future__ import annotations

import email
import email.policy
import html
import imaplib
import json
import os
import re
from datetime import datetime, date

from ..db import get_db


def configured() -> bool:
    return bool(os.getenv("FAMILYHUB_MAIL_HOST") and os.getenv("FAMILYHUB_MAIL_USER")
                and os.getenv("FAMILYHUB_MAIL_PASS"))


def _text_of(msg) -> str:
    """Best-effort plain text from a message (prefers text/plain, strips HTML)."""
    body = msg.get_body(preferencelist=("plain", "html"))
    if body is None:
        return ""
    txt = body.get_content()
    if body.get_content_type() == "text/html":
        txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", txt, flags=re.S | re.I)
        txt = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", txt, flags=re.I)
        txt = re.sub(r"<[^>]+>", " ", txt)
        txt = html.unescape(txt)
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip()[:12000]


def _ics_events(msg) -> list[dict]:
    out = []
    for part in msg.iter_attachments():
        ctype = part.get_content_type()
        name = (part.get_filename() or "").lower()
        if ctype not in ("text/calendar", "application/ics") and not name.endswith(".ics"):
            continue
        try:
            from icalendar import Calendar
            cal = Calendar.from_ical(part.get_content() if isinstance(part.get_content(), (bytes, str)) else part.get_payload(decode=True))
        except Exception:
            continue
        for comp in cal.walk("VEVENT"):
            try:
                st = comp.decoded("dtstart")
                en = comp.decoded("dtend") if comp.get("dtend") else None
                all_day = isinstance(st, date) and not isinstance(st, datetime)
                out.append({"title": str(comp.get("summary") or "Event"),
                            "start": st.isoformat(), "end": en.isoformat() if en else None,
                            "all_day": all_day, "recurrence": None,
                            "location": str(comp.get("location") or "") or None})
            except Exception:
                continue
    # inline text/calendar bodies (Google invites) aren't attachments
    if not out:
        for part in msg.walk():
            if part.get_content_type() == "text/calendar":
                try:
                    from icalendar import Calendar
                    cal = Calendar.from_ical(part.get_payload(decode=True))
                    for comp in cal.walk("VEVENT"):
                        st = comp.decoded("dtstart")
                        en = comp.decoded("dtend") if comp.get("dtend") else None
                        out.append({"title": str(comp.get("summary") or "Event"), "start": st.isoformat(),
                                    "end": en.isoformat() if en else None,
                                    "all_day": isinstance(st, date) and not isinstance(st, datetime),
                                    "recurrence": None})
                except Exception:
                    pass
    return out


def extract_events(msg) -> list[dict]:
    evs = _ics_events(msg)
    if evs:
        return evs
    if not os.getenv("ANTHROPIC_API_KEY"):
        return []
    text = _text_of(msg)
    if len(text) < 20:
        return []
    try:
        from . import ai_parse
        subj = str(msg.get("subject") or "")
        return ai_parse.parse_text_to_events(f"Subject: {subj}\n\n{text}") or []
    except Exception:
        return []


def _store(conn, uid: str, msg, events: list[dict]):
    subj = str(msg.get("subject") or "(no subject)")[:200]
    sender = str(msg.get("from") or "")[:200]
    conn.execute(
        "INSERT OR IGNORE INTO mail_imports (uid, subject, sender, received, events, status) VALUES (?,?,?,?,?,?)",
        (uid, subj, sender, datetime.now().isoformat(), json.dumps(events),
         "pending" if events else "empty"))
    if events:
        conn.execute("INSERT INTO notifications (title, body, kind, at) VALUES (?,?,?,?)",
                     (f"\U0001F4E8 {len(events)} event{'s' if len(events) != 1 else ''} found in email",
                      f"{subj} — approve on your phone", "mail", datetime.now().isoformat()))


def poll() -> dict:
    """One pass over unseen mail. Safe to call often; never raises."""
    if not configured():
        return {"configured": False}
    host = os.getenv("FAMILYHUB_MAIL_HOST")
    user = os.getenv("FAMILYHUB_MAIL_USER")
    pw = os.getenv("FAMILYHUB_MAIL_PASS")
    folder = os.getenv("FAMILYHUB_MAIL_FOLDER", "INBOX")
    n = 0
    try:
        M = imaplib.IMAP4_SSL(host, timeout=20)
        M.login(user, pw)
        M.select(folder)
        typ, data = M.search(None, "UNSEEN")
        ids = (data[0] or b"").split()[:20]
        with get_db() as conn:
            for mid in ids:
                typ, raw = M.fetch(mid, "(RFC822)")
                if typ != "OK" or not raw or not raw[0]:
                    continue
                msg = email.message_from_bytes(raw[0][1], policy=email.policy.default)
                uid = (msg.get("Message-ID") or f"{host}:{mid.decode()}:{datetime.now().date()}")[:300]
                if conn.execute("SELECT 1 FROM mail_imports WHERE uid=?", (uid,)).fetchone():
                    M.store(mid, "+FLAGS", "\\Seen")
                    continue
                events = extract_events(msg)
                _store(conn, uid, msg, events)
                M.store(mid, "+FLAGS", "\\Seen")
                n += 1
        M.logout()
        return {"configured": True, "processed": n}
    except Exception as e:
        return {"configured": True, "processed": n, "error": str(e)[:120]}
