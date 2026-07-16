import wave
import os
from pathlib import Path
import uuid
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


OUTPUT_DIR = Path("temp/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_wave_file(filename: str, pcm_data: bytes, channels: int = 1, sample_rate: int = 24000,sample_width: int = 2,):

    """
    Save PCM audio bytes as a WAV file.
    """

    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)

def text_to_speech(text: str, filename: str = f"{uuid.uuid4()}.wav", voice_name: str = "Kore",) -> str:

    api_key = os.getenv("GOOGLE_API_KEY")

    client = genai.Client(api_key=api_key)

    if not api_key:
        raise ValueError("GOOGLE_API_KEY not found in environment variables")
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-tts-preview",
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


    output_path = OUTPUT_DIR / filename

    audio_data = response.candidates[0].content.parts[0].inline_data.data

    save_wave_file(str(output_path), audio_data)

    return str(output_path)

if __name__ == "__main__":
    audio_file = text_to_speech(
        "Welcome to IntervAI. Let's begin your interview."
    )

    print(f"Audio saved to: {audio_file}")

