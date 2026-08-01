"""Compatibility imports for the relocated adaptive question service."""

from backend.app.services.interview.adaptive_question_generator import (
    generate_adaptive_question,
    generate_initial_question,
)

__all__ = ["generate_adaptive_question", "generate_initial_question"]
