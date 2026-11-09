"""
Spot a family member's name in free text so items can be assigned by voice/quick-add:
  "add call the vet for Rachell to my to-do"   -> Rachell
  "remind Rachell to book the dentist"          -> Rachell
  "Ella needs to pack her bag"                  -> Ella
  "assign take out trash to Alex"               -> Alex
Returns (person_id, name, cleaned_text) — cleaned_text has the assignment phrase removed
so it can be used as the item title. Matches are case-insensitive, first names only.
"""
from __future__ import annotations

import re


def _people(conn):
    return [(r["id"], r["name"]) for r in conn.execute("SELECT id, name FROM people")]


def extract_person(conn, text: str):
    text = text or ""
    low = text.lower()
    for pid, name in _people(conn):
        first = (name or "").strip().split(" ")[0]
        if not first:
            continue
        n = re.escape(first.lower())
        # phrases that mark an assignment; remove them from the title
        patterns = [
            rf"\b(?:for|to|assign(?:ed)?(?: to)?|assign(?:ed)? it to)\s+{n}\b\s*(?:to\s+)?",
            rf"\bremind\s+{n}\s+to\s+",
            rf"\b{n}\s+(?:needs?|has|have)\s+to\s+",
            rf"\b{n}(?:'s)?\s+(?:to[\s-]?do|task|job)\b:?\s*",
            rf"^\s*{n}\b[:,]?\s+",
        ]
        for p in patterns:
            m = re.search(p, low)
            if m:
                cleaned = (text[:m.start()] + " " + text[m.end():]).strip()
                cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.:")
                cleaned = re.sub(r"^(?:assign(?:ed)?|please)\s+", "", cleaned, flags=re.I).strip()
                return pid, name, cleaned
        if re.search(rf"\b{n}\b", low):          # name mentioned somewhere: assign, keep title
            return pid, name, text.strip()
    return None, None, text.strip()
