# IntervAI — Adaptive AI Technical Interview Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![LiteLLM](https://img.shields.io/badge/Model_Gateway-LiteLLM-7B61FF)](https://docs.litellm.ai/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Logfire](https://img.shields.io/badge/Observability-Logfire-EF5B5B)](https://logfire.pydantic.dev/)

IntervAI is an adaptive technical interview platform that turns a candidate's resume and selected skills into a personalized, one-question-at-a-time interview. It combines structured resume parsing, LangGraph orchestration, deterministic interview decisions, task-specific model routing, voice interaction, checkpointed state, and privacy-conscious observability.

The current repository contains the adaptive interview workflow. The earlier fixed-question Phase 1 and Phase 2 implementations have been removed.

## Why this project is adaptive

A fixed interview asks every candidate the same predefined questions. IntervAI changes the interview path after every answer:

- A structured answer analyzer scores correctness, completeness, clarity, and practical understanding.
- A deterministic controller chooses whether to clarify, follow up, deepen the topic, change the topic, change the skill, or finish.
- LangGraph conditionally routes the interview to the next node and checkpoints each successful transition.
- The next question is generated for the selected action, skill, topic, and difficulty instead of being taken from a static list.
- A centralized LiteLLM gateway selects task-specific models and can use a bounded fallback when the configured primary model fails.

The model evaluates the answer, but application rules control the interview progression. This keeps routing predictable while preserving personalized question generation.

## Features

| Area | Implementation |
|---|---|
| Resume processing | PDF text extraction and Pydantic-validated candidate information and skills |
| Adaptive interviews | One question at a time, personalized from the candidate's selected skills and performance |
| Orchestration | LangGraph state machine with conditional edges and per-interview checkpoints |
| Answer analysis | Structured scores, strengths, missing concepts, misconceptions, feedback, and follow-up focus |
| Decision engine | Deterministic rules for action, topic, skill, and difficulty progression |
| Question generation | Initial, clarification, follow-up, deeper-topic, new-topic, and new-skill questions |
| Model gateway | LiteLLM task policies for resume parsing, question generation, answer analysis, STT, and TTS |
| Reliability | Environment-selected primary models, optional fallbacks, configurable timeouts, and bounded attempts |
| Voice interaction | Text-to-Speech question playback and Speech-to-Text answers with editable transcripts |
| Validation | Pydantic schemas for model outputs, API data, and interview state |
| Observability | Privacy-safe Logfire spans across FastAPI, LangGraph stages, and gateway requests |
| API and UI | FastAPI backend with a Streamlit frontend |
| Testing | Unit tests for gateway routing, resume parsing, interview services, workflow recovery, and observability |

## Architecture

~~~mermaid
flowchart TD
    A["Candidate"] --> B["Streamlit interface"]
    B --> C["FastAPI routes"]
    C --> D["Resume, interview, and speech services"]
    D --> E["LiteLLM task gateway"]
    E --> F["Primary model"]
    E -->|Primary failure| G["Fallback model"]
    F --> H["Pydantic-validated output"]
    G --> H
    H --> I["LangGraph interview state"]
    I --> J["Deterministic controller"]
    J -->|Continue| K["Next adaptive question"]
    K --> B
    J -->|Finish| L["Interview summary"]
    I --> M["In-memory checkpoint"]
~~~

## Interview lifecycle

1. The candidate uploads a PDF resume through the Streamlit interface.
2. FastAPI extracts the text and sends the resume-parsing task through the LiteLLM gateway.
3. The validated candidate profile and technical skills are returned for review and selection.
4. Starting an interview creates a LangGraph state and generates the first structured question.
5. The question can be displayed as text or played through the Text-to-Speech task.
6. The candidate submits a typed answer or records speech, which is converted into an editable transcript.
7. The answer-analysis task returns structured scores, feedback, strengths, missing concepts, and misconceptions.
8. The deterministic controller selects the next action and difficulty.
9. LangGraph either generates another adaptive question or completes the interview, checkpointing successful transitions under the interview ID.
10. Logfire records privacy-safe timing, routing, status, and error metadata throughout the request.

## Model gateway

IntervAI keeps model selection outside the application services. Each task reads a LiteLLM provider/model identifier and related options from environment variables, so a model can be changed without modifying resume, interview, or speech logic.

The included `.env.example` uses the following configuration:

| Task | Primary model | Fallback model |
|---|---|---|
| Resume parsing | `gemini/gemini-3.5-flash` | Optional; blank by default |
| Question generation | `gemini/gemini-3.1-flash-lite` | Optional; blank by default |
| Answer analysis | `gemini/gemini-3.1-flash-lite` | Optional; blank by default |
| Speech-to-Text | `groq/whisper-large-v3-turbo` | `gemini/gemini-3.1-flash-lite` |
| Text-to-Speech | `groq/canopylabs/orpheus-v1-english` | `gemini/gemini-3.1-flash-tts-preview` |

Gateway behavior:

- Structured tasks use a separate LiteLLM router per task and return only Pydantic-validated outputs.
- A configured structured fallback is attempted at most once; automatic retries are disabled to keep latency bounded.
- Speech tasks try the configured primary and then the fallback using the request mode required by each provider.
- The sample TTS policy skips the primary model for inputs over 200 characters and uses the fallback model instead.
- Optional API bases allow hosted providers or local LiteLLM-compatible models to be configured.
- LiteLLM message logging is disabled, exception messages are redacted, and API-key information is not emitted.
- Logfire records task, model, attempt, duration, status, and fallback metadata without adding prompts, transcripts, resume text, or candidate answers to custom spans.

## LangGraph workflow

![IntervAI adaptive interview LangGraph workflow](docs/images/langgraph-workflow.svg)

The graph accepts three operations:

- `start` routes to `initialize_interview`, generates the first question, and stores the initial checkpoint.
- `answer` analyzes the latest answer and runs the deterministic controller. A conditional edge then completes the interview or generates and stores another question.
- `finish` routes directly to `finish_interview` for manual completion.

The interview ID is also used as the LangGraph `thread_id`, keeping candidate checkpoints separate. If a downstream node fails, the pending operation can resume without rerunning successful upstream nodes.

## Controller actions

| Action | Purpose |
|---|---|
| `clarify` | Ask a simpler question about a weak, unclear, or incorrect answer |
| `follow_up` | Examine an important concept missing from a partially correct answer |
| `deepen_topic` | Test deeper reasoning, trade-offs, implementation, or limitations |
| `change_topic` | Move to a different topic within the current skill |
| `change_skill` | Begin evaluating another selected skill |
| `finish` | Complete the interview |

## Project structure

~~~text
IntervAI/
├── backend/
│   └── app/
│       ├── main.py                         # FastAPI application
│       ├── core/
│       │   └── observability.py            # Logfire configuration and privacy controls
│       ├── api/v1/
│       │   ├── router.py                   # Versioned API router
│       │   └── routes/
│       │       ├── health.py               # Health endpoint
│       │       ├── resumes.py              # Resume upload endpoint
│       │       ├── interviews.py           # Adaptive interview endpoints
│       │       └── speech.py               # STT and TTS endpoints
│       ├── domain/interview/
│       │   └── controller.py               # Deterministic interview decisions
│       ├── schemas/
│       │   ├── interview.py                # Interview state and structured outputs
│       │   ├── resume.py                   # Candidate resume schema
│       │   └── speech.py                   # Speech request schema
│       ├── services/
│       │   ├── llm/
│       │   │   └── gateway.py              # LiteLLM routing, fallback, and speech gateway
│       │   ├── interview/
│       │   │   ├── answer_analyzer.py      # Structured answer evaluation
│       │   │   └── question_generator.py   # Initial and adaptive questions
│       │   ├── resume/
│       │   │   └── parser.py               # PDF extraction and structured parsing
│       │   └── speech/
│       │       ├── speech_to_text.py       # Audio transcription service
│       │       └── text_to_speech.py       # Question audio generation
│       └── workflows/interview/
│           ├── graph.py                    # LangGraph state machine and checkpointer
│           └── manager.py                  # Workflow lifecycle and service wiring
├── frontend/
│   └── app.py                              # Streamlit interview interface
├── docs/images/
│   └── langgraph-workflow.svg              # Workflow visualization
├── tests/
│   ├── test_llm_gateway.py                 # Gateway, fallback, speech, and privacy tests
│   ├── test_resume_parser.py               # Resume service tests
│   ├── test_answer_analyzer.py             # Answer-analysis tests
│   ├── test_question_generator.py          # Question-generation tests
│   ├── test_controller.py                  # Deterministic controller tests
│   ├── test_manager.py                     # Graph lifecycle and recovery tests
│   └── test_observability.py               # Privacy-safe telemetry tests
├── .env.example                            # Model and observability configuration
├── requirements.txt                        # Application and test dependencies
└── README.md
~~~

## Tech stack

- **Backend:** Python, FastAPI, Uvicorn, Pydantic
- **Workflow orchestration:** LangGraph
- **Prompt construction:** LangChain Core
- **Model gateway:** LiteLLM Router
- **Default model providers:** Google Gemini and Groq
- **Resume processing:** PyPDF
- **Voice:** LiteLLM transcription and speech interfaces
- **Observability:** Pydantic Logfire
- **Interface:** Streamlit and `streamlit-mic-recorder`
- **Testing:** pytest

## Getting started

### 1. Prerequisites

You need:

- Python 3.10 or newer
- A Google AI API key for the default structured tasks and Gemini speech fallbacks
- A Groq API key for the default Speech-to-Text and Text-to-Speech primary models
- A Logfire write token only if you want hosted traces

### 2. Clone and create a virtual environment

~~~bash
git clone https://github.com/Kumar-Ansuman1/IntervAI.git
cd IntervAI
python -m venv .venv
~~~

Activate the environment:

~~~powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
~~~

~~~bash
# macOS or Linux
source .venv/bin/activate
~~~

Install the dependencies:

~~~bash
python -m pip install --upgrade pip
pip install -r requirements.txt
~~~

### 3. Configure environment variables

Create `.env` from the included example. The file is ignored by Git and must not be committed.

~~~powershell
# Windows PowerShell
Copy-Item .env.example .env
~~~

~~~bash
# macOS or Linux
cp .env.example .env
~~~

At minimum, configure the provider keys used by your selected models:

~~~dotenv
GOOGLE_API_KEY=your_google_api_key
GROQ_API_KEY=your_groq_api_key

RESUME_PRIMARY_MODEL=gemini/gemini-3.5-flash
QUESTION_GENERATION_PRIMARY_MODEL=gemini/gemini-3.1-flash-lite
ANSWER_ANALYSIS_PRIMARY_MODEL=gemini/gemini-3.1-flash-lite

SPEECH_TO_TEXT_PRIMARY_MODEL=groq/whisper-large-v3-turbo
SPEECH_TO_TEXT_FALLBACK_MODEL=gemini/gemini-3.1-flash-lite

TEXT_TO_SPEECH_PRIMARY_MODEL=groq/canopylabs/orpheus-v1-english
TEXT_TO_SPEECH_FALLBACK_MODEL=gemini/gemini-3.1-flash-tts-preview

LOGFIRE_TOKEN=
~~~

Keep the associated `*_API_KEY_ENV`, speech request modes, voices, response formats, optional fallbacks, API bases, and timeouts from `.env.example`. Model identifiers must use LiteLLM's `provider/model` syntax.

## Run the application

Start the FastAPI backend from the repository root:

~~~bash
uvicorn backend.app.main:app --reload
~~~

Useful local endpoints:

- API health response: http://127.0.0.1:8000/
- Interactive API documentation: http://127.0.0.1:8000/docs

In another terminal, start the Streamlit frontend:

~~~bash
streamlit run frontend/app.py
~~~

Streamlit normally opens at http://localhost:8501.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Basic application health response |
| `POST` | `/upload-resume` | Extract candidate information and skills from a PDF |
| `POST` | `/text-to-speech` | Convert an interview question into speech |
| `POST` | `/speech-to-text` | Transcribe a recorded candidate answer |
| `POST` | `/adaptive-interview/start` | Start an interview and generate the initial question |
| `POST` | `/adaptive-interview/answer` | Analyze an answer and return the next interview state |
| `GET` | `/adaptive-interview/{interview_id}` | Retrieve the current interview state |
| `POST` | `/adaptive-interview/finish` | Manually finish an interview |

## Pydantic Logfire observability

IntervAI configures Logfire before importing the API routes. The current instrumentation records:

- FastAPI request duration, status, and exceptions
- Pydantic validation metrics
- LangGraph start, analyze, decide, generate, update, and finish stages
- Gateway task, selected model, fallback usage, attempt status, and duration
- Trace correlation using the interview ID

Candidate names, answer text, resume content, transcripts, request headers, uploaded audio, prompts, and generated model content are not added to custom span attributes. LiteLLM message logging is disabled and sensitive exception and API-key information is redacted.

Set `LOGFIRE_TOKEN` to send traces to a hosted Logfire project. With `LOGFIRE_SEND_TO_LOGFIRE=if-token-present`, the application can still run locally without a token.

## Tests

The test suite covers:

- Environment-backed, provider-agnostic task configuration
- Structured-output validation and bounded primary/fallback routing
- Speech primary and fallback behavior
- Safe gateway errors and privacy-conscious telemetry
- Resume parsing
- Answer analysis and adaptive question generation
- Deterministic controller decisions
- LangGraph lifecycle, conditional routing, and checkpoint recovery
- Manual interview completion

Run all tests with:

~~~bash
pytest -v
~~~

## Current limitations

IntervAI is production-minded, but it is not yet production-complete:

- Interview sessions use an in-memory LangGraph checkpointer and are lost when the backend restarts.
- Authentication, authorization, rate limiting, and persistent candidate storage are not implemented.
- Structured-task fallbacks are supported but remain blank in `.env.example` until provider choices are configured.
- Exact duplicate questions are rejected, but semantic duplicates are not detected.
- Generated audio is stored in a local temporary directory.
- The final interview report is calculated in the frontend rather than persisted by the backend.
- There is no Docker setup, automated CI workflow, or infrastructure-as-code deployment configuration yet.
- The repository has unit tests, but it does not yet include a golden evaluation dataset for interview quality and model-routing performance.

## Roadmap

- [ ] Replace the in-memory checkpointer with durable database-backed state
- [ ] Add authentication, authorization, rate limiting, and candidate data controls
- [ ] Configure and benchmark production fallbacks for every structured task
- [ ] Add semantic duplicate-question detection
- [ ] Generate and persist the final interview report in the backend
- [ ] Add golden datasets and automated evaluations for question quality and answer-scoring consistency
- [ ] Add Docker, CI checks, and repeatable backend/frontend deployment configuration
- [ ] Add production sampling, alerts, and gateway reliability dashboards

## Author

Built by [Kumar Ansuman Sahu](https://github.com/Kumar-Ansuman1).

If this project helps you learn or build adaptive AI interview systems, consider starring the repository.
