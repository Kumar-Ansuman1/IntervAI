from fastapi import FastAPI

from backend.app.core.observability import (
    configure_observability,
    instrument_fastapi,
)


# Configure Logfire before importing routes so Pydantic models are
# instrumented when their classes are created.
configure_observability()

from backend.app.api.v1.router import api_router  # noqa: E402


def create_app() -> FastAPI:
    app = FastAPI(title="IntervAI API")
    app.include_router(api_router)
    instrument_fastapi(app)
    return app


app = create_app()
