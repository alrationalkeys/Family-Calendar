"""
Local speech-to-text + text-to-speech for the wall, no cloud.

Why: the wall's Chromium is Ubuntu's snap build, which has no speech engine
behind the Web Speech API — SpeechRecognition errors out instantly and
speechSynthesis is often silent. So the browser just records a clip and we
do the work here on the mini PC:

  STT  faster-whisper  (CTranslate2 Whisper; `base.en` int8 is ~1-2 s for a
       5 s clip on the i3-5005U)              env FAMILYHUB_STT_MODEL
  TTS  piper            (onnx voice file)     env FAMILYHUB_PIPER_VOICE

Both are optional: `pip install faster-whisper piper-tts` + a voice file
(setup/install-voice.sh does it). If either is missing the endpoints answer
503 and the browser falls back to the Web Speech API.
"""
from __future__ import annotations

import io
import os
import tempfile
import threading
import wave

_lock = threading.Lock()
_stt = None
_tts = None

STT_MODEL = os.getenv("FAMILYHUB_STT_MODEL", "base.en")
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PIPER_VOICE = os.getenv("FAMILYHUB_PIPER_VOICE",
                        os.path.join(_ROOT, "models", "piper", "en_US-lessac-medium.onnx"))


# ---------------------------------------------------------------- STT ----
def stt_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except Exception:
        return False


def _stt_model():
    global _stt
    with _lock:
        if _stt is None:
            from faster_whisper import WhisperModel
            _stt = WhisperModel(STT_MODEL, device="cpu", compute_type="int8")
        return _stt


# Whisper's favourite hallucinations on a clip of silence / room noise
_GHOSTS = {"you", "thank you", "thanks", "thank you.", "thanks for watching", "thanks for watching!", "bye",
           "thank you for watching", "so", "okay", "the end", "."}
BEAM = int(os.environ.get("FAMILYHUB_STT_BEAM", "5"))


def transcribe(audio: bytes, suffix: str = ".webm", prompt: str = "") -> str:
    """Bytes of any container PyAV can read (webm/opus from MediaRecorder, wav, ogg)."""
    if not audio:
        return ""
    model = _stt_model()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio)
        path = f.name
    try:
        segments, _info = model.transcribe(path, language="en", beam_size=BEAM, vad_filter=True,
                                           vad_parameters={"min_silence_duration_ms": 700},
                                           condition_on_previous_text=False,
                                           initial_prompt=prompt or None)
        text = " ".join(s.text.strip() for s in segments if (s.no_speech_prob or 0) < 0.8).strip()
        return "" if text.lower().strip(" .!") in {g.strip(" .!") for g in _GHOSTS} else text
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ---------------------------------------------------------------- TTS ----
def tts_available() -> bool:
    if not os.path.exists(PIPER_VOICE):
        return False
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


def _tts_voice():
    global _tts
    with _lock:
        if _tts is None:
            from piper import PiperVoice
            _tts = PiperVoice.load(PIPER_VOICE)
        return _tts


def synthesize(text: str) -> bytes:
    """-> WAV bytes."""
    text = (text or "").strip()
    if not text:
        return b""
    voice = _tts_voice()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        if hasattr(voice, "synthesize_wav"):          # piper-tts >= 1.3
            voice.synthesize_wav(text, w)
        else:                                          # piper-tts 1.2.x
            voice.synthesize(text, w)
    return buf.getvalue()


def status() -> dict:
    return {"stt": stt_available(), "tts": tts_available(),
            "stt_model": STT_MODEL, "voice": os.path.basename(PIPER_VOICE)}


def warm_up():
    """Load models in the background at startup so the first tap isn't slow."""
    def run():
        try:
            if stt_available():
                _stt_model()
            if tts_available():
                _tts_voice()
        except Exception:
            pass
    threading.Thread(target=run, daemon=True).start()
