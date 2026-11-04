"""AI endpoints — natural language in, structured data + auto-save."""
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime, timedelta
from ..services import ai_parse, ai_route, ai_vision, voice_cmd
from ..db import get_db

router = APIRouter()


class TextReq(BaseModel):
    text: str
    category_id: int | None = None
    color: str | None = None


@router.post("/command")
def command(req: TextReq):
    """Voice/text command from the wall screen: control the smart home, run a
    scene, arm the alarm, add to a list, or answer a quick question. Returns
    {ok, say, ...} — `say` is what the screen speaks back."""
    return voice_cmd.interpret(req.text)


@router.post("/parse")
def parse(req: TextReq):
    """Parse text into events only (no save). Used by the event field preview."""
    return {"events": ai_parse.parse_text_to_events(req.text)}


@router.post("/route")
def route(req: TextReq):
    """Classify text into event/todo/grocery/meal and return a preview to confirm."""
    return ai_route.route_text(req.text)


@router.post("/quick-add")
def quick_add(req: TextReq):
    """One-tap magic: route the text AND save it. Returns what was created."""
    parsed = ai_route.route_text(req.text)
    kind = parsed.get("kind", "todo")
    items = parsed.get("items", [])
    created = []
    with get_db() as conn:
        for it in items:
            if kind == "todo":
                conn.execute("INSERT INTO todos (title, category_id, color) VALUES (?,?,?)",
                             (it["title"], req.category_id, req.color))
            elif kind == "grocery":
                conn.execute("INSERT INTO groceries (item, qty, category_id, color) VALUES (?,?,?,?)",
                             (it["item"], it.get("qty"), req.category_id, req.color))
            elif kind == "meal":
                conn.execute("INSERT INTO meals (date, slot, title, category_id, color) VALUES (?,?,?,?,?)",
                             (it["date"], it["slot"], it["title"], req.category_id, req.color))
            # events are written to the real calendar via /api/calendar/events
            created.append(it)
    return {"kind": kind, "created": created}


class MealPlanReq(BaseModel):
    days: int = 7
    prefs: str = ""
    start: str | None = None


class MealApplyReq(BaseModel):
    meals: list[dict]
    add_groceries: bool = True


@router.post("/meal-plan")
def meal_plan(req: MealPlanReq):
    """Plan dinners for the next N days (preview only). AI if a key is set,
    otherwise a built-in family rotation so it always works."""
    from ..services import ai_meals
    return ai_meals.plan(req.days, req.prefs, req.start)


@router.post("/meal-plan/apply")
def meal_plan_apply(req: MealApplyReq):
    """Save the chosen meals and add their ingredients to the grocery list."""
    from ..services import ai_meals
    return ai_meals.apply(req.meals, req.add_groceries)


class VisionReq(BaseModel):
    image_b64: str
    media_type: str = "image/jpeg"


@router.post("/vision")
def vision(req: VisionReq):
    """Photograph a flyer/schedule -> extracted events to confirm before saving."""
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        return {"events": [], "error": "AI not configured (set ANTHROPIC_API_KEY)"}
    # guard against oversized uploads (~7MB base64 ≈ 5MB image, Anthropic's limit)
    if len(req.image_b64) > 7_000_000:
        return {"events": [], "error": "Image too large — try a smaller photo"}
    if req.media_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        return {"events": [], "error": "Unsupported image type"}
    try:
        events = ai_vision.extract_events_from_image(req.image_b64, req.media_type)
        return {"events": events}
    except Exception as e:
        return {"events": [], "error": f"Couldn't read image: {e}"}
