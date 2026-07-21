from schemas.schemaV3 import AdaptiveInterviewState,AnswerAnalysis,InterviewDecision

DIFFICULTY_LEVELS = ["easy", "medium", "hard"]

def calculate_overall_score(analysis: AnswerAnalysis) -> float:

    total_score = (
        analysis.correctness_score
        + analysis.completeness_score
        + analysis.clarity_score
        + analysis.practical_understanding_score
    )
    
    return round(total_score / 4, 2)


def increase_difficulty(current_difficulty: str) -> str:

    current_index = DIFFICULTY_LEVELS.index(current_difficulty)

    if current_index < len(DIFFICULTY_LEVELS) - 1:
        return DIFFICULTY_LEVELS[current_index + 1]
    
    return current_difficulty

def decrease_difficulty(current_difficulty: str) -> str:

    current_index = DIFFICULTY_LEVELS.index(current_difficulty)

    if current_index > 0:
        return DIFFICULTY_LEVELS[current_index - 1]
    
    return current_difficulty

def get_remaining_skills(state: AdaptiveInterviewState) -> list[str]:

    return [
        skill
        for skill in state.selected_skills
        if skill not in state.completed_skills
        and skill != state.current_skill
    ]


def should_finish_interview(state: AdaptiveInterviewState) -> bool:

    if state.current_question_number >= state.maximum_questions:
        return True
    
    all_skills_completed = all(skill in state.completed_skills for skill in state.selected_skills)

    return all_skills_completed


def decide_next_step(analysis: AnswerAnalysis,state: AdaptiveInterviewState) -> InterviewDecision:

    overall_score = calculate_overall_score(analysis)

    # Rule 1: Stop when maximum questions are reached.
    if state.current_question_number >= state.maximum_questions:
        return InterviewDecision(
            action="finish",
            next_difficulty=state.current_difficulty,
            reason=(
                "The maximum number of interview questions "
                "has been reached."
            ),
        )
    
    # Rule 2: Move to another skill when the current skill limit is reached.
    if (state.questions_for_current_skill >= state.maximum_questions_per_skill):

        remaining_skills = get_remaining_skills(state)

        if remaining_skills:
            return InterviewDecision(
                action="change_skill",
                next_difficulty="medium",
                next_skill=remaining_skills[0],
                reason=(
                    f"The maximum number of questions for "
                    f"{state.current_skill} has been reached."
                ),
            )

        return InterviewDecision(
            action="finish",
            next_difficulty=state.current_difficulty,
            reason=(
                "The selected skills have received enough "
                "interview coverage."
            ),
        )

    # Rule 3: Very weak or incorrect answer.
    if overall_score < 4:
        if (state.clarification_attempts < state.maximum_clarification_attempts):

            focus = _get_question_focus(analysis)

            return InterviewDecision(
                action="clarify",
                next_difficulty=decrease_difficulty(
                    state.current_difficulty
                ),
                question_focus=focus,
                reason=(
                    "The answer demonstrates weak understanding, "
                    "so one simpler clarification question should "
                    "be asked."
                ),
            )

        return InterviewDecision(
            action="change_topic",
            next_difficulty="easy",
            reason=(
                "The clarification limit has been reached, so the "
                "interview should move to another topic."
            ),
        )
    
    # Rule 4: Partially correct or incomplete answer.
    if overall_score < 7:
        focus = _get_question_focus(analysis)

        return InterviewDecision(
            action="follow_up",
            next_difficulty=state.current_difficulty,
            question_focus=focus,
            reason=(
                "The answer shows partial understanding, so a "
                "follow-up should examine the missing concepts."
            ),
        )
    
    # Rule 5: Good answer, but not yet exceptional.
    if overall_score < 8.5:
        focus = _get_question_focus(analysis)

        if analysis.missing_concepts:
            return InterviewDecision(
                action="follow_up",
                next_difficulty=state.current_difficulty,
                question_focus=focus,
                reason=(
                    "The answer is generally correct, but some "
                    "important concepts still require examination."
                ),
            )

        return InterviewDecision(
            action="deepen_topic",
            next_difficulty=increase_difficulty(
                state.current_difficulty
            ),
            question_focus=focus,
            reason=(
                "The answer demonstrates good understanding, so "
                "the next question should test greater depth."
            ),
        )

    # Rule 6: Strong answer.
    if state.current_difficulty != "hard":
        return InterviewDecision(
            action="deepen_topic",
            next_difficulty=increase_difficulty(
                state.current_difficulty
            ),
            question_focus=_get_question_focus(analysis),
            reason=(
                "The answer demonstrates strong understanding, "
                "so the difficulty should be increased."
            ),
        )
    
     # Rule 7: Strong answer at hard difficulty.
    return InterviewDecision(
        action="change_topic",
        next_difficulty="medium",
        reason=(
            "The candidate performed strongly at hard difficulty, "
            "so enough evidence has been collected for this topic."
        ),
    )


def _get_question_focus(analysis: AnswerAnalysis) -> str | None:
    
    if analysis.misconceptions:
        return analysis.misconceptions[0]
    
    if analysis.missing_concepts:
        return analysis.missing_concepts[0]
    
    return analysis.follow_up_focus