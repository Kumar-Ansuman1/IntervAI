"""Compatibility imports for the relocated adaptive interview workflow."""

from backend.app.workflows.interview.interview_manager import (
    finish_interview,
    get_interview_state,
    interview_sessions,
    process_answer,
    start_interview,
)

__all__ = [
    "finish_interview",
    "get_interview_state",
    "interview_sessions",
    "process_answer",
    "start_interview",
]
