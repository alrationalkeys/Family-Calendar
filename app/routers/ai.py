import re
"""AI endpoints — natural language in, structured data + auto-save."""
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from datetime import datetime, timedelta
from ..services import ai_parse, ai_route, ai_vision, voice_cmd, speech, cloud_voice
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


@router.get("/wake")
def wake_status():
    """Hands-free wake word: installed, running, which word, the mic, how many wakes, the last thing heard."""
    from ..services import wake
    return wake.status()


class WakeClaim(BaseModel):
    n: int


@router.post("/wake/claim")
def wake_claim(req: WakeClaim):
    """The wall asks to run what the wake word heard; only the first screen gets it."""
    from ..services import wake
    return {"ok": wake.claim(req.n)}


class WakeRing(BaseModel):
    on: bool


@router.post("/wake/ringing")
def wake_ringing(req: WakeRing):
    """The wall says a timer is ringing (or stopped): the wake word listens harder over the chime meanwhile."""
    from ..services import wake
    wake.ringing(req.on)
    return {"ok": True}


@router.post("/wake/test")
def wake_test(req: TextReq):
    """Pretend the wake word heard `text` (phone Settings > Voice > Test): the wall runs it like a real wake."""
    from ..services import wake
    wake._publish("listening")
    wake._publish("heard", req.text.strip()[:300])
    return {"ok": True}


@router.get("/voice/log")
def voice_log():
    """What the wall heard and what it did (newest first) — Settings > Advanced > Voice history."""
    return {"log": voice_cmd.voice_log()}


@router.delete("/voice/log")
def voice_log_clear():
    with get_db() as conn:
        conn.execute("DELETE FROM settings WHERE key='voice_log'")
    return {"ok": True}


@router.get("/cost")
def ai_cost_summary():
    """Approximate spend on the AI features since tracking began (today / 7 days / this month / total, by feature)."""
    from ..services import ai_cost
    return ai_cost.summary()


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
        import time
        t0 = time.time()
        # Whisper is slow CPU work: run it on a worker thread. Calling it straight from this async route froze the
        # whole server for the length of the transcription, so the wall's other requests timed out ("offline").
        from starlette.concurrency import run_in_threadpool
        tm = {}

        def work():
            w0 = time.time()
            tm["wait"] = w0 - t0                      # waiting for a free worker
            prompt = voice_cmd.stt_prompt()
            tm["words"] = time.time() - w0            # building the word list (asks HA; cached 10 min)
            return speech.transcribe(data, suffix, prompt)
        text = await run_in_threadpool(work)
        slow = "; ".join(f"{k} {v:.1f} s" for k, v in tm.items() if v >= 1.0)
        if not text:
            voice_cmd.log_voice("", f"(heard nothing in a {len(data) // 1024} KB clip, {time.time() - t0:.1f} s)", "heard")
        if text:
            c = speech.last_clip or {}
            voice_cmd.log_voice(text, f"(turned the speech into text in {time.time() - t0:.1f} s"
                                + (f"; recording was {c.get('secs')} s long, {c.get('speech')} s of it speech" if c else "")
                                + (f"; of that: {slow}" if slow else "")
                                + (f"; {c.get('name')} model took {c.get('model')} s, reading the clip {c.get('prep')} s; "
                                   f"{c.get('cores')} cores, computer load {c.get('load')}" if c.get("model") is not None and time.time() - t0 >= 3 else "")
                                + ")", "heard")
        return {"text": text, "secs": round(time.time() - t0, 2)}
    except Exception as e:
        import traceback, sys
        print(f"[transcribe] {len(data)} bytes {ct} -> {e!r}", file=sys.stderr)
        traceback.print_exc()
        raise HTTPException(500, f"transcribe failed: {e!r}")


@router.post("/tts")
def tts(req: TextReq):
    """Text -> audio. The ElevenLabs voice when one is picked (mp3), else Piper (wav). 503 if neither is there;
    the wall then falls back to speechSynthesis."""
    text = req.text[:600]
    if cloud_voice.ready():
        mp3 = cloud_voice.speak(text)
        if mp3:
            return Response(content=mp3, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
    if not speech.tts_available():
        raise HTTPException(503, "text-to-speech not installed (run setup/install-voice.sh)")
    try:
        wav = speech.synthesize(text)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"tts failed: {e!r}")
    return Response(content=wav, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@router.post("/voice/note")
def voice_note(req: TextReq):
    """The wall reports a speech problem (audio blocked, no voice) into the voice history."""
    voice_cmd.log_voice("", "(" + req.text[:300] + ")", "wall")
    return {"ok": True}


class VoiceTestReq(BaseModel):
    voice_id: str = ""
    text: str = ""


@router.get("/voice/cloud")
def voice_cloud():
    """ElevenLabs: key present, the account's voices, credits used this month."""
    return cloud_voice.info()


@router.post("/voice/cloud/test")
def voice_cloud_test(req: VoiceTestReq):
    """Play one sentence in a voice (uses a few credits the first time; cached after)."""
    if not req.voice_id:                               # the built-in (Piper) voice
        if not speech.tts_available():
            raise HTTPException(503, "The built-in voice isn't installed (setup/install-voice.sh)")
        return Response(content=speech.synthesize((req.text or "Hello! This is the built-in voice.")[:200]),
                        media_type="audio/wav", headers={"Cache-Control": "no-store"})
    if not re.fullmatch(r"[A-Za-z0-9]{8,40}", req.voice_id or ""):
        raise HTTPException(400, "bad voice id")
    try:
        mp3 = cloud_voice.speak((req.text or "Hello! This is how I sound on the wall.")[:200], req.voice_id, strict=True)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    if not mp3:
        raise HTTPException(503, "Add ELEVENLABS_API_KEY to .env on the wall first")
    return Response(content=mp3, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


@router.post("/parse")
def parse(req: TextReq):
    """Parse text into events only (no save). Used by the event field preview."""
    return {"events": ai_parse.parse_text_to_events(req.text)}


@router.post("/route")
def route(req: TextReq):
    """Classify text into event/todo/grocery/meal and return a preview to confirm."""
    return ai_route.route_text(req.text)


@router.post("/quick-add")
def quick_add(req: TextReq, request: Request):
    """One-tap magic: route the text AND save it. Returns what was created."""
    parsed = ai_route.route_text(req.text)
    who = request.headers.get("x-fh-who")
    kind = parsed.get("kind", "todo")
    items = parsed.get("items", [])
    created = []
    with get_db() as conn:
        for it in items:
            if kind == "todo":
                # "call the vet for Rachell" -> assigned to Rachell, title cleaned
                from ..services.people import extract_person
                pid, pname, title = extract_person(conn, it["title"])
                if not pid:
                    pid, pname, _ = extract_person(conn, req.text)
                it["title"] = title or it["title"]
                if pname:
                    it["person"] = pname
                conn.execute("INSERT INTO todos (title, person_id, category_id, color) VALUES (?,?,?,?)",
                             (it["title"], pid, req.category_id, req.color))
                it["person_id"] = pid
            elif kind == "grocery":
                conn.execute("INSERT INTO groceries (item, qty, category_id, color) VALUES (?,?,?,?)",
                             (it["item"], it.get("qty"), req.category_id, req.color))
            elif kind == "meal":
                conn.execute("INSERT INTO meals (date, slot, title, category_id, color) VALUES (?,?,?,?,?)",
                             (it["date"], it["slot"], it["title"], req.category_id, req.color))
            # events are written to the real calendar via /api/calendar/events (announced there)
            created.append(it)
    if kind in ("todo", "grocery", "meal"):
        from ..services import activity
        for it in created:
            activity.record(kind, it, who, request.headers.get("x-fh-source", "phone"))
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
