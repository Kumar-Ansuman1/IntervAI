import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

from schemas.schemaV3 import AnswerAnalysis

load_dotenv()

def _create_answer_analyzer():

    model = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite",temperature=0)

    return model.with_structured_output(AnswerAnalysis)


def _create_analysis_prompt() -> ChatPromptTemplate:

    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are a strict but fair technical interviewer.

Your task is to evaluate a candidate's answer to one technical
interview question.

Evaluate the answer only according to the supplied question, skill,
topic, and difficulty.

Scoring guidelines:

Correctness score:
- 0-2: Mostly incorrect or unrelated.
- 3-4: Shows limited understanding with major errors.
- 5-6: Partially correct but important details are missing.
- 7-8: Correct with minor omissions.
- 9-10: Fully correct and technically precise.

Completeness score:
- 0-2: Does not address the important parts of the question.
- 3-4: Addresses only a small part.
- 5-6: Covers the main idea but lacks important details.
- 7-8: Covers most expected concepts.
- 9-10: Thoroughly addresses all important concepts.

Clarity score:
- 0-2: Very confusing or impossible to understand.
- 3-4: Poorly explained.
- 5-6: Understandable but not well organized.
- 7-8: Clear and reasonably structured.
- 9-10: Very clear, precise, and logically structured.

Practical understanding score:
- 0-2: No practical understanding is demonstrated.
- 3-4: Very limited practical understanding.
- 5-6: Some practical understanding is demonstrated.
- 7-8: Good practical understanding or relevant examples.
- 9-10: Excellent real-world understanding and application.

Recommended action rules:

- Use "clarify" when the answer is unclear, incorrect, or contains
  an important misconception.
- Use "follow_up" when the answer is partially correct and the
  missing concept should be examined.
- Use "deepen_topic" when the answer is strong and the candidate
  can be tested at greater depth.
- Use "change_topic" when the answer is sufficiently complete and
  no useful follow-up is necessary.

Recommended difficulty rules:

- Use "easier" when the candidate shows weak understanding.
- Use "same" when the answer is average or partially correct.
- Use "harder" when the answer demonstrates strong understanding.

Important instructions:

- Do not reward an answer merely because it is long.
- Do not punish an answer merely because it is concise.
- Identify only genuine technical misconceptions.
- Do not invent mistakes that are not present.
- Keep feedback constructive and concise.
- The follow_up_focus should be specific.
- Set follow_up_focus to null only when changing the topic.
"""
            ),
            (
                "human",
                """
Evaluate the following technical interview response.

Skill:
{skill}

Topic:
{topic}

Question difficulty:
{difficulty}

Interview question:
{question}

Candidate answer:
{candidate_answer}
"""
            )
        ]
    )


def analyze_answer(question: str, candidate_answer: str, skill: str, topic: str, difficulty: str) -> AnswerAnalysis:
    
    question = question.strip()
    candidate_answer = candidate_answer.strip()
    skill = skill.strip()
    topic = topic.strip()
    difficulty = difficulty.strip().lower()

    if not question:
        raise ValueError("Question cannot be empty.")

    if not candidate_answer:
        raise ValueError("Candidate answer cannot be empty.")

    if not skill:
        raise ValueError("Skill cannot be empty.")

    if not topic:
        raise ValueError("Topic cannot be empty.")
    

    allowed_difficulties = {"easy", "medium", "hard"}

    if difficulty not in allowed_difficulties:
        raise ValueError(
            "Difficulty must be 'easy', 'medium', or 'hard'."
        )
    
    try:

        analyzer = _create_answer_analyzer()
        prompt = _create_analysis_prompt()

        chain = prompt | analyzer

        result = chain.invoke(
            {
                "question": question,
                "candidate_answer": candidate_answer,
                "skill": skill,
                "topic": topic,
                "difficulty": difficulty
            }
        )

        if not isinstance(result, AnswerAnalysis):
            raise TypeError(
                "Gemini did not return a valid AnswerAnalysis object."
            )
        
        return result

    except Exception as error:
        raise RuntimeError(
            f"Failed to analyze candidate answer: {error}"
        ) from error

def calculate_overall_score(analysis: AnswerAnalysis) -> float:
    """
    Calculate the candidate's average score for one answer.
    """

    total_score = (
        analysis.correctness_score
        + analysis.completeness_score
        + analysis.clarity_score
        + analysis.practical_understanding_score
    )

    return round(total_score / 4, 2)
