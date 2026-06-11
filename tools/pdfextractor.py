import io
from pypdf import PdfReader
from google import genai
from dotenv import load_dotenv
import os
from schemas.schema import ResumeData

load_dotenv()


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text =""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text        



def extract_resume_details(pdf_bytes:bytes) -> ResumeData:

    resume_text = extract_text_from_pdf(pdf_bytes)

    client = genai.Client()

    prompt = f"""
    You are an expert resume parsing assistant. 
    Analyze the following raw text extracted from a resume PDF and extract all relevant 
    information structural matching the required schema.
    
    Resume Text:
    {resume_text}
    """

    response = client.models.generate_content(
    model='gemini-3.5-flash',
    contents=prompt,
    config=genai.types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=ResumeData,
        temperature=0.1,
    ),
    )
    return response.parsed

