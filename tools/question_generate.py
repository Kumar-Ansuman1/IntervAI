from schemas.schema import InterviewPrepResponse
from typing import List
from google import genai
from dotenv import load_dotenv

load_dotenv()




def generate_interview_questions(candidate_name: str, skills_list: List[str]) -> InterviewPrepResponse:
    
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
        model='gemini-2.5-flash',
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InterviewPrepResponse,  
            temperature=0.7,               
        ),
    )
    
    return response.parsed

