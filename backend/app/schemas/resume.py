from pydantic import BaseModel


class Project(BaseModel):
    title: str
    tech_stack: list[str]
    description: str


class Experience(BaseModel):
    company: str
    role: str
    duration: str
    highlights: list[str]


class ResumeData(BaseModel):
    name: str
    skills: list[str]
    tech_stack: list[str]
    projects: list[Project]
    experience: list[Experience]
