import math
import os
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv


load_dotenv()

DEFAULT_RESUME_PRIMARY_MODEL = "gemini/gemini-3.5-flash"


class LLMTask(str, Enum):
    RESUME_PARSING = "resume_parsing"


class ModelPolicyConfigurationError(ValueError):
    """Raised when an LLM routing policy is configured incorrectly."""


@dataclass(frozen=True, slots=True)
class ResumeRoutingPolicy:
    task: LLMTask
    primary_model: str
    fallback_model: str | None
    timeout_seconds: float | None
    primary_group: str = "resume-primary"
    fallback_group: str = "resume-fallback"


def _model_identifier(
    variable_name: str,
    *,
    default: str | None = None,
    optional: bool = False,
) -> str | None:
    configured_model = os.getenv(variable_name)

    if configured_model is None:
        model = default
    else:
        model = configured_model.strip()

    if not model:
        if optional:
            return None
        raise ModelPolicyConfigurationError(
            f"{variable_name} must contain a LiteLLM provider/model identifier."
        )

    provider, separator, model_name = model.partition("/")
    if not separator or not provider or not model_name:
        raise ModelPolicyConfigurationError(
            f"{variable_name} must use LiteLLM provider/model syntax."
        )

    return model


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


def get_model_policy(task: LLMTask) -> ResumeRoutingPolicy:
    if task is not LLMTask.RESUME_PARSING:
        raise ModelPolicyConfigurationError(
            f"No model policy is configured for task '{task.value}'."
        )

    primary_model = _model_identifier(
        "RESUME_PRIMARY_MODEL",
        default=DEFAULT_RESUME_PRIMARY_MODEL,
    )
    if primary_model is None:
        raise AssertionError("The resume primary model cannot be absent.")

    return ResumeRoutingPolicy(
        task=task,
        primary_model=primary_model,
        fallback_model=_model_identifier(
            "RESUME_FALLBACK_MODEL",
            optional=True,
        ),
        timeout_seconds=_resume_timeout_seconds(),
    )
