# IntervAI — Adaptive AI Technical Interview Platform

IntervAI creates a personalized technical interview from a candidate's resume and selected skills. It asks one question at a time, analyzes each answer, applies deterministic interview rules, and generates the next question according to the candidate's performance.

The repository contains only the adaptive interview workflow. The earlier fixed-question Phase 1 and Phase 2 implementations have been removed.

## Features

- PDF resume parsing and technical-skill extraction
- Candidate skill selection and interview configuration
- One-question-at-a-time adaptive interviews
- Structured answer analysis with Pydantic
- Deterministic difficulty and routing decisions
- Clarification, follow-up, deeper-topic, new-topic, and new-skill questions
- Text-to-Speech question playback
- Speech-to-Text candidate answers
- Editable answer transcripts
- Interview history and completion summary
- FastAPI backend and Streamlit frontend

## Architecture

```text
Streamlit frontend
        ↓ HTTP
FastAPI routes
        ↓
Interview workflow manager
        ├── Answer analyzer service
        ├── Deterministic controller
        └── Question generator service
        ↓
Validated interview state and history
```

The responsibilities are separated as follows:

- **Routes** receive requests and return responses.
- **Workflow** coordinates the interview lifecycle.
- **Domain controller** applies predictable interview rules.
- **Services** call Gemini or process files and audio.
- **Schemas** validate application data.

## Project Structure

```text
IntervAI/
├── backend/
│   └── app/
│       ├── main.py
│       ├── api/
│       │   └── v1/
│       │       ├── router.py
│       │       └── routes/
│       │           ├── health.py
│       │           ├── resumes.py
│       │           ├── interviews.py
│       │           └── speech.py
│       ├── domain/
│       │   └── interview/
│       │       └── controller.py
│       ├── schemas/
│       │   ├── interview.py
│       │   ├── resume.py
│       │   └── speech.py
│       ├── services/
│       │   ├── interview/
│       │   │   ├── answer_analyzer.py
│       │   │   └── question_generator.py
│       │   ├── resume/
│       │   │   └── parser.py
│       │   └── speech/
│       │       ├── speech_to_text.py
│       │       └── text_to_speech.py
│       └── workflows/
│           └── interview/
│               └── manager.py
├── frontend/
│   └── app.py
├── tests/
│   ├── test_answer_analyzer.py
│   ├── test_controller.py
│   ├── test_question_generator.py
│   └── test_manager.py
├── .gitignore
└── README.md
```

## Adaptive Interview Workflow

### 1. Resume processing

1. The candidate uploads a PDF resume.
2. The resume service extracts the PDF text.
3. Gemini converts the text into structured resume information.
4. The candidate reviews and selects technical skills.

### 2. Interview start

1. The frontend sends the candidate name, selected skills, and question limits.
2. The workflow validates and cleans the input.
3. The question generator creates the initial question.
4. The workflow creates an interview ID and stores the initial state.

### 3. Answer processing

1. The candidate types an answer or records it using the microphone.
2. Speech-to-Text produces an editable transcript when voice input is used.
3. The answer analyzer evaluates the submitted answer.
4. The controller decides the next action and difficulty.
5. The question generator creates and validates the next question.
6. The workflow updates the interview state and history.

### 4. Completion

The interview finishes when the total question limit is reached, all selected skills receive enough coverage, or the candidate manually finishes the interview.

## Controller Actions

| Action | Purpose |
| --- | --- |
| `clarify` | Ask a simpler question about a weak or unclear answer |
| `follow_up` | Examine an important missing concept |
| `deepen_topic` | Test more advanced understanding |
| `change_topic` | Move to another topic within the current skill |
| `change_skill` | Begin evaluating another selected skill |
| `finish` | Complete the interview |

## API Endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Basic application health response |
| `POST` | `/upload-resume` | Extract candidate information and skills from a PDF |
| `POST` | `/text-to-speech` | Convert a question into speech |
| `POST` | `/speech-to-text` | Transcribe a recorded answer |
| `POST` | `/adaptive-interview/start` | Start an interview and generate the initial question |
| `POST` | `/adaptive-interview/answer` | Analyze an answer and return the next question |
| `GET` | `/adaptive-interview/{interview_id}` | Retrieve the current interview state |
| `POST` | `/adaptive-interview/finish` | Manually finish an interview |

## Environment

Create a local `.env` file containing:

```env
GOOGLE_API_KEY=your_google_api_key
```

The `.env` file is ignored by Git and must not be committed.

## Run the Backend

From the repository root:

```bash
uvicorn backend.app.main:app --reload
```

The API will normally be available at:

```text
http://127.0.0.1:8000
```

FastAPI documentation:

```text
http://127.0.0.1:8000/docs
```

## Run the Frontend

In another terminal, from the repository root:

```bash
streamlit run frontend/app.py
```

## Tests

The current tests cover:

- Structured answer analysis
- Deterministic controller decisions
- Initial and adaptive question generation
- Interview state and lifecycle management

Once the dependency manifest is added, the test suite can be run with:

```bash
pytest -v
```

## Current Limitations

- Interview sessions are stored in an in-memory dictionary.
- Sessions are lost when the backend restarts.
- No authentication or authorization is implemented.
- Model calls do not yet have centralized retries or fallback routing.
- Application logging and LangSmith observability are not implemented yet.
- Exact duplicate questions are rejected, but semantic duplicates are not detected.
- The final interview report is currently calculated in the frontend.

The next architectural step is to replace the manual interview manager with a LangGraph workflow while preserving the current analyzer, controller, and question-generator responsibilities.
