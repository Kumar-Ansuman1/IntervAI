import traceback

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.schemas.speech import (
    SpeechToTextResponse,
    TextToSpeechRequest,
    TextToSpeechResponse,
)
from backend.app.services.speech.speech_to_text import speech_to_text
from backend.app.services.speech.text_to_speech import text_to_speech


router = APIRouter()


@router.post("/text-to-speech", response_model=TextToSpeechResponse)
async def text_to_speech_endpoint(request: TextToSpeechRequest):
    try:
        audio_path = text_to_speech(
            text=request.text,
            filename=request.filename,
        )

        return TextToSpeechResponse(audio_path=audio_path)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate speech: {str(error)}",
        )


@router.post("/speech-to-text", response_model=SpeechToTextResponse)
async def speech_to_text_endpoint(audio: UploadFile = File(...)):
    try:
        transcript = speech_to_text(audio)

        return SpeechToTextResponse(transcript=transcript)

    except Exception as error:
        traceback.print_exc()
        print(error)
        raise HTTPException(status_code=500, detail=str(error))
