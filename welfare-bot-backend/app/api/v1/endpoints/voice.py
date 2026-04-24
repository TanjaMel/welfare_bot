from __future__ import annotations

import io
import os
import tempfile

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.integrations.openai_client import client

router = APIRouter()


class SpeakRequest(BaseModel):
    text: str
    language: str = "fi"


class TranscribeResponse(BaseModel):
    text: str
    language: str


@router.post("/speak", summary="Convert text to speech")
def speak(payload: SpeakRequest):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text is empty")

    text = payload.text[:4096]

    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="nova",
            input=text,
            response_format="mp3",
        )
        return StreamingResponse(
            io.BytesIO(response.content),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@router.post("/transcribe", response_model=TranscribeResponse, summary="Speech to text")
async def transcribe(
    audio: UploadFile = File(...),
    language: str = Form(default="fi"),
):
    audio_bytes = await audio.read()

    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    filename = audio.filename or "recording.webm"
    ext = os.path.splitext(filename)[1] or ".webm"

    # Determine mime type from extension
    mime_map = {
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
        ".mp3": "audio/mpeg",
        ".mp4": "audio/mp4",
        ".wav": "audio/wav",
        ".m4a": "audio/m4a",
    }
    mime_type = mime_map.get(ext.lower(), "audio/webm")

    # Normalize language — default to fi if not supported
    lang = language if language in ("fi", "en", "sv") else "fi"

    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=(filename, f, mime_type),
                    language=lang,
                )
            return TranscribeResponse(
                text=transcript.text.strip(),
                language=lang,
            )
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")