import streamlit as st
import requests
from streamlit_mic_recorder import mic_recorder
import os

st.set_page_config(page_title="IntervAI", layout="centered")

#Defining backend URLS
BASE_URL = "http://127.0.0.1:8000"
UPLOAD_URL = f"{BASE_URL}/upload-resume"
GENERATE_URL = f"{BASE_URL}/generate-questions"
EVALUATE_URL = f"{BASE_URL}/evaluate"
TTS_URL = f"{BASE_URL}/text-to-speech"
SPEECH_TO_TEXT_URL= f"{BASE_URL}/speech-to-text"

st.title("IntervAI — Core Interview Engine")
st.caption("Upload your resume to instantly generate a customized technical interview scorecard blueprint.")

# It keeps the session data
if "extracted_skills" not in st.session_state:
    st.session_state.extracted_skills = None
if "candidate_name" not in st.session_state:
    st.session_state.candidate_name = ""
if "generated_questions" not in st.session_state:
    st.session_state.generated_questions = None
if "scorecard" not in st.session_state:
    st.session_state.scorecard = None
if "current_question" not in st.session_state:
    st.session_state.current_question = 0
if "candidate_answers" not in st.session_state:
    st.session_state.candidate_answers = {}
if "question_audio" not in st.session_state:
    st.session_state.question_audio = None



#Upload the resume
st.subheader("1. Resume Ingestion")
uploaded_file = st.file_uploader("Upload candidate resume (PDF format only)", type=["pdf"])

if uploaded_file is not None:
    if st.button("Extract skills and Profile"):
        with st.spinner("Parsing your resume..."):
            try:
                #Package the file and send it to the backend API
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                response = requests.post(UPLOAD_URL,files=files)

                if response.status_code == 200:
                    data = response.json() #Converts the raw text into json type so we can extract name and skills
                    st.session_state.extracted_skills = data.get("skills", [])
                    st.session_state.candidate_name = data.get("name", "Candidate")
                    st.success("Resume parsed successfully!")
                else:
                    st.error(f"Extraction failed: {response.json().get('detail')}")
            except Exception as e:
                st.error(f"Could not connect to FastAPI server: {str(e)}")

#Displaying the skills and also u can modify
if st.session_state.extracted_skills is not None:
    st.divider()
    st.subheader(f"2. Review Profile: {st.session_state.candidate_name}")
    selected_skills = st.multiselect(
        "Confirm or modify the extracted technical skills:",
        options=st.session_state.extracted_skills,
        default=st.session_state.extracted_skills
    )


#Question Generation pipeline
if st.button("Generate Interview Questions", type="primary"):
    if not selected_skills:
        st.warning("Please select at least one skill to generate interview questions.")
    else:
        with st.spinner("Generating interview questions..."):
            try:
                payload = {
                    "candidate_name": st.session_state.candidate_name,
                    "skills": selected_skills
                }
                response = requests.post(GENERATE_URL, json=payload)
                if response.status_code == 200:
                    st.session_state.generated_questions = response.json()
                    st.success("Interview prep data built!")
                else:
                    st.error(f"Generation failed: {response.json().get('detail')}")
            except Exception as e:
                st.error(f"Error communicating with generator endpoint: {str(e)}")



#Displaying the questions with input fields and sendig it to the evaluation engine

if st.session_state.generated_questions is not None:

    st.divider()
    st.subheader("Voice Interview")

    client_name = st.session_state.generated_questions.get("candidate_name", "Candidate")
    questions_list = st.session_state.generated_questions.get("questions_list", [])

    total_questions = len(questions_list)
    current = st.session_state.current_question

    st.write(f"### Candidate: {client_name}")

    progress = (current + 1) / total_questions
    st.progress(progress)

    st.markdown(f"### Question {current + 1} of {total_questions}")

    current_question = questions_list[current]

    question_id = current_question["id"]
    question_text = current_question["question"]

    if st.session_state.question_audio is None:

        with st.spinner("Generating AI voice..."):

            response = requests.post(TTS_URL,json={"text": question_text})

            if response.status_code == 200:
                st.session_state.question_audio = response.json()["audio_path"]

            else:
                st.write(response.status_code)
                st.write(response.text)

    with st.container(border=True):

        st.markdown("###  Interview Question")

        st.write(question_text)

        if st.session_state.question_audio:
            st.audio(st.session_state.question_audio)

        text_key = f"answer_{question_id}"
        if text_key not in st.session_state:
                st.session_state[text_key] = ""

        audio = mic_recorder(
            start_prompt="Start Recording",
            stop_prompt="Stop Recording",
            just_once=True,
            use_container_width=True
        )

        if audio:
            TEMP_AUDIO_DIR = "temp/audio_answers"
            os.makedirs(TEMP_AUDIO_DIR, exist_ok=True)

            audio_path = os.path.join(TEMP_AUDIO_DIR,f"answer_{question_id}.wav")



            with open(audio_path, "wb") as f:
                f.write(audio["bytes"])

            with open(audio_path, "rb") as audio_file:

                response = requests.post(SPEECH_TO_TEXT_URL,files={"audio": audio_file})

            if response.status_code == 200:
                transcript = response.json()["transcript"]
                st.session_state[text_key] = transcript
                st.session_state.candidate_answers[question_id] = transcript
                st.rerun()




        answer = st.text_area(
            "Your Answer",
            height=180,
            key=text_key
        )



        col1, col2 = st.columns(2)

        with col1:
            if current > 0:
                if st.button("⬅ Previous"):
                    st.session_state.candidate_answers[question_id] = st.session_state[text_key]
                    st.session_state.current_question -= 1
                    st.session_state.question_audio = None
                    st.rerun()
        with col2:
            if current < total_questions - 1:
                if st.button("Next ➜", type="primary"):
                    st.session_state.candidate_answers[question_id] = st.session_state[text_key]
                    st.session_state.current_question += 1
                    st.session_state.question_audio = None
                    st.rerun()


        if st.button("Submit Interview",type="primary"):
            st.session_state.candidate_answers[question_id] = answer
            submissions = []
            for question in questions_list:
                submissions.append({
                    "question_id": question["id"],
                    "question_text": question["question"],
                    "user_answer": st.session_state.candidate_answers.get(question["id"], "")
                     })

            payload ={
                    "candidate_name": client_name,
                    "submissions": submissions
                    }

            with st.spinner("Evaluating interview..."):
                response = requests.post(EVALUATE_URL, json=payload)

                if response.status_code == 200:
                    st.session_state.scorecard = response.json()
                    st.success("Interview completed!")

                else:
                    st.error(f"Status Code: {response.status_code}")
                    st.error(response.text)

#Rendering the scorecard
if st.session_state.scorecard is not None:
    st.divider()
    st.header("AI Technical Interview Scorecard")

    scorecard = st.session_state.scorecard

    #Overall Grade
    col1, col2 = st.columns([1, 2])
    with col1:
        rating = scorecard.get("overall_technical_rating", 0.0)
        st.metric(label="Overall Technical Rating", value=f"{rating} / 10")
    with col2:
        st.subheader("Summary Verdict")
        st.write(scorecard.get("summary_verdict", ""))

    st.subheader("Detailed Breakdown Per Question")

    #Individual Question Grade
    detailed_grades = scorecard.get("detailed_grades", [])
    for grade in detailed_grades:
        q_id = grade.get("question_id")
        q_score = grade.get("score", 0)
        q_feedback = grade.get("feedback", "")
        missing_kw = grade.get("missing_keywords", [])

        with st.container(border=True):
            st.markdown(f"#### Question ID #{q_id} — Score: **{q_score}/10**")
            st.write(f"**Feedback:** {q_feedback}")

            if missing_kw:
                st.markdown("**Missing Concepts/Keywords:**")
                badges = " ".join([f"`{kw}`" for kw in missing_kw])
                st.markdown(badges)
