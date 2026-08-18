import math
import os
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv


load_dotenv()

DEFAULT_RESUME_MODEL = "gemini-3.5-flash"


class LLMTask(str, Enum):
    RESUME_PARSING = "resume_parsing"


class LLMProvider(str, Enum):
    GOOGLE = "google"


class ModelPolicyConfigurationError(ValueError):
    """Raised when an LLM task policy is configured incorrectly."""


@dataclass(frozen=True, slots=True)
class ModelConfig:
    provider: LLMProvider
    model_name: str
    request_timeout_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class ModelPolicy:
    task: LLMTask
    primary: ModelConfig
    fallback: ModelConfig | None = None


def _resume_primary_model() -> str:
    configured_model = os.getenv("RESUME_PRIMARY_MODEL")

    if configured_model is None:
        return DEFAULT_RESUME_MODEL

    model_name = configured_model.strip()
    if not model_name:
        raise ModelPolicyConfigurationError(
            "RESUME_PRIMARY_MODEL must contain a model name."
        )

    return model_name


def _resume_fallback_model() -> str | None:
    configured_model = os.getenv("RESUME_FALLBACK_MODEL")

    if configured_model is None:
        return None

    return configured_model.strip() or None


def _resume_timeout_seconds() -> float | None:
    configured_timeout = os.getenv("RESUME_MODEL_TIMEOUT_SECONDS")

    if configured_timeout is None or not configured_timeout.strip():
        return None

    try:
        timeout_seconds = float(configured_timeout)
    except ValueError as error:
        raise ModelPolicyConfigurationError(
            "RESUME_MODEL_TIMEOUT_SECONDS must be a positive number."
        ) from error

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ModelPolicyConfigurationError(
            "RESUME_MODEL_TIMEOUT_SECONDS must be a positive number."
        )

    return timeout_seconds


def get_model_policy(task: LLMTask) -> ModelPolicy:
    if task is not LLMTask.RESUME_PARSING:
        raise ModelPolicyConfigurationError(
            f"No model policy is configured for task '{task.value}'."
        )

    timeout_seconds = _resume_timeout_seconds()
    fallback_model = _resume_fallback_model()

    return ModelPolicy(
        task=task,
        primary=ModelConfig(
            provider=LLMProvider.GOOGLE,
            model_name=_resume_primary_model(),
            request_timeout_seconds=timeout_seconds,
        ),
        fallback=(
            ModelConfig(
                provider=LLMProvider.GOOGLE,
                model_name=fallback_model,
                request_timeout_seconds=timeout_seconds,
            )
            if fallback_model
            else None
        ),
    )
