from fastapi import APIRouter, HTTPException

from backend.app.schemas.adaptive import (
    AdaptiveAnswerRequest,
    AdaptiveInterviewStartRequest,
    AdaptiveInterviewState,
    AnswerProcessingResult,
    FinishAdaptiveInterviewRequest,
    InterviewStartResult,
)
from backend.app.workflows.interview.interview_manager import (
    finish_interview,
    get_interview_state,
    process_answer,
    start_interview,
)


router = APIRouter()


@router.post(
    "/adaptive-interview/start",
    response_model=InterviewStartResult,
)
def start_adaptive_interview(
    request: AdaptiveInterviewStartRequest,
) -> InterviewStartResult:
    try:
        return start_interview(
            candidate_name=request.candidate_name,
            skills=request.skills,
            maximum_questions=request.maximum_questions,
            maximum_questions_per_skill=request.maximum_questions_per_skill,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@router.post(
    "/adaptive-interview/answer",
    response_model=AnswerProcessingResult,
)
def submit_adaptive_answer(
    request: AdaptiveAnswerRequest,
) -> AnswerProcessingResult:
    try:
        return process_answer(
            interview_id=request.interview_id,
            candidate_answer=request.candidate_answer,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


@router.get(
    "/adaptive-interview/{interview_id}",
    response_model=AdaptiveInterviewState,
)
def get_adaptive_interview(
    interview_id: str,
) -> AdaptiveInterviewState:
    try:
        return get_interview_state(interview_id)

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error


@router.post(
    "/adaptive-interview/finish",
    response_model=AdaptiveInterviewState,
)
def finish_adaptive_interview(
    request: FinishAdaptiveInterviewRequest,
) -> AdaptiveInterviewState:
    try:
        return finish_interview(
            interview_id=request.interview_id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error
