from uuid import uuid4

from backend.app.services.interview.adaptive_question_generator import (
    generate_adaptive_question,
    generate_initial_question,
)

from backend.app.services.interview.answer_analyzer import analyze_answer
from backend.app.domain.interview.interview_controller import decide_next_step

from backend.app.schemas.adaptive import (
    AdaptiveInterviewState,
    AdaptiveQuestion,
    AnswerProcessingResult,
    InterviewDecision,
    InterviewStartResult,
    InterviewTurn,
)

interview_sessions: dict[str, AdaptiveInterviewState] = {}

#It removes blank skills, extra spaces, and duplicate names.
def _clean_skills(skills: list[str],) -> list[str]:


    cleaned_skills: list[str] = []
    seen_skills: set[str] = set()

    for skill in skills:
        cleaned_skill = skill.strip()

        if not cleaned_skill:
            continue

        normalized_skill = cleaned_skill.lower()

        if normalized_skill not in seen_skills:
            cleaned_skills.append(cleaned_skill)
            seen_skills.add(normalized_skill)

    if not cleaned_skills:
        raise ValueError(
            "At least one valid technical skill is required."
        )

    return cleaned_skills

#Convert a generated question into a turn and stores it as memory
def _create_interview_turn(question_number: int,generated_question: AdaptiveQuestion) -> InterviewTurn:


    return InterviewTurn(
        question_number=question_number,
        question=generated_question.question,
        skill=generated_question.skill,
        topic=generated_question.topic,
        difficulty=generated_question.difficulty,
        question_type=generated_question.question_type,
    )



def start_interview(candidate_name: str,skills: list[str],maximum_questions: int = 8,maximum_questions_per_skill: int = 3,) -> InterviewStartResult:

    """
    Start a new adaptive interview.

    This function:
    1. Validates the candidate data.
    2. Generates the initial question.
    3. Creates the interview state.
    4. Stores the interview session.
    5. Returns the first question.
    """

    candidate_name = candidate_name.strip()

    if not candidate_name:
        raise ValueError(
            "Candidate name cannot be empty."
        )

    if maximum_questions < 1:
        raise ValueError(
            "Maximum questions must be at least 1."
        )

    if maximum_questions_per_skill < 1:
        raise ValueError(
            "Maximum questions per skill must be at least 1."
        )

    cleaned_skills = _clean_skills(skills)

    initial_question = generate_initial_question(
        candidate_name=candidate_name,
        skills_list=cleaned_skills,
    )

    interview_id = str(uuid4())

    initial_turn = _create_interview_turn(
        question_number=1,
        generated_question=initial_question,
    )

    state = AdaptiveInterviewState(
        interview_id=interview_id,
        candidate_name=candidate_name,
        selected_skills=cleaned_skills,
        current_skill=initial_question.skill,
        current_topic=initial_question.topic,
        current_difficulty=initial_question.difficulty,
        current_question_number=1,
        maximum_questions=maximum_questions,
        questions_for_current_skill=1,
        maximum_questions_per_skill=(
            maximum_questions_per_skill
        ),
        clarification_attempts=0,
        maximum_clarification_attempts=1,
        covered_topics=[
            initial_question.topic,
        ],
        interview_history=[
            initial_turn,
        ],
        interview_finished=False,
    )

    interview_sessions[interview_id] = state

    return InterviewStartResult(
        interview_id=interview_id,
        question_number=1,
        question=initial_question,
        interview_finished=False,
    )


def get_interview_state(interview_id: str) -> AdaptiveInterviewState:

    """
    Retrieve an adaptive interview state by ID.
    """

    interview_id = interview_id.strip()

    if not interview_id:
        raise ValueError(
            "Interview ID cannot be empty."
        )

    state = interview_sessions.get(interview_id)

    if state is None:
        raise ValueError(
            f"Interview session '{interview_id}' was not found."
        )

    return state

def _get_current_turn(state: AdaptiveInterviewState,) -> InterviewTurn:

    """
    Return the latest unanswered interview turn.
    """

    if not state.interview_history:
        raise ValueError(
            "The interview does not contain any questions."
        )

    current_turn = state.interview_history[-1]

    if current_turn.answer is not None:
        raise ValueError(
            "The current question has already been answered."
        )

    return current_turn

def _update_state_for_next_question(state: AdaptiveInterviewState,decision: InterviewDecision,next_question: AdaptiveQuestion) -> None:

    """
    Update interview state before storing the next question.
    """

    previous_skill = state.current_skill
    previous_topic = state.current_topic

    if decision.action == "change_skill":
        if previous_skill not in state.completed_skills:
            state.completed_skills.append(previous_skill)

        state.current_skill = next_question.skill
        state.current_topic = next_question.topic
        state.current_difficulty = next_question.difficulty

        state.questions_for_current_skill = 1
        state.clarification_attempts = 0

    elif decision.action == "change_topic":
        if (
            previous_topic
            and previous_topic not in state.covered_topics
        ):
            state.covered_topics.append(previous_topic)

        state.current_topic = next_question.topic
        state.current_difficulty = next_question.difficulty

        state.questions_for_current_skill += 1
        state.clarification_attempts = 0

    elif decision.action == "clarify":
        state.current_topic = next_question.topic
        state.current_difficulty = next_question.difficulty

        state.questions_for_current_skill += 1
        state.clarification_attempts += 1

    else:
        state.current_topic = next_question.topic
        state.current_difficulty = next_question.difficulty

        state.questions_for_current_skill += 1
        state.clarification_attempts = 0

    if (
        next_question.topic
        and next_question.topic not in state.covered_topics
    ):
        state.covered_topics.append(
            next_question.topic
        )

    state.current_question_number += 1


def process_answer(interview_id: str,candidate_answer: str,) -> AnswerProcessingResult:

    """
    Process one candidate answer and produce the next
    adaptive interview question.

    Flow:
    1. Retrieve the interview state.
    2. Save the candidate answer.
    3. Analyze the answer.
    4. Ask the controller for the next decision.
    5. Finish or generate the next question.
    6. Update the interview state.
    """

    candidate_answer = candidate_answer.strip()

    if not candidate_answer:
        raise ValueError(
            "Candidate answer cannot be empty."
        )

    state = get_interview_state(interview_id)

    if state.interview_finished:
        raise ValueError(
            "This interview has already finished."
        )

    current_turn = _get_current_turn(state)

    analysis = analyze_answer(
        question=current_turn.question,
        candidate_answer=candidate_answer,
        skill=current_turn.skill,
        topic=current_turn.topic,
        difficulty=current_turn.difficulty,
    )

    current_turn.answer = candidate_answer
    current_turn.analysis = analysis

    decision = decide_next_step(
        analysis=analysis,
        state=state,
    )

    if decision.action == "finish":
        state.interview_finished = True

        if (
            state.current_skill
            not in state.completed_skills
        ):
            state.completed_skills.append(
                state.current_skill
            )

        return AnswerProcessingResult(
            interview_id=interview_id,
            analysis=analysis,
            decision=decision,
            next_question_number=None,
            next_question=None,
            interview_finished=True,
        )

    next_question = generate_adaptive_question(
        state=state,
        analysis=analysis,
        decision=decision,
    )

    _update_state_for_next_question(
        state=state,
        decision=decision,
        next_question=next_question,
    )

    next_turn = _create_interview_turn(
        question_number=state.current_question_number,
        generated_question=next_question,
    )

    state.interview_history.append(next_turn)

    return AnswerProcessingResult(
        interview_id=interview_id,
        analysis=analysis,
        decision=decision,
        next_question_number=(
            state.current_question_number
        ),
        next_question=next_question,
        interview_finished=False,
    )

def finish_interview(interview_id: str,) -> AdaptiveInterviewState:

    """
    Manually finish an active interview.
    """

    state = get_interview_state(interview_id)

    if state.interview_finished:
        return state

    state.interview_finished = True

    if state.current_skill not in state.completed_skills:
        state.completed_skills.append(
            state.current_skill
        )

    return state
