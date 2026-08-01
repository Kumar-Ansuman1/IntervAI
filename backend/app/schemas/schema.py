from pydantic import BaseModel,Field
from typing import List

class Project(BaseModel):
    title: str
    tech_stack: List[str]
    description: str

class Experience(BaseModel):
    company: str
    role: str
    duration: str
    highlights: List[str]

class ResumeData(BaseModel):
    name: str
    skills: List[str]
    tech_stack: List[str]
    projects: List[Project]
    experience: List[Experience]

class InterviewQuestion(BaseModel):
    id: int
    skill_tested: str
    question: str
    ideal_answer_keywords: List[str]

class InterviewPrepRequest(BaseModel):
    candidate_name: str
    skills: List[str]

class InterviewPrepResponse(BaseModel):
    candidate_name: str
    questions_list: List[InterviewQuestion]

class AnswerSubmission(BaseModel):
    question_id: int
    question_text: str
    user_answer: str

class EvaluationRequest(BaseModel):
    candidate_name: str
    submissions: List[AnswerSubmission]

class QuestionGrade(BaseModel):
    question_id: int
    score: int = Field(description="A score from 0 to 10 evaluating the answer completeness.")
    feedback: str = Field(description="Constructive critique detailing what was good and what was missing.")
    missing_keywords: List[str] = Field(description="List of ideal keywords/concepts from the blueprint that the candidate omitted.")

class InterviewScorecard(BaseModel):
    candidate_name: str
    overall_technical_rating: float = Field(description="The average technical rating across all answers out of 10.")
    summary_verdict: str = Field(description="A high-level engineering summary of the candidate's strengths and core areas of improvement.")
    detailed_grades: List[QuestionGrade]

class TextToSpeechRequest(BaseModel):
    text: str
    filename: str = "question.wav"

class TextToSpeechResponse(BaseModel):
    audio_path: str

class SpeechToTextResponse(BaseModel):
    transcript: str