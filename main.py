from fastapi import FastAPI, UploadFile, File, HTTPException
from tools import pdfextractor,question_generate
from schemas.schema import InterviewQuestion, InterviewPrepResponse,InterviewPrepRequest



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