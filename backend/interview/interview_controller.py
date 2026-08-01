"""Compatibility imports for the relocated interview policy."""

from backend.app.domain.interview.interview_controller import (
    DIFFICULTY_LEVELS,
    calculate_overall_score,
    decide_next_step,
    decrease_difficulty,
    get_remaining_skills,
    increase_difficulty,
    should_finish_interview,
)

__all__ = [
    "DIFFICULTY_LEVELS",
    "calculate_overall_score",
    "decide_next_step",
    "decrease_difficulty",
    "get_remaining_skills",
    "increase_difficulty",
    "should_finish_interview",
]
