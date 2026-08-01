from pydantic import BaseModel


class TextToSpeechRequest(BaseModel):
    text: str
    filename: str = "question.wav"


class TextToSpeechResponse(BaseModel):
    audio_path: str


class SpeechToTextResponse(BaseModel):
    transcript: str
