from backend.app.workflows.interview.manager import (
    get_interview_state,
    process_answer,
    start_interview,
)


def test_interview_workflow_manager() -> None:
    start_result = start_interview(
        candidate_name="Kumar",
        skills=[
            "Python",
            "FastAPI",
        ],
        maximum_questions=4,
        maximum_questions_per_skill=2,
    )

    interview_id = start_result.interview_id

    print("\nINTERVIEW STARTED")
    print("-" * 50)
    print(f"Interview ID: {interview_id}")
    print(
        f"Question 1: "
        f"{start_result.question.question}"
    )
    print(
        f"Skill: {start_result.question.skill}"
    )
    print(
        f"Topic: {start_result.question.topic}"
    )

    answer_result = process_answer(
        interview_id=interview_id,
        candidate_answer=(
            "A Python list is an ordered and mutable "
            "collection that can contain duplicate values."
        ),
    )

    print("\nANSWER PROCESSED")
    print("-" * 50)
    print(
        f"Controller action: "
        f"{answer_result.decision.action}"
    )
    print(
        f"Next difficulty: "
        f"{answer_result.decision.next_difficulty}"
    )
    print(
        f"Interview finished: "
        f"{answer_result.interview_finished}"
    )

    if answer_result.next_question:
        print(
            f"Question "
            f"{answer_result.next_question_number}: "
            f"{answer_result.next_question.question}"
        )

    state = get_interview_state(interview_id)

    print("\nCURRENT STATE")
    print("-" * 50)
    print(
        f"Current question number: "
        f"{state.current_question_number}"
    )
    print(
        f"Current skill: {state.current_skill}"
    )
    print(
        f"Current topic: {state.current_topic}"
    )
    print(
        f"History length: "
        f"{len(state.interview_history)}"
    )

    assert state.current_question_number == 2
    assert len(state.interview_history) == 2
    assert state.interview_history[0].answer is not None
    assert state.interview_history[0].analysis is not None
    assert state.interview_history[1].answer is None


if __name__ == "__main__":
    test_interview_workflow_manager()

    print(
        "\nInterview manager test passed."
    )
