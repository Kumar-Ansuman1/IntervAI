from google import genai
from google.genai import types
from dotenv import load_dotenv
from schemas.schema import EvaluationRequest, InterviewScorecard

load_dotenv()

def evaluate_interview_answers(payload: EvaluationRequest) -> InterviewScorecard:

    client = genai.Client()

    formatted_submissions = ""
    for sub in payload.submissions:
        formatted_submissions += f"""
        ---
        Question ID: {sub.question_id}
        Question Asked: {sub.question_text}
        Candidate Answer: {sub.user_answer}
        """
    
    prompt = f"""
    You are an expert technical interviewer and senior engineering manager.
    Analyze the following candidate's technical interview answers and generate a comprehensive,
    highly constructive grading scorecard matching the required schema.

    Candidate Name: {payload.candidate_name}
    
    Submissions Data:
    {formatted_submissions}

    Grading Rubric Criteria:
    - Assess technical accuracy, depth, and communication clarity.
    - Provide specific engineering feedback detailing what was outstanding and what core concepts were left out.
    - Calculate the precise mathematical average technical rating out of 10.
    """

    response = client.models.generate_content(
        model='gemini-3.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InterviewScorecard,
            temperature=0.2, 
        ),
    )

    return response.parsed

