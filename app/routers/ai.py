"""AI endpoints — natural language in, structured data + auto-save."""
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from datetime import datetime, timedelta
from ..services import ai_parse, ai_route, ai_vision, voice_cmd, speech
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


# ---- local speech (see services/speech.py) ------------------------------
@router.get("/voice/status")
def voice_status():
    """{stt, tts} — whether the server can transcribe / speak locally. The wall
    uses this to decide between recording a clip for us or the browser's own
    Web Speech API (which snap Chromium lacks)."""
    return speech.status()


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Audio clip (webm/opus from MediaRecorder, or wav) -> {text}."""
    if not speech.stt_available():
        raise HTTPException(503, "speech-to-text not installed (run setup/install-voice.sh)")
    data = await audio.read()
    if len(data) > 8_000_000:
        raise HTTPException(413, "clip too long")
    ct = (audio.content_type or "").lower()
    suffix = ".wav" if "wav" in ct else ".ogg" if "ogg" in ct else ".webm"
    try:
        return {"text": speech.transcribe(data, suffix)}
    except Exception as e:
        import traceback, sys
        print(f"[transcribe] {len(data)} bytes {ct} -> {e!r}", file=sys.stderr)
        traceback.print_exc()
        raise HTTPException(500, f"transcribe failed: {e!r}")


@router.post("/tts")
def tts(req: TextReq):
    """Text -> audio/wav (Piper). 503 if no voice is installed; the wall then
    falls back to speechSynthesis."""
    if not speech.tts_available():
        raise HTTPException(503, "text-to-speech not installed (run setup/install-voice.sh)")
    try:
        wav = speech.synthesize(req.text[:600])
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"tts failed: {e!r}")
    return Response(content=wav, media_type="audio/wav", headers={"Cache-Control": "no-store"})


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
