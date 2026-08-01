# IntervAI — Adaptive AI Technical Interview Platform

![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python\&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi\&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Frontend-FF4B4B?logo=streamlit\&logoColor=white)
![Gemini](https://img.shields.io/badge/Google%20Gemini-AI-4285F4?logo=google\&logoColor=white)
![Phase](https://img.shields.io/badge/Phase%203-Adaptive%20Interview-success)
![License](https://img.shields.io/badge/License-TBD-lightgrey)

IntervAI is an AI-powered technical interview platform that creates personalized interviews from a candidate's resume and technical skills. It combines **FastAPI**, **Streamlit**, **Google Gemini**, **Pydantic**, **Text-to-Speech**, and **Speech-to-Text** to support both fixed-question and adaptive interview experiences.

The latest Phase 3 release changes IntervAI from a fixed interview workflow into a stateful adaptive interview engine. Instead of generating all questions in advance, the system now asks one question at a time, analyzes every answer immediately, and decides the most appropriate next step.

> **Project status:** Phase 3 adaptive interview flow is implemented for local development. Persistent storage, authentication, production deployment, and a React frontend are not currently implemented.

---

## Key Features

| Area                    | Features                                                                                                |
| ----------------------- | ------------------------------------------------------------------------------------------------------- |
| Resume processing       | PDF upload, resume parsing, candidate-name extraction, and technical-skill extraction                   |
| Fixed interview mode    | Generates exactly five questions in advance and evaluates all answers together                          |
| Adaptive interview mode | Generates one question at a time and adjusts the interview using the candidate's latest answer          |
| Answer analysis         | Evaluates correctness, completeness, clarity, and practical understanding                               |
| Dynamic decisions       | Clarify, follow up, deepen topic, change topic, change skill, or finish                                 |
| Difficulty control      | Increase, decrease, or maintain the current question difficulty                                         |
| Voice interaction       | Text-to-Speech playback, microphone recording, Speech-to-Text, and editable transcripts                 |
| State management        | Stores interview configuration, current state, counters, question metadata, and complete answer history |
| Structured AI output    | Uses Pydantic models to validate generated questions, analysis, decisions, and state                    |
| API access              | FastAPI endpoints for resume processing, speech features, fixed interviews, and adaptive interviews     |
| Testing                 | Unit tests for the analyzer, controller, adaptive question generator, and interview manager             |

---

## Phase-Wise Development

### Phase 1 — Fixed Technical Interview

Phase 1 introduced the original fixed-question interview workflow.

```text
Resume Upload
    ↓
Resume Parsing and Skill Extraction
    ↓
Generate Exactly 5 Technical Questions
    ↓
Candidate Submits Typed Answers
    ↓
Evaluate All Answers Together
    ↓
Generate Technical Scorecard and Feedback
```

**Implemented features:**

* Resume PDF upload
* Resume parsing and technical-skill extraction
* Generation of exactly five technical interview questions
* Typed answer submission
* Complete-answer evaluation after the interview
* Technical scorecard with feedback

### Phase 2 — Voice-Enabled Interview

Phase 2 improved the interview experience by adding voice interaction and one-question-at-a-time navigation while retaining the fixed set of five questions.

**Implemented features:**

* Text-to-Speech question playback
* Microphone-based voice recording
* Speech-to-Text transcription
* Editable transcript before submission
* Previous and next question navigation
* One-question-at-a-time interview interface
* Final evaluation after all fixed questions are answered

### Phase 3 — Adaptive Interview Engine

Phase 3 replaces the fixed interview sequence with a dynamic interview loop.

```text
Old fixed flow:
Generate 5 questions first → collect all answers → evaluate at the end

New adaptive flow:
Generate 1 question → analyze answer → decide next action
→ generate the next question → repeat until finished
```

**Implemented features:**

* Generate only one question at a time
* Generate the initial question separately from later adaptive questions
* Analyze every submitted answer immediately
* Dynamically decide whether to:

  * Ask a clarification question
  * Ask a follow-up question
  * Deepen the current topic
  * Change topic
  * Change skill
  * Finish the interview
* Increase, decrease, or maintain question difficulty
* Store the complete interview state and question-answer history
* Enforce question, clarification, and skill limits
* Prevent exact duplicate questions
* Return validated structured outputs
* Provide dedicated adaptive interview API endpoints
* Provide a new Streamlit Phase 3 frontend
* Display current question metadata:

  * Skill
  * Topic
  * Difficulty
  * Question type
* Submit answers one at a time
* Receive the next adaptive question immediately
* Display interview progress and a final summary

---

## Phase 3 Adaptive Interview Architecture

Phase 3 separates AI-based evaluation and generation from deterministic interview-control rules.

```text
┌──────────────────────────────────────────────────────────────┐
│                    Streamlit Phase 3 UI                      │
│  Resume → Skills → Configuration → Question → Voice/Answer  │
└──────────────────────────────┬───────────────────────────────┘
                               │ HTTP requests
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                         FastAPI API                          │
│       Start Interview | Submit Answer | Get State | Finish  │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    Interview Manager                         │
│  Session creation, history, state updates, and coordination │
└───────────────┬──────────────────┬──────────────────┬────────┘
                │                  │                  │
                ▼                  ▼                  ▼
┌────────────────────┐ ┌────────────────────┐ ┌──────────────────────┐
│  Answer Analyzer   │ │ Interview Controller│ │ Adaptive Question   │
│                    │ │                     │ │ Generator            │
│ AI-based analysis  │ │ Deterministic rules │ │ Initial + next      │
│ and answer scoring │ │ and limit handling  │ │ question generation │
└────────────────────┘ └────────────────────┘ └──────────────────────┘
                │                  │                  │
                └──────────────────┴──────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│       Updated Interview State and Question-Answer History   │
└──────────────────────────────────────────────────────────────┘
```

### Backend Components

| File                                                                | Responsibility                                                                                                                                                             |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/app/services/interview/answer_analyzer.py`                 | Evaluates correctness, completeness, clarity, and practical understanding; identifies strengths, missing concepts, and misconceptions; calculates the overall answer score |
| `backend/app/domain/interview/interview_controller.py`              | Applies deterministic Python rules; selects the next action and difficulty; enforces interview, skill, and clarification limits                                            |
| `backend/app/services/interview/adaptive_question_generator.py`     | Generates the first adaptive question and later questions using the previous answer and controller decision; validates structured output; prevents exact repetitions       |
| `backend/app/workflows/interview/interview_manager.py`              | Starts interviews, stores sessions, processes answers, updates state, coordinates Phase 3 components, and finishes interviews                                              |
| `backend/app/schemas/adaptive.py`                                   | Defines the adaptive request, response, question, analysis, decision, turn, and interview-state models                                                                     |
| `frontend/adaptive_app.py`                                          | Provides the adaptive Streamlit user interface                                                                                                                             |
| `backend/app/api/v1/routes/`                                        | Exposes the FastAPI routes for all interview phases                                                                                                                        |

### Responsibility Separation

The Phase 3 architecture follows a hybrid approach:

* **Gemini and the answer analyzer** interpret candidate answers.
* **The interview controller** applies predictable Python rules.
* **The adaptive question generator** creates the next question from the controller's decision.
* **The interview manager** coordinates the complete lifecycle and stores the session state.

This separation makes the adaptive flow easier to test, debug, and extend than placing all interview logic inside a single prompt.

---

## Complete Workflow

### 1. Resume and Skill Preparation

1. The candidate uploads a PDF resume.
2. FastAPI sends the resume to the PDF extractor.
3. The application extracts the candidate's name and technical skills.
4. The candidate reviews and selects the skills to include in the interview.

### 2. Adaptive Interview Configuration

The candidate configures the Phase 3 interview, including the skills and supported interview limits used by the backend.

### 3. Interview Start

1. The Streamlit frontend sends a request to `POST /adaptive-interview/start`.
2. The interview manager validates the configuration and creates an interview ID.
3. The adaptive question generator creates the initial question.
4. The initial question is stored as the first interview turn.
5. The API returns the current question and interview state.

### 4. Question Presentation

The frontend displays:

* Question text
* Skill
* Topic
* Difficulty
* Question type
* Interview progress

The candidate can read the question or play it through Text-to-Speech.

### 5. Answer Submission

1. The candidate types an answer or records it using the microphone.
2. Speech-to-Text converts the recording into text.
3. The candidate reviews and edits the transcript.
4. The frontend submits the answer to `POST /adaptive-interview/answer`.

### 6. Immediate Answer Analysis

The answer analyzer evaluates:

* Correctness
* Completeness
* Clarity
* Practical understanding
* Strengths
* Missing concepts
* Misconceptions
* Overall answer score

Detailed answer analysis is currently displayed during development to help validate the adaptive logic. In a production interface, some or all of this internal analysis may be hidden from the candidate.

### 7. Controller Decision

The interview controller uses the analysis, current state, and configured limits to select the next action:

| Action       | Meaning                                                               |
| ------------ | --------------------------------------------------------------------- |
| Clarify      | Ask the candidate to explain an unclear or incomplete answer          |
| Follow up    | Ask a related question based on the previous answer                   |
| Deepen topic | Test more advanced understanding of the current topic                 |
| Change topic | Continue with the same skill but move to another topic                |
| Change skill | Begin evaluating another selected technical skill                     |
| Finish       | End the interview because a limit or completion condition was reached |

The controller also decides whether the next question should be easier, harder, or remain at the current difficulty.

### 8. Next Question Generation

If the interview is still active:

1. The adaptive generator receives the previous question, candidate answer, answer analysis, controller decision, interview state, and question history.
2. Gemini generates the next structured question.
3. Pydantic validates the output.
4. The generator checks the question against previous questions to prevent exact duplication.
5. The interview manager stores the new turn and returns it to the frontend.

### 9. Interview Completion

The interview finishes when the controller selects the finish action, an interview limit is reached, or the user manually calls the finish endpoint.

The final Phase 3 result currently provides an interview summary based on the stored state and turn history. It can later be expanded into a dedicated backend-generated scorecard with skill-level scoring, stronger aggregation, and polished recommendations.

---

## Project Structure

```text
IntervAI/
├── app.py                       # Legacy Streamlit compatibility entry point
├── appV3.py                     # Adaptive Streamlit compatibility entry point
├── main.py                      # FastAPI compatibility entry point
├── .env
├── .gitignore
├── README.md
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py
│   │   │       └── routes/
│   │   │           ├── health.py
│   │   │           ├── resumes.py
│   │   │           ├── fixed_interviews.py
│   │   │           ├── adaptive_interviews.py
│   │   │           └── speech.py
│   │   ├── domain/
│   │   │   └── interview/
│   │   │       └── interview_controller.py
│   │   ├── schemas/
│   │   │   ├── schema.py
│   │   │   └── adaptive.py
│   │   ├── services/
│   │   │   ├── interview/
│   │   │   ├── resume/
│   │   │   └── speech/
│   │   └── workflows/
│   │       └── interview/
│   │           └── interview_manager.py
│   ├── interview/               # Legacy import compatibility
│   ├── resume/                  # Legacy import compatibility
│   └── speech/                  # Legacy import compatibility
├── frontend/
│   ├── legacy_app.py
│   └── adaptive_app.py
├── schemas/                     # Legacy import compatibility
├── tests/
│   ├── test_answer_analyzer.py
│   ├── test_interview_controller.py
│   ├── test_adaptive_question_generator.py
│   └── test_interview_manager.py
└── temp/
    ├── audio/
    └── audio_answers/
```

---

## Technology Stack

| Category               | Technology                                      |
| ---------------------- | ----------------------------------------------- |
| Programming language   | Python                                          |
| Backend API            | FastAPI                                         |
| Frontend               | Streamlit                                       |
| AI model               | Google Gemini                                   |
| Structured AI workflow | Gemini-generated output validated with Pydantic |
| Data validation        | Pydantic                                        |
| Resume processing      | PDF text extraction                             |
| Text-to-Speech         | Gemini-based TTS integration                    |
| Speech-to-Text         | Gemini-based transcription integration          |
| HTTP communication     | Requests                                        |
| Testing                | Pytest                                          |
| Development storage    | In-memory Python session dictionary             |
| Configuration          | Environment variables through `.env`            |

> A React frontend, PostgreSQL, Redis, authentication, and production deployment are possible future additions but are not part of the current implementation.

---

## FastAPI Endpoints

### Core and Fixed Interview Endpoints

| Method | Endpoint              | Purpose                                                                    |
| ------ | --------------------- | -------------------------------------------------------------------------- |
| `POST` | `/upload-resume`      | Upload a resume PDF and extract candidate information and technical skills |
| `POST` | `/generate-questions` | Generate the fixed set of five technical interview questions               |
| `POST` | `/evaluate`           | Evaluate the completed fixed-question interview and return a scorecard     |
| `POST` | `/text-to-speech`     | Convert an interview question into playable speech                         |
| `POST` | `/speech-to-text`     | Transcribe a recorded candidate answer                                     |

### Phase 3 Adaptive Interview Endpoints

| Method | Endpoint                             | Purpose                                                                                            |
| ------ | ------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `POST` | `/adaptive-interview/start`          | Create an adaptive interview session and generate its initial question                             |
| `POST` | `/adaptive-interview/answer`         | Submit one answer, analyze it, update the state, and return the next question or completion result |
| `GET`  | `/adaptive-interview/{interview_id}` | Retrieve the current interview state and question-answer history                                   |
| `POST` | `/adaptive-interview/finish`         | Manually finish an active adaptive interview                                                       |

When the FastAPI server is running, interactive API documentation is normally available at:

```text
http://127.0.0.1:8000/docs
```

---

## Installation

### Prerequisites

Before running the project, install:

* Git
* A recent Python 3 version compatible with the project dependencies
* A Google Gemini API key
* A browser with microphone permission for voice-based answers

### 1. Clone the Repository

```bash
git clone https://github.com/Kumar-Ansuman1/IntervAI.git
cd IntervAI
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

### 3. Activate the Virtual Environment

**Windows PowerShell:**

```powershell
.\venv\Scripts\Activate.ps1
```

**Windows Command Prompt:**

```cmd
venv\Scripts\activate
```

**macOS or Linux:**

```bash
source venv/bin/activate
```

### 4. Upgrade `pip`

```bash
python -m pip install --upgrade pip
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

Ensure that the project's `requirements.txt` contains all FastAPI, Streamlit, Gemini, Pydantic, speech, HTTP, PDF-processing, and testing dependencies used by the codebase.

---

## Environment Variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your_google_gemini_api_key
```

Keep the `.env` file private and ensure it is included in `.gitignore`.

Do not commit real API keys to GitHub.

---

## How to Run FastAPI

From the project root, activate the virtual environment and run:

```bash
uvicorn main:app --reload
```

The backend will be available at:

```text
http://127.0.0.1:8000
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

Keep this terminal running while using the Streamlit frontend.

---

## How to Run the Phase 3 Streamlit Frontend

Open a second terminal in the project root, activate the same virtual environment, and run:

```bash
streamlit run appV3.py
```

Streamlit normally opens the application at:

```text
http://localhost:8501
```

The Phase 3 frontend communicates with the FastAPI server at:

```text
http://127.0.0.1:8000
```

Make sure the FastAPI backend is running before starting or using the adaptive interview.

To run the earlier fixed-question Streamlit interface instead:

```bash
streamlit run app.py
```

---

## Testing

The Phase 3 modules include focused unit tests.

Run the complete test suite:

```bash
pytest -v
```

Run individual test files:

```bash
pytest tests/test_answer_analyzer.py -v
pytest tests/test_interview_controller.py -v
pytest tests/test_adaptive_question_generator.py -v
pytest tests/test_interview_manager.py -v
```

The tests cover the main responsibilities of:

* Structured answer analysis
* Deterministic controller decisions
* Initial and adaptive question generation
* Interview session creation and state updates
* Interview completion and history management

Because Gemini-backed tests can depend on external model responses, deterministic business rules should be tested separately from live AI integrations wherever possible.

---

## Current Limitations

1. **Interview sessions use in-memory storage.**
   Adaptive interview sessions are currently stored in a Python dictionary. All active sessions and their history are lost whenever the FastAPI server restarts.

2. **The system is designed primarily for local development.**
   Production deployment, scaling, monitoring, and centralized logging are not yet implemented.

3. **No authentication or authorization is implemented.**
   The current version does not provide candidate accounts, interviewer accounts, protected sessions, or role-based access.

4. **No Redis or database persistence is implemented.**
   PostgreSQL, Redis, or another persistent store may be added later, but they are not part of the current codebase.

5. **Duplicate prevention currently checks exact repetitions.**
   Semantically similar questions may still be generated even when their wording is different.

6. **AI evaluation may vary.**
   Gemini-generated analysis and questions can vary between requests and may require further prompt calibration and evaluation testing.

7. **Detailed answer analysis is development-focused.**
   Correctness details, missing concepts, misconceptions, and internal reasoning signals are currently useful for development but may be hidden or simplified in production.

8. **The Phase 3 final scorecard is currently a summary.**
   A dedicated backend-generated scorecard with per-skill aggregation, weighted scoring, recommendations, and polished feedback remains a future improvement.

9. **The frontend is currently Streamlit.**
   A React or Next.js frontend has not been implemented.

10. **External AI requests can add latency.**
    Answer analysis, question generation, TTS, and STT depend on model response time and network availability.

---

## Future Improvements

* Replace in-memory interview storage with a persistent database
* Add Redis only when distributed session or caching requirements justify it
* Build a dedicated backend-generated Phase 3 technical scorecard
* Add skill-level, topic-level, and difficulty-level performance aggregation
* Detect semantically similar questions, not only exact duplicates
* Improve scoring consistency with calibrated rubrics and reference criteria
* Hide internal answer-analysis fields from candidate-facing production views
* Add authentication, candidate profiles, interviewer roles, and protected interview access
* Add retry, timeout, concurrency, and request-version handling
* Improve temporary audio-file lifecycle management
* Build a React or Next.js frontend after the backend workflow is stable
* Add containerization, CI checks, and production deployment
* Add observability, structured logging, analytics, and error tracking
* Support interview reports that can be exported or shared

---

## Contributing

Contributions, improvements, and issue reports are welcome.

1. Fork the repository.

2. Create a feature branch:

   ```bash
   git checkout -b feature/your-feature-name
   ```

3. Make focused changes.

4. Add or update tests.

5. Run the test suite:

   ```bash
   pytest -v
   ```

6. Commit the changes:

   ```bash
   git commit -m "feat: describe your change"
   ```

7. Push the branch:

   ```bash
   git push origin feature/your-feature-name
   ```

8. Open a pull request with a clear explanation of the change.

Please avoid mixing unrelated refactoring and feature work in the same pull request.

---

## License

This repository currently does not include a public license.

Until a `LICENSE` file is added, reuse, modification, and distribution rights are not automatically granted. Add the selected license and update the license badge before publishing the project for external reuse.

---

## Author

**Kumar Ansuman Sahu**

B.Tech Computer Science and Engineering student focused on AI/ML engineering, LangChain, RAG, FastAPI, and intelligent application development.

`

---

## Acknowledgements

IntervAI uses Google Gemini for structured AI workflows and speech capabilities, FastAPI for backend APIs, Streamlit for the current user interface, and Pydantic for reliable data validation.
