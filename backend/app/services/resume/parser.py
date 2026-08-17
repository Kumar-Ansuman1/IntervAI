import io

import logfire
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pypdf import PdfReader

from backend.app.schemas.resume import ResumeData

load_dotenv()

RESUME_MODEL = "gemini-3.5-flash"


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    with logfire.span(
        "resume: extract PDF text",
        pdf_size_bytes=len(pdf_bytes),
    ) as span:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        span.set_attribute("page_count", len(reader.pages))
        span.set_attribute("extracted_character_count", len(text))

        return text


def extract_resume_details(pdf_bytes: bytes) -> ResumeData:
    resume_text = extract_text_from_pdf(pdf_bytes)

    with logfire.span(
        "resume: prepare model and prompt",
        extracted_character_count=len(resume_text),
    ):
        model = ChatGoogleGenerativeAI(model=RESUME_MODEL)
        structured_model = model.with_structured_output(ResumeData)

        template = PromptTemplate(
            template="""
                You are an expert resume parsing assistant.
                Analyze the following raw text extracted from a resume PDF and extract all relevant
                information structural matching the required schema.

                Resume Text:
                {resume_text}
            """,
            input_variables=["resume_text"],
        )

        prompt = template.invoke({"resume_text": resume_text})

    with logfire.span(
        "resume: invoke structured model",
        model_name=RESUME_MODEL,
        input_character_count=len(resume_text),
    ) as span:
        result = structured_model.invoke(prompt)
        span.set_attribute("response_type", type(result).__name__)

    return result
