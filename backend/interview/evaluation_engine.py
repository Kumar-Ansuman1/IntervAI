"""Compatibility imports for the fixed interview evaluation service."""

from backend.app.services.interview.evaluation_engine import (
    evaluate_interview_answers,
)

__all__ = ["evaluate_interview_answers"]
