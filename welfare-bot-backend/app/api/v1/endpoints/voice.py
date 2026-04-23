from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.openai_client import client

router = APIRouter()

VOICE_MAP = {
    "fi": "nova",
    "en": "nova",
    "sv": "nova",
}


class SpeakRequest(BaseModel):
    text: str
    language: str = "fi"


class TranscribeResponse(BaseModel):
    text: str
    language: str


@router.post("/speak", summary="Convert text to speech")
def speak(payload: SpeakRequest):
    """
    Converts bot reply text to audio using OpenAI TTS.
    Returns audio/mpeg stream.
    """
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text is empty")

    # Trim to OpenAI TTS limit (4096 chars)
    text = payload.text[:4096]
    voice = VOICE_MAP.get(payload.language, "nova")

    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text,
            response_format="mp3",
        )
        audio_bytes = response.content

        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@router.post("/transcribe", summary="Convert speech to text using Whisper")
async def transcribe(
    request: "Request",
):
    """
    Transcribes audio file to text using OpenAI Whisper.
    Accepts multipart/form-data with an audio file.
    """
    from fastapi import UploadFile, File, Form
    from fastapi import Request
    import tempfile
    import os

    form = await request.form()
    audio_file = form.get("audio")
    language = form.get("language", "fi")

    if not audio_file:
        raise HTTPException(status_code=400, detail="No audio file provided")

    audio_bytes = await audio_file.read()

    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Audio file is empty")

    try:
        # Write to temp file — Whisper needs a file object
        suffix = ".webm"
        if hasattr(audio_file, "filename") and audio_file.filename:
            ext = os.path.splitext(audio_file.filename)[1]
            if ext:
                suffix = ext

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language=language if language in ("fi", "en", "sv") else None,
                )
            return TranscribeResponse(
                text=transcript.text.strip(),
                language=language,
            )
        finally:
            os.unlink(tmp_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")