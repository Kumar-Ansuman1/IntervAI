import logfire
from fastapi import UploadFile

from backend.app.services.llm.gateway import get_llm_gateway


def speech_to_text(audio: UploadFile) -> str:
    filename = audio.filename or "interview-answer.wav"

    with logfire.span(
        "speech-to-text: read uploaded audio",
        content_type=audio.content_type,
    ) as span:
        audio_bytes = audio.file.read()
        span.set_attribute("audio_size_bytes", len(audio_bytes))

    if not audio_bytes:
        raise ValueError("The uploaded audio file is empty.")

    return get_llm_gateway().speech_to_text(
        audio_bytes=audio_bytes,
        filename=filename,
        mime_type=audio.content_type,
    )
