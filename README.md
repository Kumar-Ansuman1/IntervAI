# IntervAI — Adaptive AI Technical Interview Platform

IntervAI creates a personalized technical interview from a candidate's resume and selected skills. It asks one question at a time, analyzes each answer, applies deterministic interview rules, and generates the next question according to the candidate's performance.

The repository contains only the adaptive interview workflow. The earlier fixed-question Phase 1 and Phase 2 implementations have been removed.

## Features

- PDF resume parsing and technical-skill extraction
- Candidate skill selection and interview configuration
- One-question-at-a-time adaptive interviews
- Structured answer analysis with Pydantic
- Deterministic difficulty and LangGraph routing decisions
- Checkpointed workflow state for each interview session
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
        ↓
LangGraph state machine + checkpointer
        ├── Answer analyzer service
        ├── Deterministic controller
        └── Question generator service
        ↓
Validated interview state, history, and checkpoints
```

The responsibilities are separated as follows:

- **Routes** receive requests and return responses.
- **Workflow manager** keeps the API-facing functions stable.
- **LangGraph workflow** coordinates explicit nodes, branches, and state checkpoints.
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
│               ├── graph.py
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
3. LangGraph runs the `initialize_interview` node.
4. The question generator creates the initial question.
5. The in-memory checkpointer stores the initial graph state under the interview ID.

### 3. Answer processing

1. The candidate types an answer or records it using the microphone.
2. Speech-to-Text produces an editable transcript when voice input is used.
3. The `analyze_answer` node evaluates the submitted answer.
4. The deterministic `decide_next_step` node selects the next action and difficulty.
5. A conditional edge routes to completion or question generation.
6. The `generate_question` node creates and validates the next question.
7. The `update_interview` node updates the state and history.
8. LangGraph checkpoints each successful transition. A failed node can be retried without repeating completed upstream nodes.

### 4. Completion

The graph routes to `complete_after_answer` when the deterministic controller returns `finish`. A manual request routes directly to `finish_interview`.

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

- Interview sessions use LangGraph's in-memory checkpointer.
- Checkpoints are lost when the backend restarts; a database-backed checkpointer is still required for durable production persistence.
- No authentication or authorization is implemented.
- Model calls do not yet have centralized retries or fallback routing.
- Application logging and LangSmith observability are not implemented yet.
- Exact duplicate questions are rejected, but semantic duplicates are not detected.
- The final interview report is currently calculated in the frontend.

The next architectural steps are durable checkpoint storage, structured application logging, LangSmith observability, and a centralized model gateway with retry and fallback policies.
