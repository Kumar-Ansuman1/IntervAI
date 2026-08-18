import io

import logfire
from langchain_core.prompts import PromptTemplate
from pypdf import PdfReader

from backend.app.schemas.resume import ResumeData
from backend.app.services.llm.gateway import LLMGateway, get_llm_gateway
from backend.app.services.llm.policies import LLMTask


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


def extract_resume_details(
    pdf_bytes: bytes,
    gateway: LLMGateway | None = None,
) -> ResumeData:
    resume_text = extract_text_from_pdf(pdf_bytes)

    with logfire.span(
        "resume: prepare prompt",
        extracted_character_count=len(resume_text),
    ):
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
        prompt_text = prompt.to_string()

    with logfire.span(
        "resume: request structured parsing",
        input_character_count=len(resume_text),
    ) as span:
        gateway = gateway or get_llm_gateway()
        result = gateway.generate_structured(
            task=LLMTask.RESUME_PARSING,
            prompt=prompt_text,
            response_model=ResumeData,
        )
        span.set_attribute("response_type", type(result).__name__)

    return result
