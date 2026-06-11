from pdfextractor import skills
from pydantic import BaseModel
from typing import List
from google import genai
from dotenv import load_dotenv

load_dotenv()

class InterviewQuestion(BaseModel):
    id: int
    skill_tested: str
    question: str
    ideal_answer_keywords: List[str]

class InterviewPrep(BaseModel):
    candidate_name: str
    questions_list: List[InterviewQuestion]


def generate_interview_questions(candidate_name: str, skills_list: List[str]) -> InterviewPrep:
    """
    Takes a candidate's extracted skills list and generates 5 highly targeted,
    technical interview questions matching a structured Pydantic schema.
    """
    client = genai.Client()
    
    skills_formatted = ", ".join(skills_list)
    
    prompt = f"""
    You are an expert technical interviewer. 
    Review the following candidate technical skills list and generate exactly 5 high-quality, 
    real-world, open-ended technical interview questions to assess their practical knowledge.
    
    Candidate Name: {candidate_name}
    Extracted Skills: {skills_formatted}
    
    Focus on creating deep, situational, or conceptual engineering questions for their primary tech skills.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash-lite',
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InterviewPrep,  
            temperature=0.7,               
        ),
    )
    
    return response.parsed

questions = generate_interview_questions("Kumar Ansuman", skills)

print(questions)