from typing import Literal
from pydantic import BaseModel, Field



class AnswerAnalysis(BaseModel):
    correctness_score: int = Field(ge=0, le=10)
    completeness_score: int = Field(ge=0, le=10)
    clarity_score: int = Field(ge=0, le=10)
    practical_understanding_score: int = Field(ge=0, le=10)

    strengths: list[str] = Field(default_factory=list)
    missing_concepts: list[str] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)

    feedback: str

    recommended_action: Literal[
        "clarify",
        "follow_up",
        "deepen_topic",
        "change_topic",
        "change_skill",
        "finish"
    ]

    recommended_difficulty: Literal[
        "easier",
        "same",
        "harder"
    ]

    follow_up_focus: str | None = None

class InterviewTurn(BaseModel):
    question_number: int
    question: str
    answer: str | None = None

    skill: str
    topic: str

    difficulty: Literal[
        "easy",
        "medium",
        "hard",
    ]

    question_type: Literal[
        "initial",
        "clarification",
        "follow_up",
        "deeper",
        "new_topic",
        "new_skill",
    ]

    analysis: AnswerAnalysis | None = None

class AdaptiveInterviewState(BaseModel):
    interview_id: str
    candidate_name: str

    selected_skills: list[str]
    completed_skills: list[str] = Field(default_factory=list)

    current_skill: str
    current_topic: str | None = None
    current_difficulty: Literal["easy", "medium", "hard"] = "medium"

    current_question_number: int = 1
    maximum_questions: int = 8

    questions_for_current_skill: int = 0
    maximum_questions_per_skill: int = 3

    clarification_attempts: int = 0
    maximum_clarification_attempts: int = 1

    covered_topics: list[str] = Field(default_factory=list)
    interview_history: list[InterviewTurn] = Field(default_factory=list)

    interview_finished: bool = False

class InterviewDecision(BaseModel):
    action: Literal[
        "clarify",
        "follow_up",
        "deepen_topic",
        "change_topic",
        "change_skill",
        "finish"
    ]

    next_difficulty: Literal["easy", "medium", "hard"]

    next_skill: str | None = None
    next_topic: str | None = None
    question_focus: str | None = None

    reason: str

class AdaptiveQuestion(BaseModel):
    question: str = Field(
        min_length=5,
        description=(
            "Exactly one clear technical interview question. "
            "It must not contain multiple separate questions."
        ),
    )

    skill: str = Field(
        min_length=1,
        description="The main technical skill tested by the question.",
    )

    topic: str = Field(
        min_length=1,
        description="The specific technical topic tested by the question.",
    )

    difficulty: Literal[
        "easy",
        "medium",
        "hard",
    ]

    question_type: Literal[
        "initial",
        "clarification",
        "follow_up",
        "deeper",
        "new_topic",
        "new_skill",
    ]

    focus: str = Field(
        min_length=1,
        description=(
            "The particular concept or ability the question evaluates."
        ),
    )
    
class InterviewStartResult(BaseModel):
    interview_id: str
    question_number: int
    question: AdaptiveQuestion
    interview_finished: bool = False

class AnswerProcessingResult(BaseModel):
    interview_id: str
    analysis: AnswerAnalysis
    decision: InterviewDecision
    next_question_number: int | None = None
    next_question: AdaptiveQuestion | None = None
    interview_finished: bool

class AdaptiveInterviewStartRequest(BaseModel):
    candidate_name: str = Field(
        min_length=1,
        description="Name of the candidate."
    )

    skills: list[str] = Field(
        min_length=1,
        description="Technical skills extracted from the resume."
    )

    maximum_questions: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Maximum total questions in the interview."
    )

    maximum_questions_per_skill: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum questions allowed for one skill."
    )

class AdaptiveAnswerRequest(BaseModel):
    interview_id: str = Field(
        min_length=1,
        description="Unique ID of the adaptive interview session."
    )

    candidate_answer: str = Field(
        min_length=1,
        description="Candidate's typed or transcribed answer."
    )

class FinishAdaptiveInterviewRequest(BaseModel):
    interview_id: str = Field(
        min_length=1,
        description="Interview session that should be finished."
    )