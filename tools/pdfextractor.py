from pypdf import PdfReader
from pydantic import BaseModel
from typing import List
from google import genai
from dotenv import load_dotenv
import os

load_dotenv()

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

def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text =""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text        



def extract_resume_details(pdf_path:str) -> ResumeData:

    resume_text = extract_text_from_pdf(pdf_path)

    client = genai.Client()

    prompt = f"""
    You are an expert resume parsing assistant. 
    Analyze the following raw text extracted from a resume PDF and extract all relevant 
    information structural matching the required schema.
    
    Resume Text:
    {resume_text}
    """

    response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents=prompt,
    config=genai.types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ResumeData,
        temperature=0.1,
    ),
    )
    return response.parsed

parsed_resume = extract_resume_details("C:\Code\IntervAI\Resume\Kumar_Ansuman (1).pdf")

skills = parsed_resume.skills