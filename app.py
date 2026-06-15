import streamlit as st
import requests

st.set_page_config(page_title="IntervAI", page_icon="🔬", layout="centered")

#Defining backend URLS
BASE_URL = "http://127.0.0.1:8000"
UPLOAD_URL = f"{BASE_URL}/upload-resume"
GENERATE_URL = f"{BASE_URL}/generate-questions"
EVALUATE_URL = f"{BASE_URL}/evaluate"

st.title("🔬 IntervAI — Core Interview Engine")
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
        with st.spinner("Generating schema-locked interview questions..."):
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
    st.subheader("🔬 3. Interview Examination")
    

    client_name = st.session_state.generated_questions.get("candidate_name", "Candidate")
    questions_list = st.session_state.generated_questions.get("questions_list", [])

    st.write(f"**Candidate:** {client_name}")

    with st.form("Interview Submission form"):
        user_answers= {}

        for idx, q in enumerate(questions_list, 1):
            q_id = q.get("id", idx)
            q_text = q.get("question", "")

            with st.container(border=True):
                st.markdown(f"### Question {idx}")
                st.write(q_text)

                user_answers[q_id] = st.text_area(
                    "Type your detailed technical answer below:",
                    key=f"ans_{q_id}",
                    placeholder="Provide your systemic engineering approach or code explanation here..."
                )
    
        submit_interview = st.form_submit_button("Submit Interview for AI Evaluation", type="primary")

        if submit_interview:
            with st.spinner("Analyzing your answers..."):
                try:
                    submissions_list = []
                    for i, q_id in enumerate(user_answers):
                        dictionary_item = {
                            "question_id": q_id,
                            "question_text": questions_list[i].get("question", ""),
                            "user_answer": user_answers[q_id]
                        }
                        submissions_list.append(dictionary_item)
                    submission_payload = {
                        "candidate_name": client_name,  # Wraps the name string
                        "submissions": submissions_list  # Wraps your list inside the required key
                    }
                    
                    response = requests.post(EVALUATE_URL, json=submission_payload)

                    if response.status_code == 200:
                            st.session_state.scorecard = response.json()
                            st.success("Evaluation complete! Scroll down to view your scorecard.")
                    else:
                        st.error(f"Evaluation failed: {response.json().get('detail')}")
                    
                except Exception as e:
                    st.error(f"Error communicating with evaluation server: {str(e)}")


# Rendering the output result
if st.session_state.scorecard is not None:
    st.divider()
    st.header("🏆 AI Technical Interview Scorecard")

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
            
                             
                
    
                    

