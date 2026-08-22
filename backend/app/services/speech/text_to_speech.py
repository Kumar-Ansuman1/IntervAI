import uuid
from pathlib import Path

from backend.app.services.llm.gateway import get_llm_gateway

OUTPUT_DIR = Path("temp/audio")


def text_to_speech(
    text: str,
    filename: str = f"{uuid.uuid4()}.wav",
    voice_name: str | None = None,
) -> str:
    output_path = OUTPUT_DIR / filename
    return get_llm_gateway().text_to_speech(
        text=text,
        output_path=output_path,
        voice=voice_name,
    )


if __name__ == "__main__":
    audio_file = text_to_speech(
        "Welcome to IntervAI. Let's begin your interview."
    )

    print(f"Audio saved to: {audio_file}")
