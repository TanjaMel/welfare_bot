from __future__ import annotations

import io
import os
import tempfile

from fastapi import APIRouter, Request, HTTPException
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
        audio_bytes = response.content
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=speech.mp3"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {str(e)}")


@router.post("/transcribe", response_model=TranscribeResponse, summary="Speech to text")
async def transcribe(request: Request):
    try:
        form = await request.form()
    except Exception:
        raise HTTPException(status_code=422, detail="Could not parse form data")

    audio_file = form.get("audio")
    language = str(form.get("language", "fi"))

    if audio_file is None:
        raise HTTPException(status_code=422, detail="No audio field in form")

    try:
        audio_bytes = await audio_file.read()
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read audio file")

    if len(audio_bytes) == 0:
        raise HTTPException(status_code=422, detail="Audio file is empty")

    # Determine file extension
    filename = getattr(audio_file, "filename", "") or ""
    ext = os.path.splitext(filename)[1] if filename else ".webm"
    if not ext:
        ext = ".webm"

    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
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