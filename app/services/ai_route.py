"""
Smart routing: take one line of natural text from the phone and figure out
whether it's a calendar event, a to-do, a grocery item, or a meal — then
return structured data the phone app can confirm and save.

This is what lets her type "milk and eggs" OR "dentist thursday 4pm" OR
"remind me to call mom" into the same box and have it land in the right place.

Requires: pip install anthropic ; set ANTHROPIC_API_KEY
"""
import json
import os
from datetime import date
from typing import Dict

SYSTEM = """You sort a family's quick note into one of four buckets and extract fields.
Today is {today}. Return ONLY JSON (no prose, no fences).

Schema:
{{"kind": "event"|"todo"|"grocery"|"meal", "items": [ ... ]}}

Per kind, each item is:
  event:   {{"title": str, "start": ISO8601, "end": ISO8601, "all_day": bool}}
  todo:    {{"title": str}}
  grocery: {{"item": str, "qty": str|null}}
  meal:    {{"date": ISO8601 date, "slot": "breakfast"|"lunch"|"dinner"|"snack", "title": str}}

Rules:
- A note can produce multiple items (e.g. "milk, eggs, bread" -> 3 grocery items).
- Resolve relative dates ("thursday", "tomorrow") against today.
- Events with no end default to +1 hour.
- "remind me to X" / "need to X" -> todo. Food to buy -> grocery.
  "for dinner X" / "X for lunch tuesday" -> meal. Anything with a date/time -> event."""


def route_text(text: str, model: str | None = None) -> Dict:
    from .ai_model import model as _model
    model = model or _model()
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    from . import ai_model
    resp = ai_model.create(
        client, model=model, max_tokens=4096, **ai_model.effort(model, "low"),
        system=SYSTEM.format(today=date.today().isoformat()),
        messages=[{"role": "user", "content": text}],
    )
    try:
        from . import ai_cost
        ai_cost.record("quick-add", resp)
    except Exception:
        pass
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"kind": "todo", "items": [{"title": text}]}  # safe fallback
