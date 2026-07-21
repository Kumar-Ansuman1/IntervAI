import requests
import streamlit as st
import hashlib
import io
from streamlit_mic_recorder import mic_recorder

st.set_page_config(
    page_title="IntervAI Phase 3",
    layout="centered",
)

st.title("IntervAI — Adaptive Interview")
st.caption(
    "An AI-powered technical interview that adapts "
    "to each candidate response."
)

BASE_URL = "http://127.0.0.1:8000"

UPLOAD_RESUME_URL = f"{BASE_URL}/upload-resume"

ADAPTIVE_START_URL = (
    f"{BASE_URL}/adaptive-interview/start"
)

ADAPTIVE_ANSWER_URL = (
    f"{BASE_URL}/adaptive-interview/answer"
)

ADAPTIVE_FINISH_URL = (
    f"{BASE_URL}/adaptive-interview/finish"
)

ADAPTIVE_STATE_URL = (
    f"{BASE_URL}/adaptive-interview"
)
TTS_URL = f"{BASE_URL}/text-to-speech"
SPEECH_TO_TEXT_URL = f"{BASE_URL}/speech-to-text"


def initialize_session_state() -> None:
    """
    Initialize all Streamlit session values required
    by the Phase 3 adaptive interview frontend.
    """

    default_values = {
        "candidate_name": "",
        "extracted_skills": None,
        "selected_skills": [],
        "resume_processed": False,

        "interview_started": False,
        "interview_id": None,
        "current_question": None,
        "current_question_number": 0,
        "interview_finished": False,

        "current_answer": "",
        "interview_history": [],

        "latest_analysis": None,
        "latest_decision": None,

        "maximum_questions": 8,
        "maximum_questions_per_skill": 3,

        "question_audio": None,
        "question_audio_number": None,
        "audio_hashes": {},
        "transcription_in_progress": False,
    }

    for key, default_value in default_values.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

initialize_session_state()

def get_backend_error(
    response: requests.Response,
) -> str:
    """
    Extract a readable error message from a FastAPI response.
    """

    try:
        response_data = response.json()

        if isinstance(response_data, dict):
            return str(
                response_data.get(
                    "detail",
                    response_data,
                )
            )

        return str(response_data)

    except ValueError:
        return response.text or "Unknown backend error."


def calculate_answer_score(
    analysis: dict,
) -> float:
    """
    Calculate the average score for one answer from
    the four evaluation dimensions.
    """

    scores = [
        analysis.get("correctness_score", 0),
        analysis.get("completeness_score", 0),
        analysis.get("clarity_score", 0),
        analysis.get(
            "practical_understanding_score",
            0,
        ),
    ]

    return round(sum(scores) / len(scores), 2)


def reset_interview_state() -> None:
    """
    Reset only adaptive-interview data.

    Candidate profile and extracted skills are preserved.
    """

    keys_to_reset = {
        "interview_started": False,
        "interview_id": None,
        "current_question": None,
        "current_question_number": 0,
        "interview_finished": False,
        "current_answer": "",
        "interview_history": [],
        "latest_analysis": None,
        "latest_decision": None,
        "question_audio": None,
        "question_audio_number": None,
        "audio_hashes": {},
        "transcription_in_progress": False,
    }

    for key, value in keys_to_reset.items():
        st.session_state[key] = value

def generate_question_audio(
    question_text: str,
    question_number: int,
) -> None:
    
    """
    Generate speech audio for the current interview question.

    Audio is generated only once for each question.
    """

    if not question_text.strip():
        st.error("Cannot generate audio for an empty question.")
        return

    already_generated = (
        st.session_state.question_audio is not None
        and st.session_state.question_audio_number
        == question_number
    )

    if already_generated:
        return

    try:
        response = requests.post(
            TTS_URL,
            json={
                "text": question_text,
            },
            timeout=90,
        )

        if response.status_code != 200:
            st.warning(
                "Question audio could not be generated: "
                f"{get_backend_error(response)}"
            )
            return

        data = response.json()

        audio_path = data.get("audio_path")

        if not audio_path:
            st.warning(
                "The Text-to-Speech endpoint did not "
                "return an audio path."
            )
            return

        st.session_state.question_audio = audio_path
        st.session_state.question_audio_number = (
            question_number
        )

    except requests.ConnectionError:
        st.warning(
            "Could not connect to the Text-to-Speech service."
        )

    except requests.Timeout:
        st.warning(
            "Text-to-Speech generation took too long."
        )

    except Exception as error:
        st.warning(
            f"Unable to generate question audio: {error}"
        )


def transcribe_recorded_answer(
    audio_bytes: bytes,
    question_number: int,
    answer_key: str,
    mime_type: str = "audio/wav",
) -> None:
    audio_hash = hashlib.sha256(
        audio_bytes
    ).hexdigest()

    if (
        st.session_state.audio_hashes.get(
            question_number
        )
        == audio_hash
    ):
        return

    extension_mapping = {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/webm": "webm",
        "audio/mp3": "mp3",
        "audio/mpeg": "mp3",
    }

    extension = extension_mapping.get(
        mime_type,
        "wav",
    )

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = (
        f"answer_question_{question_number}."
        f"{extension}"
    )

    files = {
        "audio": (
            audio_file.name,
            audio_file,
            mime_type,
        )
    }

    try:
        response = requests.post(
            SPEECH_TO_TEXT_URL,
            files=files,
            timeout=120,
        )

        if response.status_code != 200:
            st.error(
                "Speech transcription failed: "
                f"{get_backend_error(response)}"
            )
            return

        transcript = response.json().get(
            "transcript",
            "",
        ).strip()

        if not transcript:
            st.warning(
                "The speech service returned an "
                "empty transcript."
            )
            return

        st.session_state.audio_hashes[
            question_number
        ] = audio_hash

        st.session_state[answer_key] = transcript
        st.rerun()

    except Exception as error:
        st.error(
            f"Unable to transcribe recording: {error}"
        )


def render_resume_section() -> None:

    """
    Render the resume upload and extraction interface.
    """

    st.subheader("1. Upload Resume")

    uploaded_file = st.file_uploader(
        "Upload the candidate resume",
        type=["pdf"],
        help="Only PDF resumes are currently supported.",
    )

    if uploaded_file is None:
        return

    if st.button(
        "Extract Candidate Profile",
        use_container_width=True,
    ):
        files = {
            "file": (
                uploaded_file.name,
                uploaded_file.getvalue(),
                "application/pdf",
            )
        }

        with st.spinner(
            "Extracting candidate name and technical skills..."
        ):
            try:
                response = requests.post(
                    UPLOAD_RESUME_URL,
                    files=files,
                    timeout=60,
                )

                if response.status_code != 200:
                    st.error(
                        "Resume extraction failed: "
                        f"{get_backend_error(response)}"
                    )
                    return

                data = response.json()

                extracted_skills = data.get(
                    "skills",
                    [],
                )

                candidate_name = data.get(
                    "name",
                    "Candidate",
                )

                st.session_state.candidate_name = (
                    candidate_name
                )

                st.session_state.extracted_skills = (
                    extracted_skills
                )

                st.session_state.selected_skills = (
                    extracted_skills.copy()
                )

                st.session_state.resume_processed = True

                reset_interview_state()

                st.success(
                    "Candidate profile extracted successfully."
                )

                st.rerun()

            except requests.ConnectionError:
                st.error(
                    "Could not connect to FastAPI. "
                    "Make sure the backend server is running."
                )

            except requests.Timeout:
                st.error(
                    "Resume extraction took too long."
                )

            except Exception as error:
                st.error(
                    f"Unexpected error: {error}"
                )



def render_candidate_profile() -> None:

    """
    Display candidate information and allow skill selection.
    """

    if not st.session_state.resume_processed:
        return

    st.divider()
    st.subheader("2. Review Candidate Profile")

    candidate_name = st.text_input(
        "Candidate name",
        value=st.session_state.candidate_name,
    )

    st.session_state.candidate_name = (
        candidate_name.strip()
    )

    extracted_skills = (
        st.session_state.extracted_skills or []
    )

    selected_skills = st.multiselect(
        "Select the skills to evaluate",
        options=extracted_skills,
        default=[
            skill
            for skill in st.session_state.selected_skills
            if skill in extracted_skills
        ],
    )

    st.session_state.selected_skills = selected_skills

    if selected_skills:
        badges = " ".join(
            f"`{skill}`"
            for skill in selected_skills
        )

        st.markdown(
            f"**Selected skills:** {badges}"
        )



def render_interview_setup() -> None:

    """
    Render interview limits and the start button.
    """

    if not st.session_state.resume_processed:
        return

    if st.session_state.interview_started:
        return

    st.divider()
    st.subheader("3. Configure Adaptive Interview")

    col1, col2 = st.columns(2)

    with col1:
        maximum_questions = st.number_input(
            "Maximum total questions",
            min_value=1,
            max_value=20,
            value=st.session_state.maximum_questions,
            step=1,
        )

    with col2:
        maximum_per_skill = st.number_input(
            "Maximum questions per skill",
            min_value=1,
            max_value=10,
            value=(
                st.session_state
                .maximum_questions_per_skill
            ),
            step=1,
        )

    st.session_state.maximum_questions = int(
        maximum_questions
    )

    st.session_state.maximum_questions_per_skill = int(
        maximum_per_skill
    )

    if st.button(
        "Start Adaptive Interview",
        type="primary",
        use_container_width=True,
    ):
        
        start_adaptive_interview()


def start_adaptive_interview() -> None:

    """
    Call FastAPI to create an interview session and
    retrieve the first adaptive question.
    """

    candidate_name = (
        st.session_state.candidate_name.strip()
    )

    selected_skills = (
        st.session_state.selected_skills
    )

    if not candidate_name:
        st.warning(
            "Please provide the candidate name."
        )
        return

    if not selected_skills:
        st.warning(
            "Select at least one technical skill."
        )
        return

    payload = {
        "candidate_name": candidate_name,
        "skills": selected_skills,
        "maximum_questions": (
            st.session_state.maximum_questions
        ),
        "maximum_questions_per_skill": (
            st.session_state
            .maximum_questions_per_skill
        ),
    }

    with st.spinner(
        "Generating the first adaptive question..."
    ):
        try:
            response = requests.post(
                ADAPTIVE_START_URL,
                json=payload,
                timeout=90,
            )

            if response.status_code != 200:
                st.error(
                    "Could not start the interview: "
                    f"{get_backend_error(response)}"
                )
                return

            data = response.json()

            st.session_state.interview_id = data[
                "interview_id"
            ]

            st.session_state.current_question_number = (
                data["question_number"]
            )

            st.session_state.current_question = data[
                "question"
            ]

            st.session_state.interview_finished = (
                data.get(
                    "interview_finished",
                    False,
                )
            )

            st.session_state.interview_started = True
            st.session_state.current_answer = ""
            st.session_state.interview_history = []
            st.session_state.latest_analysis = None
            st.session_state.latest_decision = None
            st.session_state.question_audio = None

            st.rerun()

        except requests.ConnectionError:
            st.error(
                "Could not connect to the FastAPI server."
            )

        except requests.Timeout:
            st.error(
                "The backend took too long to generate "
                "the first question."
            )

        except KeyError as error:
            st.error(
                "The backend response is missing a required "
                f"field: {error}"
            )

        except Exception as error:
            st.error(
                "Unexpected error while starting the "
                f"interview: {error}"
            )


def render_current_question() -> None:
    """
    Render the current adaptive question with:

    - Interview progress
    - Question metadata
    - Text-to-Speech playback
    - Microphone recording
    - Speech-to-Text transcription
    - Editable answer text area
    - Submit and finish buttons
    """

    if not st.session_state.interview_started:
        return

    if st.session_state.interview_finished:
        return

    question = st.session_state.current_question

    if not question:
        st.error(
            "The interview is active, but no current "
            "question is available."
        )
        return

    question_number = (
        st.session_state.current_question_number
    )

    maximum_questions = (
        st.session_state.maximum_questions
    )

    question_text = question.get(
        "question",
        "Question unavailable.",
    )

    skill = question.get(
        "skill",
        "Unknown",
    )

    topic = question.get(
        "topic",
        "General",
    )

    difficulty = question.get(
        "difficulty",
        "medium",
    )

    question_type = question.get(
        "question_type",
        "initial",
    )

    # Every question receives separate widget keys.
    # This prevents the previous transcript or recording
    # from appearing in the next question.
    answer_key = f"answer_input_{question_number}"
    recorder_key = f"mic_recorder_{question_number}"
    submit_key = f"submit_answer_{question_number}"
    finish_key = f"finish_interview_{question_number}"

    st.divider()
    st.subheader("Adaptive Technical Interview")

    # Interview progress
    progress = min(
        question_number / maximum_questions,
        1.0,
    )

    st.progress(progress)

    st.caption(
        f"Question {question_number} of up to "
        f"{maximum_questions}"
    )

    # Question metadata
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Skill",
            skill,
        )

    with col2:
        st.metric(
            "Difficulty",
            difficulty.title(),
        )

    with col3:
        st.metric(
            "Question Type",
            question_type.replace(
                "_",
                " ",
            ).title(),
        )

    # Generate TTS audio only once for this question
    generate_question_audio(
        question_text=question_text,
        question_number=question_number,
    )

    # Keep this container outside the three metadata columns
    with st.container(border=True):
        st.markdown(
            f"#### Question {question_number}"
        )

        st.write(question_text)

        st.caption(
            f"Topic: {topic}"
        )

        # Question audio
        if (
            st.session_state.question_audio
            and st.session_state.question_audio_number
            == question_number
        ):
            st.markdown("##### Listen to the question")

            st.audio(
                st.session_state.question_audio
            )

            if st.button(
                "Regenerate Question Audio",
                key=f"regenerate_audio_{question_number}",
                use_container_width=True,
            ):
                st.session_state.question_audio = None
                st.session_state.question_audio_number = None
                st.rerun()

        st.divider()

        # Candidate recording
        st.markdown("##### Record your answer")

        recorded_audio = mic_recorder(
            start_prompt="Start Recording",
            stop_prompt="Stop Recording",
            just_once=True,
            use_container_width=True,
            key=recorder_key,
        )

        if recorded_audio:
            audio_bytes = recorded_audio.get("bytes")

            # Depending on the package version, this may be
            # audio/wav, audio/webm, or another MIME type.
            mime_type = recorded_audio.get(
                "format",
                "audio/wav",
            )

            if audio_bytes:
                with st.spinner(
                    "Converting your voice answer to text..."
                ):
                    transcribe_recorded_answer(
                        audio_bytes=audio_bytes,
                        question_number=question_number,
                        answer_key=answer_key,
                        mime_type=mime_type,
                    )

        st.caption(
            "Review and edit the transcript before "
            "submitting your answer."
        )

        # Editable transcript/manual answer
        answer = st.text_area(
            "Your Answer",
            height=180,
            placeholder=(
                "Record your answer or type it manually. "
                "You can edit the transcript before submitting."
            ),
            key=answer_key,
        )

        submit_column, finish_column = st.columns(2)

        with submit_column:
            submit_button = st.button(
                "Submit Answer",
                type="primary",
                use_container_width=True,
                key=submit_key,
            )

        with finish_column:
            finish_button = st.button(
                "Finish Interview",
                use_container_width=True,
                key=finish_key,
            )

        if submit_button:
            submit_current_answer(answer)

        if finish_button:
            finish_adaptive_interview()

def submit_current_answer(
    candidate_answer: str,
) -> None:
    
    """
    Submit the current answer to FastAPI.

    The backend will:
    - analyze the answer
    - make the controller decision
    - generate the next question
    - update the interview state
    """

    candidate_answer = candidate_answer.strip()

    if not candidate_answer:
        st.warning(
            "Please provide an answer before submitting."
        )
        return

    interview_id = st.session_state.interview_id

    if not interview_id:
        st.error(
            "Interview ID is missing. "
            "Please restart the interview."
        )
        return

    current_question = (
        st.session_state.current_question or {}
    )

    payload = {
        "interview_id": interview_id,
        "candidate_answer": candidate_answer,
    }

    with st.spinner(
        "Analyzing your answer and preparing "
        "the next adaptive question..."
    ):
        try:
            response = requests.post(
                ADAPTIVE_ANSWER_URL,
                json=payload,
                timeout=120,
            )

            if response.status_code != 200:
                st.error(
                    "Could not process the answer: "
                    f"{get_backend_error(response)}"
                )
                return

            data = response.json()

            analysis = data.get(
                "analysis",
                {},
            )

            decision = data.get(
                "decision",
                {},
            )

            history_entry = {
                "question_number": (
                    st.session_state
                    .current_question_number
                ),
                "question": current_question.get(
                    "question",
                    "",
                ),
                "answer": candidate_answer,
                "skill": current_question.get(
                    "skill",
                    "Unknown",
                ),
                "topic": current_question.get(
                    "topic",
                    "General",
                ),
                "difficulty": current_question.get(
                    "difficulty",
                    "medium",
                ),
                "question_type": current_question.get(
                    "question_type",
                    "initial",
                ),
                "analysis": analysis,
                "decision": decision,
                "overall_score": (
                    calculate_answer_score(analysis)
                ),
            }

            st.session_state.interview_history.append(
                history_entry
            )

            st.session_state.latest_analysis = analysis
            st.session_state.latest_decision = decision

            interview_finished = data.get(
                "interview_finished",
                False,
            )

            st.session_state.interview_finished = (
                interview_finished
            )

            if interview_finished:
                st.session_state.current_question = None

            else:
                next_question = data.get(
                    "next_question"
                )

                next_question_number = data.get(
                    "next_question_number"
                )

                if not next_question:
                    st.error(
                        "The backend did not return the "
                        "next question."
                    )
                    return

                if next_question_number is None:
                    st.error(
                        "The backend did not return the "
                        "next question number."
                    )
                    return

                st.session_state.current_question = (
                    next_question
                )

                st.session_state.current_question_number = (
                    next_question_number
                )

                st.session_state.current_question = next_question
                st.session_state.current_question_number = (
                next_question_number
                )

            st.session_state.question_audio = None
            st.session_state.question_audio_number = None

            if "answer_input" in st.session_state:
                del st.session_state["answer_input"]

            st.rerun()

        except requests.ConnectionError:
            st.error(
                "Could not connect to FastAPI. "
                "Make sure the backend is running."
            )

        except requests.Timeout:
            st.error(
                "Answer processing took too long. "
                "Please try again."
            )

        except KeyError as error:
            st.error(
                "The backend response is missing a "
                f"required field: {error}"
            )

        except Exception as error:
            st.error(
                "Unexpected error while processing "
                f"the answer: {error}"
            )

def finish_adaptive_interview() -> None:

    """
    Manually finish the current adaptive interview.
    """

    interview_id = st.session_state.interview_id

    if not interview_id:
        st.error(
            "Interview ID is missing."
        )
        return

    payload = {
        "interview_id": interview_id,
    }

    with st.spinner(
        "Finishing the interview..."
    ):
        try:
            response = requests.post(
                ADAPTIVE_FINISH_URL,
                json=payload,
                timeout=30,
            )

            if response.status_code != 200:
                st.error(
                    "Could not finish the interview: "
                    f"{get_backend_error(response)}"
                )
                return

            st.session_state.interview_finished = True
            st.session_state.current_question = None
            st.session_state.current_answer = ""
            st.session_state.question_audio = None

            if "answer_input" in st.session_state:
                del st.session_state["answer_input"]

            st.rerun()

        except requests.ConnectionError:
            st.error(
                "Could not connect to FastAPI."
            )

        except requests.Timeout:
            st.error(
                "The finish request took too long."
            )

        except Exception as error:
            st.error(
                f"Unable to finish interview: {error}"
            )


def render_latest_analysis() -> None:

    """
    Display the evaluation of the most recently
    submitted answer.
    """

    analysis = st.session_state.latest_analysis
    decision = st.session_state.latest_decision

    if not analysis:
        return

    st.divider()

    with st.expander(
        "Previous Answer Analysis",
        expanded=True,
    ):
        overall_score = calculate_answer_score(
            analysis
        )

        st.metric(
            "Answer Score",
            f"{overall_score}/10",
        )

        col1, col2 = st.columns(2)

        with col1:
            st.metric(
                "Correctness",
                (
                    f"{analysis.get(
                        'correctness_score',
                        0,
                    )}/10"
                ),
            )

            st.metric(
                "Clarity",
                (
                    f"{analysis.get(
                        'clarity_score',
                        0,
                    )}/10"
                ),
            )

        with col2:
            st.metric(
                "Completeness",
                (
                    f"{analysis.get(
                        'completeness_score',
                        0,
                    )}/10"
                ),
            )

            st.metric(
                "Practical Understanding",
                (
                    f"{analysis.get(
                        'practical_understanding_score',
                        0,
                    )}/10"
                ),
            )

        st.markdown("#### Feedback")

        st.write(
            analysis.get(
                "feedback",
                "No feedback available.",
            )
        )

        strengths = analysis.get(
            "strengths",
            [],
        )

        if strengths:
            st.markdown("#### Strengths")

            for strength in strengths:
                st.write(f"- {strength}")

        missing_concepts = analysis.get(
            "missing_concepts",
            [],
        )

        if missing_concepts:
            st.markdown("#### Missing Concepts")

            for concept in missing_concepts:
                st.write(f"- {concept}")

        misconceptions = analysis.get(
            "misconceptions",
            [],
        )

        if misconceptions:
            st.markdown("#### Misconceptions")

            for misconception in misconceptions:
                st.write(f"- {misconception}")

        if decision:
            st.markdown("#### Adaptive Decision")

            action = decision.get(
                "action",
                "Unknown",
            )

            next_difficulty = decision.get(
                "next_difficulty",
                "Unknown",
            )

            st.write(
                f"**Next action:** "
                f"{action.replace('_', ' ').title()}"
            )

            st.write(
                f"**Next difficulty:** "
                f"{next_difficulty.title()}"
            )

            reason = decision.get(
                "reason"
            )

            if reason:
                st.write(
                    f"**Reason:** {reason}"
                )


def render_interview_completion() -> None:

    """
    Display the temporary Phase 3 interview summary.
    """

    if not st.session_state.interview_started:
        return

    if not st.session_state.interview_finished:
        return

    st.divider()
    st.success(
        "The adaptive interview has been completed."
    )

    st.header("Interview Summary")

    history = st.session_state.interview_history

    total_answered = len(history)

    st.metric(
        "Questions Answered",
        total_answered,
    )

    if history:
        answer_scores = [
            item.get("overall_score", 0)
            for item in history
        ]

        overall_score = round(
            sum(answer_scores) / len(answer_scores),
            2,
        )

        st.metric(
            "Average Technical Score",
            f"{overall_score}/10",
        )

        st.subheader("Question History")

        for item in history:
            title = (
                f"Question {item['question_number']} — "
                f"{item['skill']} — "
                f"{item['overall_score']}/10"
            )

            with st.expander(title):
                st.markdown("**Question**")
                st.write(item["question"])

                st.markdown("**Candidate answer**")
                st.write(item["answer"])

                analysis = item.get(
                    "analysis",
                    {},
                )

                st.markdown("**Feedback**")
                st.write(
                    analysis.get(
                        "feedback",
                        "No feedback available.",
                    )
                )

                decision = item.get(
                    "decision",
                    {},
                )

                if decision:
                    st.markdown(
                        "**Controller decision**"
                    )

                    st.write(
                        decision.get(
                            "action",
                            "Unknown",
                        )
                        .replace("_", " ")
                        .title()
                    )

    if st.button(
        "Start New Interview",
        type="primary",
        use_container_width=True,
    ):
        reset_interview_state()

        if "answer_input" in st.session_state:
            del st.session_state["answer_input"]

        st.rerun()



render_resume_section()
render_candidate_profile()
render_interview_setup()

if st.session_state.interview_finished:
    render_interview_completion()
else:
    render_current_question()
    render_latest_analysis()