"""Speech-to-Text endpoint for the floating mic button.

Workflow:
  1. Browser records audio via MediaRecorder (webm/opus typically).
  2. POSTs the blob as multipart/form-data to `/api/voice/transcribe`.
  3. We hand it to OpenAI Whisper via emergentintegrations.
  4. Optionally chain through `/api/companion/chat` and auto-apply actions.
"""
import io
import os
import logging
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_BYTES = 24 * 1024 * 1024  # 24MB (Whisper hard limit is 25MB)
ALLOWED_EXT = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm", "ogg"}


def _ext_from_filename(name: str) -> str:
    return (name or "").rsplit(".", 1)[-1].lower() if "." in (name or "") else ""


def _ext_from_mime(mime: str) -> str:
    """Best-effort map of common browser MediaRecorder MIME types to Whisper-friendly extensions."""
    mime = (mime or "").lower()
    if "webm" in mime:
        return "webm"
    if "ogg" in mime:
        return "ogg"
    if "mp4" in mime or "m4a" in mime:
        return "mp4"
    if "wav" in mime:
        return "wav"
    if "mpeg" in mime or "mp3" in mime:
        return "mp3"
    return ""


@router.post("/voice/transcribe")
async def transcribe_voice(audio: UploadFile = File(...)):
    """Transcribe a single short audio clip via Whisper. Returns {text}.
    Accepts webm/opus (Chrome/Edge default), mp4 (Safari), wav, mp3, ogg.
    """
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(500, "Voice transcription not configured")

    raw = await audio.read()
    if not raw:
        raise HTTPException(400, "Empty audio upload")
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "Audio too large (max 24MB)")

    ext = _ext_from_filename(audio.filename or "") or _ext_from_mime(audio.content_type or "")
    if ext not in ALLOWED_EXT:
        # default to webm — most browsers send opus-in-webm
        ext = "webm"

    # emergentintegrations Whisper wrapper expects a file-like object with `.name`
    # so it can infer the format. We wrap bytes in BytesIO and set .name.
    bio = io.BytesIO(raw)
    bio.name = f"voice-{datetime.utcnow().timestamp():.0f}.{ext}"

    try:
        stt = OpenAISpeechToText(api_key=api_key)
        response = await stt.transcribe(
            file=bio,
            model="whisper-1",
            response_format="json",
        )
        text = (getattr(response, "text", None) or "").strip()
        if not text:
            return {"text": "", "ok": True, "note": "Whisper returned empty — too quiet or too short."}
        return {"text": text, "ok": True}
    except Exception as e:
        logger.exception("Voice transcription failed")
        raise HTTPException(500, f"Couldn't transcribe: {str(e)[:120]}")


# --------- Text → Speech ---------
class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice: str = "coral"   # coral = warm, friendly; sage = wise; nova = energetic
    speed: float = 1.0


# Available voices on tts-1
ALLOWED_VOICES = {"alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"}


@router.post("/voice/speak")
async def speak(payload: SpeakRequest):
    """Convert short Yaar reply into MP3 audio. Returned as audio/mpeg stream so the
    browser can use `new Audio(blobUrl)` for instant playback."""
    api_key = os.environ.get("EMERGENT_LLM_KEY")
    if not api_key:
        raise HTTPException(500, "Voice replies not configured")

    voice = payload.voice if payload.voice in ALLOWED_VOICES else "coral"
    speed = max(0.5, min(2.0, float(payload.speed or 1.0)))

    try:
        tts = OpenAITextToSpeech(api_key=api_key)
        audio_bytes = await tts.generate_speech(
            text=payload.text.strip()[:4000],
            model="tts-1",
            voice=voice,
            speed=speed,
            response_format="mp3",
        )
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=yaar.mp3"},
        )
    except Exception as e:
        logger.exception("TTS failed")
        raise HTTPException(500, f"Couldn't synthesize: {str(e)[:120]}")


# --------- Proactive briefs ---------
class BriefRequest(BaseModel):
    kind: str = Field(..., pattern=r"^(morning|midday|evening|custom)$")
    custom_prompt: str | None = None  # only used when kind == "custom"


@router.post("/voice/brief")
async def make_brief(payload: BriefRequest):
    """Return the spoken text for a proactive brief. Frontend then optionally hits
    /voice/speak to get audio. Deterministic for morning/midday/evening; AI-driven
    when kind=custom (uses the existing companion chat pipeline)."""
    from voice_briefs import generate_brief

    if payload.kind in ("morning", "midday", "evening"):
        text = await generate_brief(payload.kind)
        if not text:
            raise HTTPException(500, "Couldn't build the brief")
        return {"text": text, "kind": payload.kind}

    # custom — delegate to companion chat for a richer, contextual response
    prompt = (payload.custom_prompt or "").strip()
    if not prompt:
        raise HTTPException(400, "custom briefs need a custom_prompt")
    # Call the same chat pipeline with no DB-write side-effects: just a generation
    from routes.companion import chat as companion_chat
    from models import ChatRequest as _CR
    from fastapi import BackgroundTasks
    bg = BackgroundTasks()
    res = await companion_chat(_CR(message=f"[Brief request] {prompt}"), bg)
    text = (res.get("reply", {}) or {}).get("content") or ""
    return {"text": text, "kind": "custom"}
