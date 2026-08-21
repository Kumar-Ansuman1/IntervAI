from backend.app.services.interview import (
    question_generator as question_generator_module,
)
from backend.app.services.interview.question_generator import (
    generate_adaptive_question,
)

from backend.app.schemas.interview import (
    AdaptiveInterviewState,
    AdaptiveQuestion,
    AnswerAnalysis,
    InterviewDecision,
    InterviewTurn,
)


class FakeGateway:
    def __init__(self, result: AdaptiveQuestion) -> None:
        self.result = result

    def generate_structured(self, **_kwargs) -> AdaptiveQuestion:
        return self.result


def create_test_analysis() -> AnswerAnalysis:
    return AnswerAnalysis(
        correctness_score=7,
        completeness_score=5,
        clarity_score=8,
        practical_understanding_score=5,
        strengths=[
            "Correctly identified mutability",
        ],
        missing_concepts=[
            "Practical use cases",
            "Performance differences",
        ],
        misconceptions=[],
        feedback=(
            "The answer is correct but lacks practical depth."
        ),
        recommended_action="follow_up",
        recommended_difficulty="same",
        follow_up_focus="Practical use cases of tuples",
    )


def create_test_state() -> AdaptiveInterviewState:
    previous_turn = InterviewTurn(
        question_number=1,
        question=(
            "What is the difference between a "
            "Python list and a tuple?"
        ),
        answer=(
            "A list is mutable while a tuple "
            "is immutable."
        ),
        skill="Python",
        topic="Data structures",
        difficulty="medium",
        question_type="initial",
        analysis=create_test_analysis(),
    )

    return AdaptiveInterviewState(
        interview_id="test-interview-001",
        candidate_name="Kumar",
        selected_skills=[
            "Python",
            "FastAPI",
            "Machine Learning",
        ],
        current_skill="Python",
        current_topic="Data structures",
        current_difficulty="medium",
        current_question_number=1,
        maximum_questions=8,
        questions_for_current_skill=1,
        maximum_questions_per_skill=3,
        clarification_attempts=0,
        maximum_clarification_attempts=1,
        covered_topics=[
            "Data structures",
        ],
        interview_history=[
            previous_turn,
        ],
        interview_finished=False,
    )


def test_follow_up_question(monkeypatch) -> None:
    analysis = create_test_analysis()
    state = create_test_state()

    decision = InterviewDecision(
        action="clarify",
        next_difficulty="easy",
        question_focus="Meaning of mutability",
        reason="The candidate does not understand mutability.",
    )
    expected = AdaptiveQuestion(
        question="What does mutability mean in Python?",
        skill="Python",
        topic="Data structures",
        difficulty="easy",
        question_type="clarification",
        focus="Meaning of mutability",
    )
    monkeypatch.setattr(
        question_generator_module,
        "get_llm_gateway",
        lambda: FakeGateway(expected),
    )

    question = generate_adaptive_question(
        state=state,
        analysis=analysis,
        decision=decision,
    )

    assert question.skill.lower() == "python"
    assert question.difficulty == "easy"
    assert question.question_type == "clarification"
    assert question.question.endswith("?")
