import io
from pypdf import PdfReader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
from backend.app.schemas.resume import ResumeData

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

    model = ChatGoogleGenerativeAI(model='gemini-3.5-flash')

    structured_model = model.with_structured_output(ResumeData)

    template = PromptTemplate(
        template='''
                You are an expert resume parsing assistant.
                Analyze the following raw text extracted from a resume PDF and extract all relevant
                information structural matching the required schema.

                Resume Text:
                {resume_text}
            ''',
            input_variables=['resume_text']
    )

    prompt = template.invoke({'resume_text':resume_text})

    result = structured_model.invoke(prompt)

    return result
