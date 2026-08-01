"""Compatibility imports for the relocated answer analyzer service."""

from backend.app.services.interview.answer_analyzer import (
    analyze_answer,
    calculate_overall_score,
)

__all__ = ["analyze_answer", "calculate_overall_score"]
