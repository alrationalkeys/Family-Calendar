"""
The 10x feature: AI-native event entry.

Skylight charges a subscription for "Magic Import" (forward an email/photo,
it extracts dates). We do it better and free using the Anthropic API:
  - Natural language: "kids dentist next thursday at 4, recurring monthly"
  - Pasted text: a school newsletter, a sports schedule, a flyer
  - (extend with vision: a photo of a paper schedule)

Returns structured events ready to write to Google/iCloud.

Requires: pip install anthropic
Set ANTHROPIC_API_KEY in the environment.
"""
import json
import os
from datetime import date
from typing import List, Dict

SYSTEM = """You extract calendar events from text. Today's date is {today}.
Return ONLY a JSON array, no prose, no markdown fences. Each item:
{{"title": str, "start": ISO8601, "end": ISO8601, "all_day": bool, "recurrence": str|null}}
Resolve relative dates ("next thursday") against today. If no end time is given,
default events to 1 hour. recurrence uses RRULE-ish shorthand like "weekly:TH" or null."""


def parse_text_to_events(text: str, model: str | None = None) -> List[Dict]:
    from .ai_model import model as _model
    model = model or _model()
    from anthropic import Anthropic

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM.format(today=date.today().isoformat()),
        messages=[{"role": "user", "content": text}],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []
