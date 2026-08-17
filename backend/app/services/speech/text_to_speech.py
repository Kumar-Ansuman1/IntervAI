import os
import uuid
import wave
from pathlib import Path

import logfire
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

OUTPUT_DIR = Path("temp/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TTS_MODEL = "gemini-3.1-flash-tts-preview"


def save_wave_file(
    filename: str,
    pcm_data: bytes,
    channels: int = 1,
    sample_rate: int = 24000,
    sample_width: int = 2,
):
    """Save PCM audio bytes as a WAV file."""
    with logfire.span(
        "text-to-speech: write WAV file",
        audio_size_bytes=len(pcm_data),
        channels=channels,
        sample_rate=sample_rate,
        sample_width=sample_width,
    ):
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data)


def text_to_speech(
    text: str,
    filename: str = f"{uuid.uuid4()}.wav",
    voice_name: str = "Kore",
) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables")

    client = genai.Client(api_key=api_key)

    with logfire.span(
        "text-to-speech: generate audio",
        model_name=TTS_MODEL,
        text_character_count=len(text),
        voice_name=voice_name,
    ) as span:
        response = client.models.generate_content(
            model=TTS_MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice_name
                        )
                    )
                ),
            ),
        )

        audio_data = response.candidates[0].content.parts[0].inline_data.data
        span.set_attribute("audio_size_bytes", len(audio_data))

    output_path = OUTPUT_DIR / filename
    save_wave_file(str(output_path), audio_data)

    return str(output_path)


if __name__ == "__main__":
    audio_file = text_to_speech(
        "Welcome to IntervAI. Let's begin your interview."
    )

    print(f"Audio saved to: {audio_file}")
