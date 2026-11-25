"""
Hands-free wake word on the wall ("Hey Jarvis, set a timer for 5 minutes for eggs").

Runs on the wall PC itself, offline: openWakeWord listens to the microphone all the time
(PipeWire shares the mic, so the wall's tap-to-talk still works). When it hears the wake
word it keeps recording until you stop talking, Whisper turns that into text, and the wall
is told over the live event stream (`/api/ha/events`, field `wake`). The wall then does
exactly what a tap on the mic does: runs the command, speaks the reply, starts the timer.

  settings.wakeWord       built-in model name (hey_jarvis, hey_mycroft, hey_rhasspy, alexa), the file name of
                          a custom model in models/wakeword/ (without .onnx), or "off". Default hey_jarvis.
  settings.wakeSensitivity  low | normal | high   (how sure the model must be)
  FAMILYHUB_WAKE_MIC_CMD  override the recording command (must write raw 16 kHz mono s16le to stdout)

Install: setup/install-wakeword.sh  (pip openwakeword --no-deps + onnxruntime, downloads the models).
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import subprocess
import threading
import time
import wave
from collections import deque

from ..db import get_db

RATE = 16000
FRAME = 1280                       # 80 ms: what openWakeWord wants per call
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CUSTOM_DIR = os.path.join(_ROOT, "models", "wakeword")
BUILTIN = {"hey_jarvis": "Hey Jarvis", "hey_mycroft": "Hey Mycroft", "hey_rhasspy": "Hey Rhasspy", "alexa": "Alexa"}
THRESH = {"low": 0.7, "normal": 0.5, "high": 0.3}
SKIP = 9                           # first 0.7 s after the word: the wall's chime (heard by the mic) is ignored
COOLDOWN = 2.5                     # seconds after a wake before another can fire

_S: dict = {"running": False, "word": "", "error": "", "mic": "", "wakes": 0, "last_score": 0.0, "best_recent": 0.0,
            "last_wake": None, "last_text": ""}
_event: dict = {"n": 0, "stage": "", "text": "", "at": 0}
_claimed = 0
_lock = threading.Lock()
_busy = threading.Lock()           # held while a command is being turned into text
_started = False
_ringing_until = 0.0              # a timer is ringing on the wall: listen harder (the chime drowns the word)
RING_THRESH = 0.2


# ------------------------------------------------------------------ settings ----
def _settings() -> dict:
    try:
        with get_db() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key='ui'").fetchone()
            return json.loads(row["value"]) if row else {}
    except Exception:
        return {}


def installed() -> bool:
    try:
        import openwakeword  # noqa: F401
        import onnxruntime  # noqa: F401
        return True
    except Exception:
        return False


def custom_words() -> list[str]:
    try:
        return sorted(f[:-5] for f in os.listdir(CUSTOM_DIR) if f.endswith(".onnx"))
    except OSError:
        return []


def choices() -> list[dict]:
    out = [{"id": k, "name": v} for k, v in BUILTIN.items()]
    out += [{"id": c, "name": pretty(c)} for c in custom_words()]
    return out


def pretty(word: str) -> str:
    if word in BUILTIN:
        return BUILTIN[word]
    w = re.sub(r"_v\d+(\.\d+)*$", "", word or "")
    return " ".join(p.capitalize() for p in re.split(r"[_\-\s]+", w) if p)


def wanted() -> tuple[str, float]:
    s = _settings()
    word = str(s.get("wakeWord") or "hey_jarvis").strip()
    if word.lower() in ("off", "none", "false"):
        word = ""
    return word, THRESH.get(str(s.get("wakeSensitivity") or "normal"), 0.5)


def _model_path(word: str) -> str:
    """A custom model file wins over a built-in of the same name."""
    p = os.path.join(CUSTOM_DIR, word + ".onnx")
    return p if os.path.exists(p) else word


# ------------------------------------------------------------------ text ----
def strip_wake(text: str, word: str) -> str:
    """Whisper often catches the tail of the wake word ("Jarvis, set a timer", "vis. Set a timer"). Drop leading
    words that belong to the wake phrase (or the end of its last word), plus filler punctuation."""
    parts = [p for p in re.split(r"[_\-\s]+", re.sub(r"_v\d+(\.\d+)*$", "", word.lower())) if p] + ["hey", "hi", "ok", "okay"]
    last = parts[0] if parts else ""
    for p in parts:
        if p not in ("hey", "hi", "ok", "okay"):
            last = p
    import difflib
    toks = (text or "").strip().split()
    fuzzy = True                       # the name itself is often misheard ("Carvus", "Jervis"): once, as the first name-like word
    while toks:
        t = re.sub(r"[^a-z']", "", toks[0].lower())
        if not t or t in parts or (len(t) >= 2 and last.endswith(t) and last != t and len(toks) > 1):
            toks.pop(0)
            continue
        if fuzzy and len(toks) > 1 and len(t) >= 3 and difflib.SequenceMatcher(None, t, last).ratio() >= 0.6:
            fuzzy = False
            toks.pop(0)
            continue
        break
    out = " ".join(toks).strip(" ,.!?")
    return out[:1].upper() + out[1:] if out else ""


# ------------------------------------------------------------------ events for the wall ----
def _publish(stage: str, text: str = ""):
    with _lock:
        _event.update(n=_event["n"] + 1, stage=stage, text=text, at=time.time())
    try:
        from . import ha_live
        ha_live.bump()
    except Exception:
        pass


def event() -> dict | None:
    """What rides on the live stream: {n, stage: listening|heard|nothing, text}. None until the first wake."""
    with _lock:
        return dict(_event) if _event["n"] else None


def claim(n: int) -> bool:
    """The wall asks to run wake #n; only the first screen to ask gets it (two walls never set two timers)."""
    global _claimed
    with _lock:
        if n != _event["n"] or n <= _claimed or time.time() - _event["at"] > 30:
            return False
        _claimed = n
        return True


def ringing(on: bool):
    global _ringing_until
    _ringing_until = time.time() + 65 if on else 0.0


def _thr(thr: float) -> float:
    return min(thr, RING_THRESH) if time.time() < _ringing_until else thr


def status() -> dict:
    word, thr = wanted()
    return {"installed": installed(), "word": word, "name": pretty(word) if word else "", "threshold": thr,
            "choices": choices(), **{k: v for k, v in _S.items() if k != "word"}, "active_word": _S.get("word")}


# ------------------------------------------------------------------ microphone ----
def _mic_cmds() -> list[list[str]]:
    env = os.environ.get("FAMILYHUB_WAKE_MIC_CMD", "").strip()
    if env:
        return [["sh", "-c", env]]
    out = []
    if shutil.which("parec"):
        out.append(["parec", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=1", "--latency-msec=80"])
    if shutil.which("arecord"):
        out.append(["arecord", "-q", "-D", "default", "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"])
    if shutil.which("pw-record"):
        out.append(["pw-record", "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"])
    return out


def _open_mic():
    env = dict(os.environ)
    env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    last = "no recording program (install pulseaudio-utils or alsa-utils)"
    for cmd in _mic_cmds():
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, bufsize=0)
        except OSError as e:
            last = f"{cmd[0]}: {e}"
            continue
        first = p.stdout.read(FRAME * 2)          # proves it really records
        if first and len(first) == FRAME * 2:
            return p, cmd[0] if cmd[0] != "sh" else "custom", first
        err = (p.stderr.read(300) or b"").decode(errors="replace").strip() if p.poll() is not None else "no sound"
        last = f"{cmd[0]}: {err or 'stopped'}"
        try:
            p.kill()
        except Exception:
            pass
    raise RuntimeError(last)


def _read(p, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = p.stdout.read(n - len(buf))
        if not chunk:
            raise RuntimeError("the microphone stopped")
        buf += chunk
    return buf


# ------------------------------------------------------------------ after the wake word ----
def _rms(frame) -> float:
    import numpy as np
    a = frame.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(a * a))) if a.size else 0.0


def record_command(next_frame, floor: float) -> list:
    """Keep reading 80 ms frames until the speaker stops: ~1.1 s of quiet after speech, 6 s with no speech at all,
    12 s at most. `floor` = how loud the room was just before the wake word. Same rules as the wall's mic button."""
    frames, heard, quiet, peak, talk = [], False, 0, 0.0, 0
    thr = max(0.006, min(0.03, floor * 3))
    for i in range(int(12 / 0.08)):
        f = next_frame()
        frames.append(f)
        if i < SKIP:                 # the wall's "listening" chime comes out of the speaker now: it is not the cook talking
            continue
        r = _rms(f)
        peak = max(peak, r)
        if r > thr and r > peak * 0.3:
            talk += 1
            quiet = 0
            heard = heard or talk >= 3          # a quarter second of talking, not one clank of a pan
        elif heard:
            quiet += 1
            if quiet * 0.08 >= 1.1:
                break
        if not heard and i * 0.08 >= 6:
            break
    return frames if heard else []


def _wav(frames) -> bytes:
    import numpy as np
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(np.concatenate(frames).astype(np.int16).tobytes())
    return buf.getvalue()


def _prefetch_words():
    try:
        from . import voice_cmd
        voice_cmd.stt_prompt()
    except Exception:
        pass


def _handle(frames, word: str, t0: float):
    with _busy:
        _handle_one(frames, word, t0)


def _handle_one(frames, word: str, t0: float):
    from . import speech, voice_cmd
    if not frames:
        _publish("nothing")
        voice_cmd.log_voice("", f"(heard “{pretty(word)}”, then nothing)", "heard")
        return
    rec = time.time() - t0                       # from the wake word to the end of talking
    t1 = time.time()
    words = 0.0
    try:
        prompt = voice_cmd.stt_prompt()
        words = time.time() - t1
        text = speech.transcribe(_wav(frames), ".wav", prompt) if speech.stt_available() else ""
    except Exception as e:
        text = ""
        _S["error"] = f"speech to text: {e!r}"[:200]
    raw, text = text, strip_wake(text, word)
    _S["last_text"] = text
    c = speech.last_clip or {}
    voice_cmd.log_voice(text, f"(heard “{pretty(word)}”; recorded {rec:.1f} s ({len(frames) * 0.08:.1f} s of sound), "
                        f"speech to text {time.time() - t1:.1f} s" + (f" (word list {words:.1f} s)" if words >= 0.5 else "")
                        + (f"; model {c.get('model')} s, load {c.get('load')}" if c.get("model") is not None else "")
                        + (f"; heard as “{raw}”" if raw and raw != text else "") + ")", "heard")
    _publish("heard" if text else "nothing", text)


# ------------------------------------------------------------------ main loop ----
def _loop():
    import numpy as np
    while True:
        word, thr = wanted()
        if not word or not installed():
            _S.update(running=False, word="", error="" if not word else "not installed (setup/install-wakeword.sh)")
            time.sleep(10)
            continue
        p = None
        try:
            from openwakeword.model import Model
            model = Model(wakeword_models=[_model_path(word)], inference_framework="onnx")
            key = next(iter(model.models.keys()))
            p, mic, first = _open_mic()
            _S.update(running=True, word=word, error="", mic=mic)
            pre = deque(maxlen=int(1.5 / 0.08))        # the last 1.5 s, for the room's noise level
            tail = deque(maxlen=6)                     # the last 0.5 s of sound: "Hey Jarvis set a…" said in one breath
            pending = [first]
            last_wake, checked, best = 0.0, time.time(), 0.0
            paused = False

            def next_frame():
                if pending:
                    return np.frombuffer(pending.pop(0), dtype=np.int16)
                return np.frombuffer(_read(p, FRAME * 2), dtype=np.int16)

            while True:
                f = next_frame()
                if _busy.locked():                      # the speech model is working: keep draining the mic, leave it the processor
                    paused = True
                    continue
                if paused:
                    paused = False
                    model.reset()
                score = float(model.predict(f)[key])
                best = max(best, score)
                pre.append(_rms(f))
                tail.append(f)
                now = time.time()
                if now - checked > 5:                   # setting changed? (word off / another word / sensitivity)
                    checked = now
                    _S.update(last_score=round(score, 3), best_recent=round(best, 3))
                    best = 0.0
                    w2, thr = wanted()
                    if w2 != word:
                        break
                if score >= _thr(thr) and now - last_wake > COOLDOWN and _busy.locked():
                    last_wake = now                         # still working on the last one: don't pile a second on top
                    continue
                if score >= _thr(thr) and now - last_wake > COOLDOWN:
                    last_wake = now
                    _S["wakes"] += 1
                    _S["last_wake"] = time.strftime("%Y-%m-%d %H:%M:%S")
                    _publish("listening")
                    threading.Thread(target=_prefetch_words, daemon=True).start()   # fetched while you talk, not after
                    floor = sorted(pre)[len(pre) // 3] if pre else 0.0     # quieter third: the wake word itself isn't room noise
                    frames = record_command(next_frame, floor)
                    if frames:
                        frames = list(tail) + frames           # Whisper hears "…vis, set a timer"; strip_wake drops the "vis"
                    tail.clear()
                    threading.Thread(target=_handle, args=(frames, word, now), daemon=True, name="wake-stt").start()
                    model.reset()
                    last_wake = time.time()
        except Exception as e:
            _S.update(running=False, error=str(e)[:200])
            time.sleep(15)
        finally:
            if p:
                try:
                    p.kill()
                except Exception:
                    pass


def start():
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, daemon=True, name="wake-word").start()
