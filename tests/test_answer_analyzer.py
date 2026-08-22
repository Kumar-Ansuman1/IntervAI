from typing import Any

from backend.app.schemas.interview import AnswerAnalysis
from backend.app.services.interview import answer_analyzer as analyzer_module
from backend.app.services.interview.answer_analyzer import (
    analyze_answer,
    calculate_overall_score,
)
from backend.app.services.llm.gateway import LLMTask


class FakeGateway:
    def __init__(self, result: AnswerAnalysis) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def generate_structured(self, **kwargs: Any) -> AnswerAnalysis:
        self.calls.append(kwargs)
        return self.result


def test_answer_analyzer_uses_gateway(monkeypatch) -> None:
    expected = AnswerAnalysis(
        correctness_score=9,
        completeness_score=8,
        clarity_score=9,
        practical_understanding_score=8,
        strengths=["Correctly explains mutability."],
        missing_concepts=[],
        misconceptions=[],
        feedback="Clear and technically correct.",
        recommended_action="deepen_topic",
        recommended_difficulty="harder",
        follow_up_focus="Performance trade-offs",
    )
    gateway = FakeGateway(expected)
    monkeypatch.setattr(
        analyzer_module,
        "get_llm_gateway",
        lambda: gateway,
    )

    analysis = analyze_answer(
        question="What is the difference between a list and a tuple?",
        candidate_answer="Lists are mutable and tuples are immutable.",
        skill="Python",
        topic="Data structures",
        difficulty="easy",
    )

    assert analysis == expected
    assert calculate_overall_score(analysis) == 8.5
    assert len(gateway.calls) == 1
    call = gateway.calls[0]
    assert call["task"] is LLMTask.ANSWER_ANALYSIS
    assert call["response_model"] is AnswerAnalysis
    assert call["temperature"] == 0
    assert "What is the difference between a list and a tuple?" in call["prompt"]
    assert "Lists are mutable and tuples are immutable." in call["prompt"]
