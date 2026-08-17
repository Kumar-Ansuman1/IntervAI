from collections.abc import Callable
from typing import Literal, TypedDict
from uuid import uuid4

import logfire
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from backend.app.schemas.interview import (
    AdaptiveInterviewState,
    AdaptiveQuestion,
    AnswerAnalysis,
    AnswerProcessingResult,
    InterviewDecision,
    InterviewStartResult,
    InterviewTurn,
)


WorkflowOperation = Literal["start", "answer", "finish"]

AnswerAnalyzer = Callable[..., AnswerAnalysis]
InitialQuestionGenerator = Callable[..., AdaptiveQuestion]
AdaptiveQuestionGenerator = Callable[..., AdaptiveQuestion]
DecisionMaker = Callable[..., InterviewDecision]


class InterviewGraphState(TypedDict, total=False):
    operation: WorkflowOperation
    interview_id: str

    candidate_name: str
    skills: list[str]
    maximum_questions: int
    maximum_questions_per_skill: int

    candidate_answer: str
    interview: AdaptiveInterviewState
    analysis: AnswerAnalysis
    decision: InterviewDecision
    next_question: AdaptiveQuestion

    start_result: InterviewStartResult
    answer_result: AnswerProcessingResult


def _clean_skills(skills: list[str]) -> list[str]:
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


def _create_interview_turn(
    question_number: int,
    generated_question: AdaptiveQuestion,
) -> InterviewTurn:
    return InterviewTurn(
        question_number=question_number,
        question=generated_question.question,
        skill=generated_question.skill,
        topic=generated_question.topic,
        difficulty=generated_question.difficulty,
        question_type=generated_question.question_type,
    )


def _get_current_turn(
    interview: AdaptiveInterviewState,
) -> InterviewTurn:
    if not interview.interview_history:
        raise ValueError(
            "The interview does not contain any questions."
        )

    current_turn = interview.interview_history[-1]

    if current_turn.answer is not None:
        raise ValueError(
            "The current question has already been answered."
        )

    return current_turn


def _finish_interview_state(
    interview: AdaptiveInterviewState,
) -> AdaptiveInterviewState:
    finished_interview = interview.model_copy(deep=True)
    finished_interview.interview_finished = True

    if (
        finished_interview.current_skill
        not in finished_interview.completed_skills
    ):
        finished_interview.completed_skills.append(
            finished_interview.current_skill
        )

    return finished_interview


def _advance_interview(
    interview: AdaptiveInterviewState,
    decision: InterviewDecision,
    next_question: AdaptiveQuestion,
) -> AdaptiveInterviewState:
    updated_interview = interview.model_copy(deep=True)
    previous_skill = updated_interview.current_skill
    previous_topic = updated_interview.current_topic

    if decision.action == "change_skill":
        if previous_skill not in updated_interview.completed_skills:
            updated_interview.completed_skills.append(previous_skill)

        updated_interview.current_skill = next_question.skill
        updated_interview.questions_for_current_skill = 1
        updated_interview.clarification_attempts = 0

    elif decision.action == "change_topic":
        if (
            previous_topic
            and previous_topic not in updated_interview.covered_topics
        ):
            updated_interview.covered_topics.append(previous_topic)

        updated_interview.questions_for_current_skill += 1
        updated_interview.clarification_attempts = 0

    elif decision.action == "clarify":
        updated_interview.questions_for_current_skill += 1
        updated_interview.clarification_attempts += 1

    else:
        updated_interview.questions_for_current_skill += 1
        updated_interview.clarification_attempts = 0

    updated_interview.current_topic = next_question.topic
    updated_interview.current_difficulty = next_question.difficulty

    if next_question.topic not in updated_interview.covered_topics:
        updated_interview.covered_topics.append(next_question.topic)

    updated_interview.current_question_number += 1
    updated_interview.interview_history.append(
        _create_interview_turn(
            question_number=updated_interview.current_question_number,
            generated_question=next_question,
        )
    )

    return updated_interview


def _route_operation(state: InterviewGraphState) -> WorkflowOperation:
    operation = state.get("operation")

    if operation not in {"start", "answer", "finish"}:
        raise ValueError(f"Unsupported workflow operation: {operation}")

    return operation


def _route_after_decision(
    state: InterviewGraphState,
) -> Literal["finish", "continue"]:
    decision = state.get("decision")

    if decision is None:
        raise ValueError("The workflow decision is missing.")

    if decision.action == "finish":
        return "finish"

    return "continue"


class InterviewWorkflow:
    """LangGraph orchestration for the Phase 3 adaptive interview."""

    def __init__(
        self,
        *,
        analyze_answer: AnswerAnalyzer,
        generate_initial_question: InitialQuestionGenerator,
        generate_adaptive_question: AdaptiveQuestionGenerator,
        decide_next_step: DecisionMaker,
        checkpointer=None,
    ) -> None:
        self._analyze_answer = analyze_answer
        self._generate_initial_question = generate_initial_question
        self._generate_adaptive_question = generate_adaptive_question
        self._decide_next_step = decide_next_step

        graph_builder = StateGraph(InterviewGraphState)
        graph_builder.add_node(
            "initialize_interview",
            self._initialize_interview,
        )
        graph_builder.add_node(
            "analyze_answer",
            self._analyze_candidate_answer,
        )
        graph_builder.add_node(
            "decide_next_step",
            self._decide_interview_step,
        )
        graph_builder.add_node(
            "generate_question",
            self._generate_next_question,
        )
        graph_builder.add_node(
            "update_interview",
            self._update_interview,
        )
        graph_builder.add_node(
            "complete_after_answer",
            self._complete_after_answer,
        )
        graph_builder.add_node(
            "finish_interview",
            self._finish_interview,
        )

        graph_builder.add_conditional_edges(
            START,
            _route_operation,
            {
                "start": "initialize_interview",
                "answer": "analyze_answer",
                "finish": "finish_interview",
            },
        )
        graph_builder.add_edge("initialize_interview", END)
        graph_builder.add_edge("analyze_answer", "decide_next_step")
        graph_builder.add_conditional_edges(
            "decide_next_step",
            _route_after_decision,
            {
                "finish": "complete_after_answer",
                "continue": "generate_question",
            },
        )
        graph_builder.add_edge("generate_question", "update_interview")
        graph_builder.add_edge("update_interview", END)
        graph_builder.add_edge("complete_after_answer", END)
        graph_builder.add_edge("finish_interview", END)

        workflow_checkpointer = (
            checkpointer
            if checkpointer is not None
            else InMemorySaver()
        )
        self._graph = graph_builder.compile(
            checkpointer=workflow_checkpointer
        )

    def start(
        self,
        *,
        candidate_name: str,
        skills: list[str],
        maximum_questions: int = 8,
        maximum_questions_per_skill: int = 3,
    ) -> InterviewStartResult:
        interview_id = str(uuid4())
        result = self._invoke_graph(
            {
                "operation": "start",
                "interview_id": interview_id,
                "candidate_name": candidate_name,
                "skills": skills,
                "maximum_questions": maximum_questions,
                "maximum_questions_per_skill": (
                    maximum_questions_per_skill
                ),
            },
            interview_id=interview_id,
            operation="start",
        )

        start_result = result.get("start_result")

        if not isinstance(start_result, InterviewStartResult):
            raise RuntimeError(
                "The interview workflow did not return a start result."
            )

        return start_result

    def process_answer(
        self,
        *,
        interview_id: str,
        candidate_answer: str,
    ) -> AnswerProcessingResult:
        interview_id = self._validate_interview_id(interview_id)
        candidate_answer = candidate_answer.strip()

        if not candidate_answer:
            raise ValueError("Candidate answer cannot be empty.")

        snapshot = self._get_snapshot(interview_id)
        interview = self._get_interview(snapshot.values, interview_id)

        if interview.interview_finished:
            raise ValueError("This interview has already finished.")

        if snapshot.next:
            pending_answer = snapshot.values.get("candidate_answer")

            if pending_answer != candidate_answer:
                raise ValueError(
                    "The previous answer is still being processed. "
                    "Retry that same answer before submitting another one."
                )

            result = self._invoke_graph(
                None,
                interview_id=interview_id,
                operation="answer",
            )
        else:
            result = self._invoke_graph(
                {
                    "operation": "answer",
                    "candidate_answer": candidate_answer,
                },
                interview_id=interview_id,
                operation="answer",
            )

        answer_result = result.get("answer_result")

        if not isinstance(answer_result, AnswerProcessingResult):
            raise RuntimeError(
                "The interview workflow did not return an answer result."
            )

        return answer_result

    def get_interview_state(
        self,
        interview_id: str,
    ) -> AdaptiveInterviewState:
        interview_id = self._validate_interview_id(interview_id)
        snapshot = self._get_snapshot(interview_id)
        interview = self._get_interview(snapshot.values, interview_id)
        return interview.model_copy(deep=True)

    def finish(
        self,
        interview_id: str,
    ) -> AdaptiveInterviewState:
        interview_id = self._validate_interview_id(interview_id)
        snapshot = self._get_snapshot(interview_id)
        interview = self._get_interview(snapshot.values, interview_id)

        if interview.interview_finished:
            return interview.model_copy(deep=True)

        if snapshot.next:
            finished_interview = _finish_interview_state(interview)
            self._graph.update_state(
                self._config(interview_id),
                {
                    "operation": "finish",
                    "interview": finished_interview,
                },
                as_node="finish_interview",
            )
            return finished_interview

        result = self._invoke_graph(
            {"operation": "finish"},
            interview_id=interview_id,
            operation="finish",
        )
        finished_interview = result.get("interview")

        if not isinstance(
            finished_interview,
            AdaptiveInterviewState,
        ):
            raise RuntimeError(
                "The interview workflow did not return its final state."
            )

        return finished_interview.model_copy(deep=True)

    def _initialize_interview(
        self,
        state: InterviewGraphState,
    ) -> InterviewGraphState:
        candidate_name = state.get("candidate_name", "").strip()

        if not candidate_name:
            raise ValueError("Candidate name cannot be empty.")

        maximum_questions = state.get("maximum_questions", 8)
        maximum_questions_per_skill = state.get(
            "maximum_questions_per_skill",
            3,
        )

        if maximum_questions < 1:
            raise ValueError("Maximum questions must be at least 1.")

        if maximum_questions_per_skill < 1:
            raise ValueError(
                "Maximum questions per skill must be at least 1."
            )

        cleaned_skills = _clean_skills(state.get("skills", []))
        interview_id = state["interview_id"]

        with logfire.span(
            "interview node: initialize",
            interview_id=interview_id,
            skill_count=len(cleaned_skills),
        ) as node_span:
            initial_question = self._generate_initial_question(
                candidate_name=candidate_name,
                skills_list=cleaned_skills,
            )
            node_span.set_attribute(
                "question_difficulty",
                initial_question.difficulty,
            )
        interview = AdaptiveInterviewState(
            interview_id=interview_id,
            candidate_name=candidate_name,
            selected_skills=cleaned_skills,
            current_skill=initial_question.skill,
            current_topic=initial_question.topic,
            current_difficulty=initial_question.difficulty,
            current_question_number=1,
            maximum_questions=maximum_questions,
            questions_for_current_skill=1,
            maximum_questions_per_skill=maximum_questions_per_skill,
            clarification_attempts=0,
            maximum_clarification_attempts=1,
            covered_topics=[initial_question.topic],
            interview_history=[
                _create_interview_turn(1, initial_question)
            ],
            interview_finished=False,
        )

        return {
            "candidate_name": candidate_name,
            "skills": cleaned_skills,
            "interview": interview,
            "start_result": InterviewStartResult(
                interview_id=interview_id,
                question_number=1,
                question=initial_question,
                interview_finished=False,
            ),
        }

    def _analyze_candidate_answer(
        self,
        state: InterviewGraphState,
    ) -> InterviewGraphState:
        interview = self._require_interview(state)

        if interview.interview_finished:
            raise ValueError("This interview has already finished.")

        candidate_answer = state.get("candidate_answer", "").strip()

        if not candidate_answer:
            raise ValueError("Candidate answer cannot be empty.")

        updated_interview = interview.model_copy(deep=True)
        current_turn = _get_current_turn(updated_interview)
        with logfire.span(
            "interview node: analyze answer",
            interview_id=interview.interview_id,
            question_number=interview.current_question_number,
            answer_length=len(candidate_answer),
        ) as node_span:
            analysis = self._analyze_answer(
                question=current_turn.question,
                candidate_answer=candidate_answer,
                skill=current_turn.skill,
                topic=current_turn.topic,
                difficulty=current_turn.difficulty,
            )
            node_span.set_attribute(
                "correctness_score",
                analysis.correctness_score,
            )
            node_span.set_attribute(
                "completeness_score",
                analysis.completeness_score,
            )
        current_turn.answer = candidate_answer
        current_turn.analysis = analysis

        return {
            "candidate_answer": candidate_answer,
            "interview": updated_interview,
            "analysis": analysis,
        }

    def _decide_interview_step(
        self,
        state: InterviewGraphState,
    ) -> InterviewGraphState:
        interview = self._require_interview(state)
        analysis = self._require_analysis(state)
        with logfire.span(
            "interview node: decide next step",
            interview_id=interview.interview_id,
            question_number=interview.current_question_number,
        ) as node_span:
            decision = self._decide_next_step(
                analysis=analysis,
                state=interview,
            )
            node_span.set_attribute(
                "decision_action",
                decision.action,
            )
            node_span.set_attribute(
                "next_difficulty",
                decision.next_difficulty,
            )
        return {"decision": decision}

    def _generate_next_question(
        self,
        state: InterviewGraphState,
    ) -> InterviewGraphState:
        interview = self._require_interview(state)
        analysis = self._require_analysis(state)
        decision = self._require_decision(state)
        with logfire.span(
            "interview node: generate question",
            interview_id=interview.interview_id,
            next_question_number=(
                interview.current_question_number + 1
            ),
            decision_action=decision.action,
        ) as node_span:
            next_question = self._generate_adaptive_question(
                state=interview,
                analysis=analysis,
                decision=decision,
            )
            node_span.set_attribute(
                "question_difficulty",
                next_question.difficulty,
            )
            node_span.set_attribute(
                "question_type",
                next_question.question_type,
            )
        return {"next_question": next_question}

    def _update_interview(
        self,
        state: InterviewGraphState,
    ) -> InterviewGraphState:
        interview = self._require_interview(state)
        analysis = self._require_analysis(state)
        decision = self._require_decision(state)
        next_question = state.get("next_question")

        if not isinstance(next_question, AdaptiveQuestion):
            raise ValueError("The next interview question is missing.")

        updated_interview = _advance_interview(
            interview=interview,
            decision=decision,
            next_question=next_question,
        )

        return {
            "interview": updated_interview,
            "answer_result": AnswerProcessingResult(
                interview_id=updated_interview.interview_id,
                analysis=analysis,
                decision=decision,
                next_question_number=(
                    updated_interview.current_question_number
                ),
                next_question=next_question,
                interview_finished=False,
            ),
        }

    def _complete_after_answer(
        self,
        state: InterviewGraphState,
    ) -> InterviewGraphState:
        interview = _finish_interview_state(
            self._require_interview(state)
        )
        analysis = self._require_analysis(state)
        decision = self._require_decision(state)

        return {
            "interview": interview,
            "answer_result": AnswerProcessingResult(
                interview_id=interview.interview_id,
                analysis=analysis,
                decision=decision,
                next_question_number=None,
                next_question=None,
                interview_finished=True,
            ),
        }

    def _finish_interview(
        self,
        state: InterviewGraphState,
    ) -> InterviewGraphState:
        interview = self._require_interview(state)
        return {
            "interview": _finish_interview_state(interview),
        }

    def _invoke_graph(
        self,
        input_state: InterviewGraphState | None,
        *,
        interview_id: str,
        operation: WorkflowOperation,
    ) -> InterviewGraphState:
        with logfire.span(
            "interview workflow: {operation}",
            operation=operation,
            interview_id=interview_id,
        ):
            return self._graph.invoke(
                input_state,
                self._config(interview_id),
            )

    def _get_snapshot(self, interview_id: str):
        snapshot = self._graph.get_state(self._config(interview_id))

        if not snapshot.values:
            raise ValueError(
                f"Interview session '{interview_id}' was not found."
            )

        return snapshot

    @staticmethod
    def _get_interview(
        values: InterviewGraphState,
        interview_id: str,
    ) -> AdaptiveInterviewState:
        interview = values.get("interview")

        if not isinstance(interview, AdaptiveInterviewState):
            raise ValueError(
                f"Interview session '{interview_id}' was not found."
            )

        return interview

    @staticmethod
    def _require_interview(
        state: InterviewGraphState,
    ) -> AdaptiveInterviewState:
        interview = state.get("interview")

        if not isinstance(interview, AdaptiveInterviewState):
            raise ValueError("The interview state is missing.")

        return interview

    @staticmethod
    def _require_analysis(
        state: InterviewGraphState,
    ) -> AnswerAnalysis:
        analysis = state.get("analysis")

        if not isinstance(analysis, AnswerAnalysis):
            raise ValueError("The answer analysis is missing.")

        return analysis

    @staticmethod
    def _require_decision(
        state: InterviewGraphState,
    ) -> InterviewDecision:
        decision = state.get("decision")

        if not isinstance(decision, InterviewDecision):
            raise ValueError("The interview decision is missing.")

        return decision

    @staticmethod
    def _validate_interview_id(interview_id: str) -> str:
        interview_id = interview_id.strip()

        if not interview_id:
            raise ValueError("Interview ID cannot be empty.")

        return interview_id

    @staticmethod
    def _config(interview_id: str) -> dict[str, dict[str, str]]:
        return {
            "configurable": {
                "thread_id": interview_id,
            }
        }
