from backend.interview.interview_controller import calculate_overall_score,decide_next_step

from schemas.schemaV3 import AdaptiveInterviewState,AnswerAnalysis

def create_test_state(
    difficulty: str = "medium",
    question_number: int = 1,
    questions_for_current_skill: int = 1,
    clarification_attempts: int = 0,
) -> AdaptiveInterviewState:
    
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
        current_difficulty=difficulty,
        current_question_number=question_number,
        maximum_questions=8,
        questions_for_current_skill=questions_for_current_skill,
        maximum_questions_per_skill=3,
        clarification_attempts=clarification_attempts,
        maximum_clarification_attempts=1,
    )




def test_weak_answer() -> None:
    analysis = AnswerAnalysis(
        correctness_score=2,
        completeness_score=2,
        clarity_score=4,
        practical_understanding_score=1,
        strengths=[],
        missing_concepts=[
            "Mutability",
            "Use cases",
        ],
        misconceptions=[
            "Lists and tuples are the same",
        ],
        feedback="The answer contains a major misconception.",
        recommended_action="clarify",
        recommended_difficulty="easier",
        follow_up_focus="Mutability",
    )

    state = create_test_state()

    decision = decide_next_step(
        analysis=analysis,
        state=state,
    )

    print("\nWEAK ANSWER")
    print("-" * 50)
    print(f"Score: {calculate_overall_score(analysis)}")
    print(f"Action: {decision.action}")
    print(f"Difficulty: {decision.next_difficulty}")
    print(f"Focus: {decision.question_focus}")
    print(f"Reason: {decision.reason}")

    assert decision.action == "clarify", (
    f"Expected 'clarify', but received '{decision.action}'"
    )

    assert decision.next_difficulty == "easy", (
    f"Expected 'easy', but received '{decision.next_difficulty}'"
    )



def test_average_answer() -> None:
    analysis = AnswerAnalysis(
        correctness_score=7,
        completeness_score=5,
        clarity_score=7,
        practical_understanding_score=5,
        strengths=[
            "Correctly identified mutability",
        ],
        missing_concepts=[
            "Practical use cases",
        ],
        misconceptions=[],
        feedback=(
            "The answer is correct but lacks practical depth."
        ),
        recommended_action="follow_up",
        recommended_difficulty="same",
        follow_up_focus="Practical use cases",
    )

    state = create_test_state()

    decision = decide_next_step(
        analysis=analysis,
        state=state,
    )

    print("\nAVERAGE ANSWER")
    print("-" * 50)
    print(f"Score: {calculate_overall_score(analysis)}")
    print(f"Action: {decision.action}")
    print(f"Difficulty: {decision.next_difficulty}")
    print(f"Focus: {decision.question_focus}")
    print(f"Reason: {decision.reason}")

    assert decision.action == "follow_up"
    assert decision.next_difficulty == "medium"


def test_strong_answer() -> None:
    analysis = AnswerAnalysis(
        correctness_score=9,
        completeness_score=9,
        clarity_score=9,
        practical_understanding_score=8,
        strengths=[
            "Correct technical explanation",
            "Included practical use cases",
        ],
        missing_concepts=[],
        misconceptions=[],
        feedback=(
            "The answer demonstrates strong technical understanding."
        ),
        recommended_action="deepen_topic",
        recommended_difficulty="harder",
        follow_up_focus="Memory and performance differences",
    )

    state = create_test_state(
        difficulty="medium",
    )

    decision = decide_next_step(
        analysis=analysis,
        state=state,
    )

    print("\nSTRONG ANSWER")
    print("-" * 50)
    print(f"Score: {calculate_overall_score(analysis)}")
    print(f"Action: {decision.action}")
    print(f"Difficulty: {decision.next_difficulty}")
    print(f"Focus: {decision.question_focus}")
    print(f"Reason: {decision.reason}")

    assert decision.action == "deepen_topic"
    assert decision.next_difficulty == "hard"


def test_skill_question_limit() -> None:
    analysis = AnswerAnalysis(
        correctness_score=7,
        completeness_score=7,
        clarity_score=7,
        practical_understanding_score=7,
        strengths=[],
        missing_concepts=[],
        misconceptions=[],
        feedback="Good answer.",
        recommended_action="change_topic",
        recommended_difficulty="same",
        follow_up_focus=None,
    )

    state = create_test_state(
        questions_for_current_skill=3,
    )

    decision = decide_next_step(
        analysis=analysis,
        state=state,
    )

    print("\nSKILL QUESTION LIMIT")
    print("-" * 50)
    print(f"Action: {decision.action}")
    print(f"Next skill: {decision.next_skill}")
    print(f"Reason: {decision.reason}")

    assert decision.action == "change_skill"
    assert decision.next_skill == "FastAPI"



def test_maximum_question_limit() -> None:
    analysis = AnswerAnalysis(
        correctness_score=8,
        completeness_score=8,
        clarity_score=8,
        practical_understanding_score=8,
        strengths=[],
        missing_concepts=[],
        misconceptions=[],
        feedback="Strong answer.",
        recommended_action="deepen_topic",
        recommended_difficulty="harder",
        follow_up_focus="Advanced implementation",
    )

    state = create_test_state(
        question_number=8,
    )

    decision = decide_next_step(
        analysis=analysis,
        state=state,
    )

    print("\nMAXIMUM QUESTION LIMIT")
    print("-" * 50)
    print(f"Action: {decision.action}")
    print(f"Reason: {decision.reason}")

    assert decision.action == "finish"


if __name__ == "__main__":
    test_weak_answer()
    test_average_answer()
    test_strong_answer()
    test_skill_question_limit()
    test_maximum_question_limit()

    print("\nAll interview controller tests passed.")

