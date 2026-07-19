from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from schemas.schemaV3 import AdaptiveInterviewState,AdaptiveQuestion,AnswerAnalysis,InterviewDecision

load_dotenv()

#Create the gemini model
def _create_question_generator():

    model = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        temperature=0.3
    )

    return model.with_structured_output(AdaptiveQuestion)

#Maps InterviewDescion.action to AdaptiveQuestion.questiontype
def _map_action_to_question_type(action: str) -> str:

    action_mapping = {
        "clarify": "clarification",
        "follow_up": "follow_up",
        "deepen_topic": "deeper",
        "change_topic": "new_topic",
        "change_skill": "new_skill",
    }


    question_type = action_mapping.get(action)

    if question_type is None:
        raise ValueError(
            f"Cannot generate a question for action: {action}"
        )
    
    return question_type

#gets all the asked question
def _get_asked_questions(state: AdaptiveInterviewState) -> list[str]:
 
    return [
        turn.question
        for turn in state.interview_history
    ]

#Builds the prompt
def _create_question_prompt() -> ChatPromptTemplate:

    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are an experienced technical interviewer.

Generate exactly one adaptive technical interview question.

The interview controller has already decided the next action.
You must follow that decision and must not override it.

General rules:

1. Return exactly one question.
2. Do not combine multiple questions using words such as:
   "and also", "additionally", or "as well as".
3. Do not repeat any previously asked question.
4. Do not provide the answer.
5. Do not provide hints unless the action is clarification.
6. Keep the wording clear and concise.
7. Test only the requested skill and topic.
8. Match the requested difficulty.
9. The question must be answerable verbally.
10. Avoid yes-or-no questions.
11. Avoid unnecessarily long scenarios.
12. Do not mention scores, evaluation, or interview decisions.

Action-specific rules:

CLARIFY:
- Ask a simpler question about the misconception or missing concept.
- Use more direct wording than the previous question.
- Do not reveal the complete answer.
- Stay on the same topic.

FOLLOW_UP:
- Ask about an important concept missing from the previous answer.
- Stay close to the previous question.
- Do not simply repeat the previous question in different words.

DEEPEN_TOPIC:
- Test deeper reasoning, implementation, trade-offs,
  performance, limitations, or real-world use.
- Stay within the current topic.
- Increase complexity according to the requested difficulty.

CHANGE_TOPIC:
- Ask about a different topic within the same skill.
- Avoid topics already present in the covered-topics list.
- The question should not depend on the previous answer.

CHANGE_SKILL:
- Ask an introductory or medium-level question about the next skill.
- The question should not depend on the previous skill.
- Use the skill specified by the controller.
"""
            ),
            (
                "human",
                """
Generate the next adaptive interview question.

Controller action:
{action}

Required question type:
{question_type}

Target skill:
{target_skill}

Current topic:
{current_topic}

Target topic:
{target_topic}

Target difficulty:
{target_difficulty}

Question focus:
{question_focus}

Previous question:
{previous_question}

Candidate answer:
{candidate_answer}

Answer strengths:
{strengths}

Missing concepts:
{missing_concepts}

Misconceptions:
{misconceptions}

Covered topics:
{covered_topics}

Previously asked questions:
{asked_questions}

Controller reason:
{decision_reason}
"""
            ),
        ]
    )


#fetch the last answer
def _get_latest_answered_turn(state: AdaptiveInterviewState):

    for turn in reversed(state.interview_history):
        if turn.answer:
            return turn
    
    raise ValueError(
        "No answered interview turn was found."
    )

#Converts list into text
def _format_list(values: list[str]) -> str:

    if not values:
        return "None"
    
    return "\n".join(
        f"- {value}"
        for value in values
    )

#decides which skill should be used for the next generated question.
def _resolve_target_skill(state: AdaptiveInterviewState,decision: InterviewDecision) -> str:

    if decision.action == "change_skill":
        if not decision.next_skill:
            raise ValueError(
                "next_skill is required when changing skill."
            )
        return decision.next_skill
    
    return state.current_skill


#decides what topic instruction should be used for the next question.
def _resolve_target_topic(state: AdaptiveInterviewState,decision: InterviewDecision,) -> str:


    if decision.next_topic:
        return decision.next_topic

    if decision.action == "change_topic":
        return (
            "Select a new topic within the target skill that "
            "is not present in covered_topics."
        )

    if decision.action == "change_skill":
        return (
            "Select an appropriate introductory topic for "
            "the new skill."
        )

    if state.current_topic:
        return state.current_topic

    return "Select an appropriate topic for the target skill."



def generate_adaptive_question(state: AdaptiveInterviewState,analysis: AnswerAnalysis,
decision: InterviewDecision) -> AdaptiveQuestion:
    
    if decision.action == "finish":
        raise ValueError(
            "A new question cannot be generated because "
            "the interview is finished."
        )
    
    if state.interview_finished:
        raise ValueError(
            "A new question cannot be generated for a "
            "finished interview."
        )
    
    if not state.interview_history:
        raise ValueError(
            "Interview history is empty. Use the initial "
            "question generator to start the interview."
        )
    
    latest_turn = _get_latest_answered_turn(state)

    target_skill = _resolve_target_skill(
        state=state,
        decision=decision,
    )

    target_topic = _resolve_target_topic(
        state=state,
        decision=decision,
    )

    question_type = _map_action_to_question_type(
        decision.action
    )

    asked_questions = _get_asked_questions(state)

    try:

        generator = _create_question_generator()
        prompt = _create_question_prompt()

        chain = prompt | generator

        result = chain.invoke(
            {
                "action": decision.action,
                "question_type": question_type,
                "target_skill": target_skill,
                "current_topic": (
                    state.current_topic or "Not set"
                ),
                "target_topic": target_topic,
                "target_difficulty": (
                    decision.next_difficulty
                ),
                "question_focus": (
                    decision.question_focus
                    or analysis.follow_up_focus
                    or "General technical understanding"
                ),
                "previous_question": latest_turn.question,
                "candidate_answer": (
                    latest_turn.answer or "No answer"
                ),
                "strengths": _format_list(
                    analysis.strengths
                ),
                "missing_concepts": _format_list(
                    analysis.missing_concepts
                ),
                "misconceptions": _format_list(
                    analysis.misconceptions
                ),
                "covered_topics": _format_list(
                    state.covered_topics
                ),
                "asked_questions": _format_list(
                    asked_questions
                ),
                "decision_reason": decision.reason,
            }
        )

        if not isinstance(result, AdaptiveQuestion):
            raise TypeError(
                "Gemini did not return a valid "
                "AdaptiveQuestion object."
            )
        
        _validate_generated_question(
            question=result,
            expected_skill=target_skill,
            expected_difficulty=decision.next_difficulty,
            expected_question_type=question_type,
            asked_questions=asked_questions,
        )

        return result
    
    except ValueError:
        raise
    
    except Exception as error:
        raise RuntimeError(
            f"Failed to generate adaptive question: {error}"
        ) from error
    


def _validate_generated_question(
    question: AdaptiveQuestion,
    expected_skill: str,
    expected_difficulty: str,
    expected_question_type: str,
    asked_questions: list[str],
) -> None:
    

    generated_text = question.question.strip()

    if not generated_text.endswith("?"):
        raise ValueError(
            "The generated interview question must "
            "end with a question mark."
        )

    if (
        question.skill.strip().lower()
        != expected_skill.strip().lower()
    ):
        raise ValueError(
            "The generated question does not match "
            f"the expected skill '{expected_skill}'."
        )

    if question.difficulty != expected_difficulty:
        raise ValueError(
            "The generated question does not match "
            f"the expected difficulty '{expected_difficulty}'."
        )

    if question.question_type != expected_question_type:
        raise ValueError(
            "The generated question does not match "
            f"the expected type '{expected_question_type}'."
        )

    normalized_generated_question = (
        _normalize_question(generated_text)
    )

    normalized_previous_questions = {
        _normalize_question(previous_question)
        for previous_question in asked_questions
    }

    if (
        normalized_generated_question
        in normalized_previous_questions
    ):
        raise ValueError(
            "Gemini repeated a previously asked question."
        )
    
def _normalize_question(question: str) -> str:
    

    return " ".join(
        question.lower()
        .replace("?", "")
        .strip()
        .split()
    )