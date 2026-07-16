from fastapi import FastAPI, UploadFile, File, HTTPException
from backend.resume import pdfextractor
from backend.interview import question_generate,evaluation_engine
from schemas.schema import InterviewQuestion, InterviewPrepResponse,InterviewPrepRequest, EvaluationRequest, InterviewScorecard,TextToSpeechRequest, TextToSpeechResponse,SpeechToTextResponse
from backend.speech.text_to_speech import text_to_speech
from backend.speech.speech_to_text import speech_to_text
import traceback




app = FastAPI(title="IntervAI API")

@app.get("/")
def home():
    return {"status": "healthy", "project": "IntervAI"}

@app.post("/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=415, 
            detail="Unsupported file format. Please upload a valid PDF document."
        )
    
    try:
        pdf_bytes = await file.read()

        if len(pdf_bytes) == 0:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file stream is empty."
            )
        
        parsed_resume_data = pdfextractor.extract_resume_details(pdf_bytes)

        return parsed_resume_data
    
    except HTTPException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal Processing Error: {str(e)}"
        )

@app.post("/generate-questions", response_model=InterviewPrepResponse)
async def generate_questions_endpoint(request: InterviewPrepRequest):
    
    try:
        if not request.skills:
            raise HTTPException(
                status_code=400,
                detail="The skills list cannot be empty."
            )
        generated_questions = question_generate.generate_interview_questions(
            candidate_name=request.candidate_name,
            skills_list=request.skills
        )
        
        return generated_questions
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate interview questions: {str(e)}"
        )
    
@app.post("/evaluate", response_model= InterviewScorecard)
async def evaluate_endpoint(request: EvaluationRequest):
    try:
        if not request.submissions:
            raise HTTPException(
                status_code=400,
                detail="Submission tracker is empty. No answers were provided."
            )

        scorecard_results = evaluation_engine.evaluate_interview_answers(request)
        return scorecard_results
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation Engine Error: {str(e)}"
        )
    
@app.post("/text-to-speech", response_model=TextToSpeechResponse)
async def text_to_speech_endpoint(request: TextToSpeechRequest):

    try:
        audio_path = text_to_speech(
            text=request.text,
            filename=request.filename
        )

        return TextToSpeechResponse(
            audio_path=audio_path
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate speech: {str(e)}"
        )
    
@app.post("/speech-to-text",response_model=SpeechToTextResponse)
async def speech_to_text_endpoint(audio: UploadFile = File(...)):

    try:
        transcript = speech_to_text(audio)

        return SpeechToTextResponse(transcript=transcript)
    
    except Exception as e:
        traceback.print_exc()      
        print(e)
        raise HTTPException(status_code=500,detail=str(e))