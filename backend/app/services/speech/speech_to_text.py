import os
import tempfile
from pathlib import Path

import logfire
from dotenv import load_dotenv
from fastapi import UploadFile
from google import genai

load_dotenv()

STT_MODEL = "gemini-3.1-flash-lite"


def speech_to_text(audio: UploadFile) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found.")

    client = genai.Client(api_key=api_key)
    suffix = Path(audio.filename).suffix or ".wav"

    with logfire.span(
        "speech-to-text: save temporary audio",
        audio_format=suffix,
    ) as span:
        audio_bytes = audio.file.read()
        span.set_attribute("audio_size_bytes", len(audio_bytes))

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

    try:
        with logfire.span(
            "speech-to-text: upload audio",
            audio_format=suffix,
            audio_size_bytes=len(audio_bytes),
        ):
            uploaded_file = client.files.upload(file=temp_path)

        with logfire.span(
            "speech-to-text: transcribe audio",
            model_name=STT_MODEL,
            audio_size_bytes=len(audio_bytes),
        ) as span:
            response = client.models.generate_content(
                model=STT_MODEL,
                contents=[
                    "Transcribe this interview answer. Return only the transcript.",
                    uploaded_file,
                ],
            )
            transcript = response.text.strip()
            span.set_attribute("transcript_character_count", len(transcript))

        return transcript

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
