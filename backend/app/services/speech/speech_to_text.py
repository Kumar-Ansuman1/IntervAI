import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import UploadFile
from google import genai

load_dotenv()


def speech_to_text(audio: UploadFile) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found.")

    client = genai.Client(api_key=api_key)

    # Save uploaded file temporarily
    suffix = Path(audio.filename).suffix or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(audio.file.read())
        temp_path = temp_file.name

    try:
        # Upload temporary file to Gemini
        uploaded_file = client.files.upload(file=temp_path)

        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[
                "Transcribe this interview answer. Return only the transcript.",
                uploaded_file,
            ],
        )

        return response.text.strip()

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)