from backend.app.domain.interview.controller import decide_next_step
from backend.app.schemas.interview import (
    AdaptiveInterviewState,
    AnswerProcessingResult,
    InterviewStartResult,
)
from backend.app.services.interview.answer_analyzer import analyze_answer
from backend.app.services.interview.question_generator import (
    generate_adaptive_question,
    generate_initial_question,
)
from backend.app.workflows.interview.graph import InterviewWorkflow


interview_workflow = InterviewWorkflow(
    analyze_answer=analyze_answer,
    generate_initial_question=generate_initial_question,
    generate_adaptive_question=generate_adaptive_question,
    decide_next_step=decide_next_step,
)


def start_interview(
    candidate_name: str,
    skills: list[str],
    maximum_questions: int = 8,
    maximum_questions_per_skill: int = 3,
) -> InterviewStartResult:
    return interview_workflow.start(
        candidate_name=candidate_name,
        skills=skills,
        maximum_questions=maximum_questions,
        maximum_questions_per_skill=maximum_questions_per_skill,
    )


def get_interview_state(
    interview_id: str,
) -> AdaptiveInterviewState:
    return interview_workflow.get_interview_state(interview_id)


def process_answer(
    interview_id: str,
    candidate_answer: str,
) -> AnswerProcessingResult:
    return interview_workflow.process_answer(
        interview_id=interview_id,
        candidate_answer=candidate_answer,
    )


def finish_interview(
    interview_id: str,
) -> AdaptiveInterviewState:
    return interview_workflow.finish(interview_id)
