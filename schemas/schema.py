from pydantic import BaseModel
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