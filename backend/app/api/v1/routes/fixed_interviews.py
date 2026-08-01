from fastapi import APIRouter, HTTPException

from backend.app.schemas.schema import (
    EvaluationRequest,
    InterviewPrepRequest,
    InterviewPrepResponse,
    InterviewScorecard,
)
from backend.app.services.interview import evaluation_engine, question_generate


router = APIRouter()


@router.post("/generate-questions", response_model=InterviewPrepResponse)
async def generate_questions_endpoint(request: InterviewPrepRequest):
    try:
        if not request.skills:
            raise HTTPException(
                status_code=400,
                detail="The skills list cannot be empty.",
            )

        generated_questions = question_generate.generate_interview_questions(
            candidate_name=request.candidate_name,
            skills_list=request.skills,
        )

        return generated_questions

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate interview questions: {str(error)}",
        )


@router.post("/evaluate", response_model=InterviewScorecard)
async def evaluate_endpoint(request: EvaluationRequest):
    try:
        if not request.submissions:
            raise HTTPException(
                status_code=400,
                detail="Submission tracker is empty. No answers were provided.",
            )

        scorecard_results = evaluation_engine.evaluate_interview_answers(request)
        return scorecard_results

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation Engine Error: {str(error)}",
        )
