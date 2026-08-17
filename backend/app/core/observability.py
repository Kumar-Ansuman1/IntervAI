import os
from typing import Any, Literal

import logfire
from dotenv import load_dotenv
from fastapi import FastAPI
from starlette.requests import Request
from starlette.websockets import WebSocket


_configured = False
_instrumented_app_ids: set[int] = set()


def _send_to_logfire_setting() -> bool | Literal["if-token-present"]:
    value = os.getenv(
        "LOGFIRE_SEND_TO_LOGFIRE",
        "if-token-present",
    ).strip().lower()

    if value in {"1", "true", "yes", "on"}:
        return True

    if value in {"0", "false", "no", "off"}:
        return False

    return "if-token-present"


def _summarize_validation_errors(
    errors: object,
) -> list[dict[str, str]]:
    if not isinstance(errors, list):
        return []

    summarized_errors: list[dict[str, str]] = []

    for error in errors:
        if not isinstance(error, dict):
            continue

        location = error.get("loc", ())
        if isinstance(location, (list, tuple)):
            location_text = ".".join(str(part) for part in location)
        else:
            location_text = str(location)

        summarized_errors.append(
            {
                "type": str(error.get("type", "validation_error")),
                "location": location_text,
                "message": str(error.get("msg", "Invalid value")),
            }
        )

    return summarized_errors


def _safe_request_attributes(
    request: Request | WebSocket,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    errors = _summarize_validation_errors(
        attributes.get("errors"),
    )
    safe_attributes: dict[str, Any] = {
        "route": request.url.path,
    }

    if errors:
        safe_attributes["validation_error_count"] = len(errors)
        safe_attributes["errors"] = errors

    return safe_attributes


def configure_observability() -> None:
    global _configured

    if _configured:
        return

    load_dotenv()

    logfire.configure(
        service_name=os.getenv(
            "LOGFIRE_SERVICE_NAME",
            "intervai-api",
        ),
        environment=os.getenv(
            "LOGFIRE_ENVIRONMENT",
            "development",
        ),
        send_to_logfire=_send_to_logfire_setting(),
        scrubbing=logfire.ScrubbingOptions(
            extra_patterns=[
                "candidate[._ -]?answer",
                "candidate[._ -]?name",
                "resume",
                "transcript",
                "audio",
            ]
        ),
    )

    # Validation metrics provide useful failure-rate visibility without
    # exporting model inputs such as names, answers, or resume data.
    logfire.instrument_pydantic(record="metrics")

    # Gemini prompts and completions remain elided unless content capture
    # is explicitly enabled outside this application.
    logfire.instrument_google_genai()

    _configured = True


def instrument_fastapi(app: FastAPI) -> None:
    app_id = id(app)

    if app_id in _instrumented_app_ids:
        return

    logfire.instrument_fastapi(
        app,
        capture_headers=False,
        request_attributes_mapper=_safe_request_attributes,
        excluded_urls=os.getenv("LOGFIRE_EXCLUDED_URLS"),
    )
    _instrumented_app_ids.add(app_id)
