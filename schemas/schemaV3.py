"""Compatibility imports for the relocated adaptive interview schemas."""

from backend.app.schemas.adaptive import (
    AdaptiveAnswerRequest,
    AdaptiveInterviewStartRequest,
    AdaptiveInterviewState,
    AdaptiveQuestion,
    AnswerAnalysis,
    AnswerProcessingResult,
    FinishAdaptiveInterviewRequest,
    InterviewDecision,
    InterviewStartResult,
    InterviewTurn,
)

__all__ = [
    "AdaptiveAnswerRequest",
    "AdaptiveInterviewStartRequest",
    "AdaptiveInterviewState",
    "AdaptiveQuestion",
    "AnswerAnalysis",
    "AnswerProcessingResult",
    "FinishAdaptiveInterviewRequest",
    "InterviewDecision",
    "InterviewStartResult",
    "InterviewTurn",
]
