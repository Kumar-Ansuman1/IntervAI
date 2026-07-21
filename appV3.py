import requests
import streamlit as st

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
    }

    for key, value in keys_to_reset.items():
        st.session_state[key] = value


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
    Render the current adaptive interview question.
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

    st.divider()
    st.subheader("Adaptive Technical Interview")

    st.markdown(
        f"### Question "
        f"{st.session_state.current_question_number}"
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

    with st.container(border=True):
        st.markdown("#### Interview Question")

        st.write(
            question.get(
                "question",
                "Question unavailable.",
            )
        )

        st.caption(
            f"Topic: {topic}"
        )

initialize_session_state()

render_resume_section()
render_candidate_profile()
render_interview_setup()
render_current_question()