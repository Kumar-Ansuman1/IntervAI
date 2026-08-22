import base64
import logging
import math
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

import litellm
import logfire
from dotenv import load_dotenv
from litellm import Router
from litellm.exceptions import LITELLM_EXCEPTION_TYPES
from litellm.types.router import RouterRateLimitError, RouterRateLimitErrorBasic
from pydantic import BaseModel, ValidationError


load_dotenv()

T = TypeVar("T", bound=BaseModel)


class LLMTask(str, Enum):
    RESUME_PARSING = "resume_parsing"
    QUESTION_GENERATION = "question_generation"
    ANSWER_ANALYSIS = "answer_analysis"
    SPEECH_TO_TEXT = "speech_to_text"
    TEXT_TO_SPEECH = "text_to_speech"


@dataclass(frozen=True, slots=True)
class TaskModelConfig:
    env_prefix: str
    primary_model: str
    primary_group: str
    fallback_group: str
    primary_api_key_env: str | None = None
    primary_api_base: str | None = None
    fallback_model: str | None = None
    fallback_api_key_env: str | None = None
    fallback_api_base: str | None = None
    timeout_seconds: float | None = None


STT_PROMPT = "Transcribe this interview answer. Return only the transcript."


TASK_MODELS: dict[LLMTask, TaskModelConfig] = {
    LLMTask.RESUME_PARSING: TaskModelConfig(
        env_prefix="RESUME",
        primary_model="",
        primary_group="resume-primary",
        fallback_group="resume-fallback",
    ),
    LLMTask.QUESTION_GENERATION: TaskModelConfig(
        env_prefix="QUESTION_GENERATION",
        primary_model="",
        primary_group="question-primary",
        fallback_group="question-fallback",
    ),
    LLMTask.ANSWER_ANALYSIS: TaskModelConfig(
        env_prefix="ANSWER_ANALYSIS",
        primary_model="",
        primary_group="answer-primary",
        fallback_group="answer-fallback",
    ),
    LLMTask.SPEECH_TO_TEXT: TaskModelConfig(
        env_prefix="SPEECH_TO_TEXT",
        primary_model="",
        primary_group="stt-primary",
        fallback_group="stt-fallback",
    ),
    LLMTask.TEXT_TO_SPEECH: TaskModelConfig(
        env_prefix="TEXT_TO_SPEECH",
        primary_model="",
        primary_group="tts-primary",
        fallback_group="tts-fallback",
    ),
}


class LLMGatewayError(RuntimeError):
    """Safe public error for a failed structured model request."""


class LLMGatewayConfigurationError(ValueError):
    """Safe public error for invalid model credentials or configuration."""


class _StructuredResponseError(ValueError):
    """Raised when LiteLLM returns no usable structured content."""


class _SpeechResponseError(ValueError):
    """Raised when LiteLLM returns no usable speech content."""


_REQUEST_ERRORS = tuple(LITELLM_EXCEPTION_TYPES) + (
    RouterRateLimitError,
    RouterRateLimitErrorBasic,
    ValidationError,
    _StructuredResponseError,
)

_SPEECH_REQUEST_ERRORS = _REQUEST_ERRORS + (
    AttributeError,
    OSError,
    TimeoutError,
    TypeError,
    _SpeechResponseError,
)


def _optional_env(variable_name: str, default: str | None = None) -> str | None:
    value = os.getenv(variable_name, default)
    return value.strip() if value and value.strip() else None


def _required_env(variable_name: str) -> str:
    value = _optional_env(variable_name)
    if value is None:
        raise LLMGatewayConfigurationError(f"{variable_name} is required.")

    return value


def _validated_model(variable_name: str, model: str) -> str:
    provider, separator, model_name = model.partition("/")
    if not separator or not provider or not model_name:
        raise LLMGatewayConfigurationError(
            f"{variable_name} must use LiteLLM provider/model syntax."
        )

    return model


def _timeout_seconds(variable_name: str) -> float | None:
    configured_timeout = _optional_env(variable_name)
    if configured_timeout is None:
        return None

    try:
        timeout_seconds = float(configured_timeout)
    except ValueError as error:
        raise LLMGatewayConfigurationError(
            f"{variable_name} must be a positive number."
        ) from error

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise LLMGatewayConfigurationError(
            f"{variable_name} must be a positive number."
        )

    return timeout_seconds


def _positive_integer(variable_name: str) -> int | None:
    configured_value = _optional_env(variable_name)
    if configured_value is None:
        return None

    try:
        value = int(configured_value)
    except ValueError as error:
        raise LLMGatewayConfigurationError(
            f"{variable_name} must be a positive integer."
        ) from error

    if value <= 0:
        raise LLMGatewayConfigurationError(
            f"{variable_name} must be a positive integer."
        )

    return value


def get_task_model_config(task: LLMTask) -> TaskModelConfig:
    try:
        defaults = TASK_MODELS[task]
    except KeyError as error:
        raise LLMGatewayConfigurationError(
            f"No model configuration exists for task '{task.value}'."
        ) from error

    prefix = defaults.env_prefix
    primary_model_variable = f"{prefix}_PRIMARY_MODEL"
    primary_model = _optional_env(primary_model_variable)
    if primary_model is None:
        raise LLMGatewayConfigurationError(
            f"{primary_model_variable} is required."
        )

    fallback_model_variable = f"{prefix}_FALLBACK_MODEL"
    fallback_model = _optional_env(fallback_model_variable)

    return TaskModelConfig(
        env_prefix=prefix,
        primary_model=_validated_model(
            primary_model_variable,
            primary_model,
        ),
        primary_api_base=_optional_env(
            f"{prefix}_PRIMARY_API_BASE",
        ),
        primary_api_key_env=_optional_env(
            f"{prefix}_PRIMARY_API_KEY_ENV",
        ),
        primary_group=defaults.primary_group,
        fallback_model=(
            _validated_model(fallback_model_variable, fallback_model)
            if fallback_model
            else None
        ),
        fallback_api_base=_optional_env(
            f"{prefix}_FALLBACK_API_BASE",
        ),
        fallback_api_key_env=_optional_env(
            f"{prefix}_FALLBACK_API_KEY_ENV",
        ),
        fallback_group=defaults.fallback_group,
        timeout_seconds=_timeout_seconds(
            f"{prefix}_MODEL_TIMEOUT_SECONDS"
        ),
    )


def _deployment(
    group: str,
    model: str,
    api_base: str | None,
    api_key_env: str | None,
) -> dict[str, object]:
    params: dict[str, object] = {"model": model}

    if api_base:
        params["api_base"] = api_base

    if api_key_env:
        api_key = os.getenv(api_key_env, "").strip()
        if not api_key:
            raise LLMGatewayConfigurationError(
                f"{api_key_env} is required for the configured model."
            )
        params["api_key"] = api_key

    return {"model_name": group, "litellm_params": params}


def _configure_litellm_privacy() -> None:
    litellm.turn_off_message_logging = True
    litellm.redact_messages_in_exceptions = True
    litellm.redact_user_api_key_info = True
    logging.getLogger("LiteLLM Router").disabled = True


def _audio_request_options(
    config: TaskModelConfig,
    *,
    fallback: bool,
) -> dict[str, object]:
    model = config.fallback_model if fallback else config.primary_model
    api_base = config.fallback_api_base if fallback else config.primary_api_base
    api_key_env = (
        config.fallback_api_key_env
        if fallback
        else config.primary_api_key_env
    )

    if model is None:
        raise LLMGatewayConfigurationError(
            "The configured speech fallback model is unavailable."
        )

    options: dict[str, object] = {
        "model": model,
        "max_retries": 0,
        "turn_off_message_logging": True,
    }

    if api_base:
        options["api_base"] = api_base

    if api_key_env:
        api_key = os.getenv(api_key_env, "").strip()
        if not api_key:
            raise LLMGatewayConfigurationError(
                f"{api_key_env} is required for the configured model."
            )
        options["api_key"] = api_key

    if config.timeout_seconds is not None:
        options["timeout"] = config.timeout_seconds

    return options


@lru_cache(maxsize=len(LLMTask))
def get_litellm_router(
    task: LLMTask = LLMTask.RESUME_PARSING,
) -> Router:
    _configure_litellm_privacy()
    config = get_task_model_config(task)
    model_list = [
        _deployment(
            config.primary_group,
            config.primary_model,
            config.primary_api_base,
            config.primary_api_key_env,
        )
    ]
    router_options: dict[str, object] = {
        "model_list": model_list,
        "num_retries": 0,
        "max_fallbacks": 1,
        "routing_strategy": "simple-shuffle",
        "set_verbose": False,
    }

    if config.fallback_model:
        model_list.append(
            _deployment(
                config.fallback_group,
                config.fallback_model,
                config.fallback_api_base,
                config.fallback_api_key_env,
            )
        )
        router_options["fallbacks"] = [
            {config.primary_group: [config.fallback_group]}
        ]

    if config.timeout_seconds is not None:
        router_options["timeout"] = config.timeout_seconds

    return Router(**router_options)


def _validate_response(response: object, response_model: type[T]) -> T:
    try:
        content = response.choices[0].message.content  # type: ignore[attr-defined]
    except (AttributeError, IndexError, TypeError) as error:
        raise _StructuredResponseError from error

    if isinstance(content, str) and content.strip():
        return response_model.model_validate_json(content)
    if isinstance(content, Mapping):
        return response_model.model_validate(dict(content))

    raise _StructuredResponseError


def _routing_result(
    response: object,
    config: TaskModelConfig,
) -> tuple[str | None, bool]:
    metadata = getattr(response, "_hidden_params", {})
    metadata = metadata if isinstance(metadata, Mapping) else {}
    final_model = metadata.get("litellm_model_name") or getattr(
        response,
        "model",
        None,
    )

    headers = metadata.get("additional_headers", {})
    model_group = (
        headers.get("x-litellm-model-group")
        if isinstance(headers, Mapping)
        else None
    )
    fallback_used = model_group == config.fallback_group

    if (
        model_group is None
        and config.fallback_model
        and isinstance(final_model, str)
    ):
        fallback_name = config.fallback_model.partition("/")[2]
        fallback_used = final_model in {
            config.fallback_model,
            fallback_name,
        }

    return final_model if isinstance(final_model, str) else None, fallback_used


class LLMGateway:
    def __init__(
        self,
        *,
        router: Router | None = None,
        config_loader: Callable[[LLMTask], TaskModelConfig] = (
            get_task_model_config
        ),
    ) -> None:
        self._use_task_routers = router is None
        self._router = router
        self._config_loader = config_loader

    def speech_to_text(
        self,
        *,
        audio_bytes: bytes,
        filename: str = "interview-answer.wav",
        mime_type: str | None = None,
        language: str | None = None,
        prompt: str = STT_PROMPT,
        response_format: str = "json",
    ) -> str:
        _configure_litellm_privacy()
        config = self._config_loader(LLMTask.SPEECH_TO_TEXT)
        attempts = [("primary", config.primary_model, False)]
        if config.fallback_model:
            attempts.append(("fallback", config.fallback_model, True))

        for attempt, selected_model, fallback in attempts:
            provider = selected_model.partition("/")[0]
            started_at = time.perf_counter()
            option_prefix = (
                f"{config.env_prefix}_FALLBACK"
                if fallback
                else f"{config.env_prefix}_PRIMARY"
            )
            request_mode = _required_env(
                f"{option_prefix}_REQUEST_MODE"
            ).lower()
            if request_mode not in {"transcription", "completion"}:
                raise LLMGatewayConfigurationError(
                    f"{option_prefix}_REQUEST_MODE must be "
                    "'transcription' or 'completion'."
                )

            with logfire.span(
                "litellm gateway: speech request",
                task=LLMTask.SPEECH_TO_TEXT.value,
                selected_model=selected_model,
                provider=provider,
                attempt=attempt,
                status="started",
                success=False,
            ) as span:
                try:
                    request_options = _audio_request_options(
                        config,
                        fallback=fallback,
                    )
                    if request_mode == "transcription":
                        audio_file: object = (
                            (filename, audio_bytes, mime_type)
                            if mime_type
                            else (filename, audio_bytes)
                        )
                        transcription_options: dict[str, object] = {
                            "file": audio_file,
                            "prompt": prompt,
                            "response_format": response_format,
                            **request_options,
                        }
                        if language:
                            transcription_options["language"] = language

                        response = litellm.transcription(
                            **transcription_options,
                        )
                        transcript = getattr(response, "text", None)
                        if transcript is None and isinstance(response, Mapping):
                            transcript = response.get("text")
                    else:
                        audio_format = ""
                        if mime_type:
                            audio_format = (
                                mime_type.split(";", 1)[0]
                                .partition("/")[2]
                                .removeprefix("x-")
                            )
                        if not audio_format:
                            audio_format = (
                                Path(filename).suffix.lstrip(".").lower()
                            )
                        audio_format = audio_format or "wav"
                        encoded_audio = base64.b64encode(audio_bytes).decode(
                            "ascii"
                        )
                        response = litellm.completion(
                            messages=[
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": prompt},
                                        {
                                            "type": "input_audio",
                                            "input_audio": {
                                                "data": encoded_audio,
                                                "format": audio_format,
                                            },
                                        },
                                    ],
                                }
                            ],
                            **request_options,
                        )
                        try:
                            transcript = response.choices[0].message.content
                        except (AttributeError, IndexError, TypeError) as error:
                            raise _SpeechResponseError from error

                    if not isinstance(transcript, str) or not transcript.strip():
                        raise _SpeechResponseError(
                            "The transcription response was empty."
                        )
                except _SPEECH_REQUEST_ERRORS as error:
                    span.set_attribute("status", "error")
                    span.set_attribute("error_type", type(error).__name__)
                else:
                    transcript = transcript.strip()
                    span.set_attribute("status", "success")
                    span.set_attribute("success", True)
                    span.set_attribute(
                        "transcript_character_count",
                        len(transcript),
                    )
                    return transcript
                finally:
                    span.set_attribute(
                        "duration_ms",
                        round((time.perf_counter() - started_at) * 1000, 3),
                    )

        raise LLMGatewayError("Speech to text model request failed.") from None

    def text_to_speech(
        self,
        *,
        text: str,
        output_path: str | Path,
        voice: str | None = None,
    ) -> str:
        _configure_litellm_privacy()
        config = self._config_loader(LLMTask.TEXT_TO_SPEECH)
        max_primary_characters = _positive_integer(
            f"{config.env_prefix}_PRIMARY_MAX_CHARACTERS"
        )
        fallback_only = (
            max_primary_characters is not None
            and len(text) > max_primary_characters
        )
        attempts: list[tuple[str, str, bool]] = []

        if not fallback_only:
            attempts.append(("primary", config.primary_model, False))
        if config.fallback_model:
            attempts.append(("fallback", config.fallback_model, True))

        audio_path = Path(output_path)
        for attempt, selected_model, fallback in attempts:
            provider = selected_model.partition("/")[0]
            started_at = time.perf_counter()
            option_prefix = (
                f"{config.env_prefix}_FALLBACK"
                if fallback
                else f"{config.env_prefix}_PRIMARY"
            )
            selected_voice = voice or _required_env(f"{option_prefix}_VOICE")
            audio_format = _optional_env(
                f"{option_prefix}_RESPONSE_FORMAT"
            )

            with logfire.span(
                "litellm gateway: speech request",
                task=LLMTask.TEXT_TO_SPEECH.value,
                selected_model=selected_model,
                provider=provider,
                attempt=attempt,
                voice=selected_voice,
                status="started",
                success=False,
                primary_skipped_input_limit=(fallback_only and fallback),
            ) as span:
                try:
                    request_options = _audio_request_options(
                        config,
                        fallback=fallback,
                    )
                    if audio_format:
                        request_options["response_format"] = audio_format

                    response = litellm.speech(
                        input=text,
                        voice=selected_voice,
                        **request_options,
                    )
                    stream_to_file = getattr(response, "stream_to_file", None)
                    if not callable(stream_to_file):
                        raise _SpeechResponseError(
                            "The speech response contained no audio."
                        )

                    audio_path.parent.mkdir(parents=True, exist_ok=True)
                    stream_to_file(audio_path)
                except _SPEECH_REQUEST_ERRORS as error:
                    span.set_attribute("status", "error")
                    span.set_attribute("error_type", type(error).__name__)
                else:
                    span.set_attribute("status", "success")
                    span.set_attribute("success", True)
                    return str(audio_path)
                finally:
                    span.set_attribute(
                        "duration_ms",
                        round((time.perf_counter() - started_at) * 1000, 3),
                    )

        raise LLMGatewayError("Text to speech model request failed.") from None

    def generate_structured(
        self,
        *,
        task: LLMTask,
        prompt: str,
        response_model: type[T],
        temperature: float | None = None,
    ) -> T:
        config = self._config_loader(task)
        router = (
            get_litellm_router(task)
            if self._use_task_routers
            else self._router
        )
        if router is None:
            raise AssertionError("The LiteLLM router is unavailable.")
        result: T | None = None
        request_failed = False

        with logfire.span(
            "litellm gateway: structured request",
            task=task.value,
            primary_model=config.primary_model,
            fallback_configured=config.fallback_model is not None,
            timeout_configured=config.timeout_seconds is not None,
            response_model=response_model.__name__,
            status="started",
            fallback_used=False,
        ) as span:
            try:
                completion_options: dict[str, object] = {
                    "model": config.primary_group,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": response_model,
                    "enable_json_schema_validation": True,
                    "turn_off_message_logging": True,
                    "num_retries": 0,
                }
                if temperature is not None:
                    completion_options["temperature"] = temperature

                response = router.completion(**completion_options)
                result = _validate_response(response, response_model)
            except _REQUEST_ERRORS as error:
                request_failed = True
                span.set_attribute("status", "error")
                span.set_attribute("error_type", type(error).__name__)
            else:
                final_model, fallback_used = _routing_result(
                    response,
                    config,
                )
                span.set_attribute("status", "success")
                span.set_attribute("fallback_used", fallback_used)
                span.set_attribute("response_type", type(result).__name__)
                if final_model:
                    span.set_attribute("final_model", final_model)

        if request_failed:
            task_name = task.value.replace("_", " ").capitalize()
            raise LLMGatewayError(f"{task_name} model request failed.") from None

        if result is None:
            raise AssertionError("Structured response validation produced no result.")

        return result


@lru_cache(maxsize=1)
def get_llm_gateway() -> LLMGateway:
    return LLMGateway()
