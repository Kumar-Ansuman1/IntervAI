import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.core.observability import (
    configure_observability,
    instrument_fastapi,
)


# Configure Logfire before importing routes.
configure_observability()

from backend.app.api.v1.router import api_router  # noqa: E402


def create_app() -> FastAPI:
    app = FastAPI(title="IntervAI API")

    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    frontend_url = os.getenv("FRONTEND_URL", "").strip().rstrip("/")

    if frontend_url:
        allowed_origins.append(frontend_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Authorization"],
    )

    audio_directory = Path("temp/audio")
    audio_directory.mkdir(parents=True, exist_ok=True)

    app.mount(
        "/temp/audio",
        StaticFiles(directory=audio_directory),
        name="audio",
    )

    app.include_router(api_router)
    instrument_fastapi(app)

    return app


app = create_app()