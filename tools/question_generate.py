from schemas.schema import InterviewPrepResponse
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()




def generate_interview_questions(candidate_name: str, skills_list: List[str]) -> InterviewPrepResponse:
    
    
    skills_formatted = ", ".join(skills_list)
    
    prompt = f"""
    You are an expert technical interviewer. 
    Review the following candidate technical skills list and generate exactly 5 high-quality, 
    real-world, open-ended technical interview questions to assess their practical knowledge.
    
    Candidate Name: {candidate_name}
    Extracted Skills: {skills_formatted}
    
    Focus on creating deep, situational, or conceptual engineering questions for their primary tech skills.
    """
    
    model = ChatGoogleGenerativeAI(model='gemini-3.5-flash')

    structured_model = model.with_structured_output(InterviewPrepResponse)

    response = structured_model.invoke(prompt)

    return response

