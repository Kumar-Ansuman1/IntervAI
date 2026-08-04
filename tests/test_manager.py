import pytest

from backend.app.domain.interview.controller import decide_next_step
from backend.app.schemas.interview import (
    AdaptiveQuestion,
    AnswerAnalysis,
)
from backend.app.workflows.interview.graph import InterviewWorkflow


def _analysis(score: int = 6) -> AnswerAnalysis:
    return AnswerAnalysis(
        correctness_score=score,
        completeness_score=score,
        clarity_score=score,
        practical_understanding_score=score,
        strengths=["Explained the core concept"],
        missing_concepts=["Practical trade-offs"],
        misconceptions=[],
        feedback="The answer needs more practical depth.",
        recommended_action="follow_up",
        recommended_difficulty="same",
        follow_up_focus="Practical trade-offs",
    )


def _initial_question(**_kwargs) -> AdaptiveQuestion:
    return AdaptiveQuestion(
        question="How do Python lists manage mutable data?",
        skill="Python",
        topic="Data structures",
        difficulty="medium",
        question_type="initial",
        focus="List mutability",
    )


def _adaptive_question(*, state, decision, **_kwargs) -> AdaptiveQuestion:
    question_types = {
        "clarify": "clarification",
        "follow_up": "follow_up",
        "deepen_topic": "deeper",
        "change_topic": "new_topic",
        "change_skill": "new_skill",
    }
    target_skill = decision.next_skill or state.current_skill
    target_topic = (
        "Routing"
        if decision.action == "change_skill"
        else state.current_topic or "Core concepts"
    )

    return AdaptiveQuestion(
        question=f"What trade-offs matter when using {target_skill}?",
        skill=target_skill,
        topic=target_topic,
        difficulty=decision.next_difficulty,
        question_type=question_types[decision.action],
        focus=decision.question_focus or "Technical trade-offs",
    )


def _workflow(
    *,
    analyze_answer=lambda **_kwargs: _analysis(),
    generate_adaptive_question=_adaptive_question,
) -> InterviewWorkflow:
    return InterviewWorkflow(
        analyze_answer=analyze_answer,
        generate_initial_question=_initial_question,
        generate_adaptive_question=generate_adaptive_question,
        decide_next_step=decide_next_step,
    )


def test_workflow_starts_and_checkpoints_interview_state() -> None:
    workflow = _workflow()
    result = workflow.start(
        candidate_name=" Kumar ",
        skills=[" Python ", "python", "FastAPI"],
        maximum_questions=4,
        maximum_questions_per_skill=2,
    )

    state = workflow.get_interview_state(result.interview_id)

    assert state.candidate_name == "Kumar"
    assert state.selected_skills == ["Python", "FastAPI"]
    assert state.current_question_number == 1
    assert len(state.interview_history) == 1
    assert state.interview_history[0].answer is None


def test_answer_runs_analysis_decision_and_question_nodes() -> None:
    workflow = _workflow()
    started = workflow.start(
        candidate_name="Kumar",
        skills=["Python", "FastAPI"],
        maximum_questions=4,
        maximum_questions_per_skill=2,
    )

    result = workflow.process_answer(
        interview_id=started.interview_id,
        candidate_answer="Lists are mutable collections.",
    )
    state = workflow.get_interview_state(started.interview_id)

    assert result.decision.action == "follow_up"
    assert result.next_question_number == 2
    assert result.next_question is not None
    assert state.current_question_number == 2
    assert len(state.interview_history) == 2
    assert state.interview_history[0].answer is not None
    assert state.interview_history[0].analysis is not None
    assert state.interview_history[1].answer is None


def test_controller_finish_branch_ends_the_interview() -> None:
    workflow = _workflow()
    started = workflow.start(
        candidate_name="Kumar",
        skills=["Python"],
        maximum_questions=1,
    )

    result = workflow.process_answer(
        interview_id=started.interview_id,
        candidate_answer="Lists are mutable collections.",
    )
    state = workflow.get_interview_state(started.interview_id)

    assert result.decision.action == "finish"
    assert result.next_question is None
    assert result.interview_finished is True
    assert state.interview_finished is True
    assert state.completed_skills == ["Python"]


def test_failed_node_can_resume_without_repeating_analysis() -> None:
    calls = {"analysis": 0, "question": 0}

    def analyze(**_kwargs) -> AnswerAnalysis:
        calls["analysis"] += 1
        return _analysis()

    def generate_question(**kwargs) -> AdaptiveQuestion:
        calls["question"] += 1

        if calls["question"] == 1:
            raise RuntimeError("Temporary model failure")

        return _adaptive_question(**kwargs)

    workflow = _workflow(
        analyze_answer=analyze,
        generate_adaptive_question=generate_question,
    )
    started = workflow.start(
        candidate_name="Kumar",
        skills=["Python"],
        maximum_questions=3,
    )

    with pytest.raises(RuntimeError, match="Temporary model failure"):
        workflow.process_answer(
            interview_id=started.interview_id,
            candidate_answer="Lists are mutable collections.",
        )

    result = workflow.process_answer(
        interview_id=started.interview_id,
        candidate_answer="Lists are mutable collections.",
    )

    assert result.next_question_number == 2
    assert calls == {"analysis": 1, "question": 2}


def test_manual_finish_updates_the_checkpoint() -> None:
    workflow = _workflow()
    started = workflow.start(
        candidate_name="Kumar",
        skills=["Python"],
    )

    finished = workflow.finish(started.interview_id)
    stored = workflow.get_interview_state(started.interview_id)

    assert finished.interview_finished is True
    assert stored.interview_finished is True
    assert stored.completed_skills == ["Python"]


def test_manual_finish_can_cancel_a_failed_answer_run() -> None:
    def unavailable_question_generator(**_kwargs) -> AdaptiveQuestion:
        raise RuntimeError("Question service unavailable")

    workflow = _workflow(
        generate_adaptive_question=unavailable_question_generator,
    )
    started = workflow.start(
        candidate_name="Kumar",
        skills=["Python"],
        maximum_questions=3,
    )

    with pytest.raises(RuntimeError, match="Question service unavailable"):
        workflow.process_answer(
            interview_id=started.interview_id,
            candidate_answer="Lists are mutable collections.",
        )

    finished = workflow.finish(started.interview_id)
    stored = workflow.get_interview_state(started.interview_id)

    assert finished.interview_finished is True
    assert stored.interview_finished is True
    assert stored.completed_skills == ["Python"]
