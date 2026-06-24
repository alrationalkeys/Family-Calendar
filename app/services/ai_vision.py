"""
Vision quick-add: take a photo of a paper flyer, school newsletter, or sports
schedule and extract calendar events from it. This is the feature Skylight charges
for ("Magic Import") and does less well.

Accepts base64 image data from the phone, sends to the Anthropic vision API,
returns structured events ready to confirm and save.

Requires: pip install anthropic ; set ANTHROPIC_API_KEY
"""
import json
import os
from datetime import date
from typing import Dict, List

SYSTEM = """You extract calendar events from a photo of a document (flyer, school
newsletter, sports schedule, appointment card, etc). Today is {today}.
Return ONLY a JSON array (no prose, no fences). Each item:
{{"title": str, "start": ISO8601, "end": ISO8601, "all_day": bool}}
Resolve relative/partial dates against today. Infer the year if omitted.
If a time isn't given, set all_day true. Include every distinct event you find."""


def extract_events_from_image(image_b64: str, media_type: str = "image/jpeg",
                              model: str = "claude-opus-4-8") -> List[Dict]:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    resp = client.messages.create(
        model=model, max_tokens=2048,
        system=SYSTEM.format(today=date.today().isoformat()),
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": media_type, "data": image_b64}},
                {"type": "text", "text": "Extract all events from this image."},
            ],
        }],
    )
    raw = "".join(b.text for b in resp.content if b.type == "text").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []
