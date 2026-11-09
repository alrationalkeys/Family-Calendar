"""
Spot a family member's name in free text so items can be assigned by voice/quick-add:
  "add call the vet for Rachell to my to-do"   -> Rachell
  "remind Rachell to book the dentist"          -> Rachell
  "Ella needs to pack her bag"                  -> Ella
  "assign take out trash to Alex"               -> Alex
  "grab forks to rachel's to-do"                -> Rachell  (speech-to-text misspelling + 's)
Returns (person_id, name, cleaned_text) — cleaned_text has the assignment phrase removed
so it can be used as the item title. Matching is case-insensitive, first names only, and
tolerant of near-miss spellings (Rachel/Rachell, Izzy/Izzie) because Whisper will never
spell an unusual name the way it's spelled in the People list.
"""
from __future__ import annotations

import difflib
import re


def _people(conn):
    return [(r["id"], r["name"]) for r in conn.execute("SELECT id, name FROM people")]


def _similar(word: str, first: str) -> bool:
    if word == first:
        return True
    if len(word) >= 4 and len(first) >= 4 and (word.startswith(first) or first.startswith(word)):
        return True
    return len(first) >= 4 and difflib.SequenceMatcher(None, word, first).ratio() >= 0.8


def _find_spoken_name(low: str, first: str):
    """The token in `low` that stands for `first` (handles 's), or None."""
    for tok in re.findall(r"[a-z]+(?:'s)?", low):
        base = tok[:-2] if tok.endswith("'s") else tok
        if _similar(base, first):
            return tok
    return None


def extract_person(conn, text: str):
    text = text or ""
    low = text.lower()
    for pid, name in _people(conn):
        first = (name or "").strip().split(" ")[0].lower()
        if not first:
            continue
        spoken = _find_spoken_name(low, first)
        if not spoken:
            continue
        n = re.escape(spoken)
        # phrases that mark an assignment; remove them from the title
        patterns = [
            rf"\b(?:for|to|assign(?:ed)?(?: to)?|assign(?:ed)? it to)\s+{n}\b\s*(?:to\s+)?",
            rf"\bremind\s+{n}\s+to\s+",
            rf"\b{n}\s+(?:needs?|has|have)\s+to\s+",
            rf"\b{n}\s+(?:to[\s-]?do|task|job|list)\b:?\s*",
            rf"^\s*{n}\b[:,]?\s+",
            rf"\b{n}\b",
        ]
        for p in patterns:
            m = re.search(p, low)
            if m:
                cleaned = (text[:m.start()] + " " + text[m.end():]).strip()
                cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.:")
                cleaned = re.sub(r"^(?:assign(?:ed)?|please)\s+", "", cleaned, flags=re.I).strip()
                return pid, name, cleaned or text.strip()
    return None, None, text.strip()
