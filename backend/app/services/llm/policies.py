import math
import os
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv


load_dotenv()

DEFAULT_RESUME_PRIMARY_MODEL = "gemini/gemini-3.5-flash"
DEFAULT_RESUME_PRIMARY_API_KEY_ENV = "GOOGLE_API_KEY"
DEFAULT_QUESTION_PRIMARY_MODEL = "gemini/gemini-3.1-flash-lite"
DEFAULT_QUESTION_PRIMARY_API_KEY_ENV = "GOOGLE_API_KEY"


class LLMTask(str, Enum):
    RESUME_PARSING = "resume_parsing"
    QUESTION_GENERATION = "question_generation"


class ModelPolicyConfigurationError(ValueError):
    """Raised when an LLM routing policy is configured incorrectly."""


@dataclass(frozen=True, slots=True)
class ModelConfig:
    model: str
    api_base: str | None = None
    api_key_env: str | None = None


@dataclass(frozen=True, slots=True)
class ModelRoutingPolicy:
    task: LLMTask
    primary: ModelConfig
    fallback: ModelConfig | None
    timeout_seconds: float | None
    primary_group: str
    fallback_group: str


ResumeRoutingPolicy = ModelRoutingPolicy


def _optional_env(variable_name: str, default: str | None = None) -> str | None:
    value = os.getenv(variable_name, default)
    return value.strip() if value and value.strip() else None


def _model_config(
    model_variable: str,
    api_base_variable: str,
    api_key_env_variable: str,
    *,
    default_model: str | None = None,
    default_api_key_env: str | None = None,
) -> ModelConfig | None:
    model = _optional_env(model_variable, default_model)
    if model is None:
        return None

    provider, separator, model_name = model.partition("/")
    if not separator or not provider or not model_name:
        raise ModelPolicyConfigurationError(
            f"{model_variable} must use LiteLLM provider/model syntax."
        )

    return ModelConfig(
        model=model,
        api_base=_optional_env(api_base_variable),
        api_key_env=_optional_env(
            api_key_env_variable,
            default_api_key_env,
        ),
    )


def _timeout_seconds(variable_name: str) -> float | None:
    configured_timeout = _optional_env(variable_name)
    if configured_timeout is None:
        return None

    try:
        timeout_seconds = float(configured_timeout)
    except ValueError as error:
        raise ModelPolicyConfigurationError(
            f"{variable_name} must be a positive number."
        ) from error

    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ModelPolicyConfigurationError(
            f"{variable_name} must be a positive number."
        )

    return timeout_seconds


def _routing_policy(
    *,
    task: LLMTask,
    variable_prefix: str,
    default_model: str,
    default_api_key_env: str,
    primary_group: str,
    fallback_group: str,
) -> ModelRoutingPolicy:
    primary = _model_config(
        f"{variable_prefix}_PRIMARY_MODEL",
        f"{variable_prefix}_PRIMARY_API_BASE",
        f"{variable_prefix}_PRIMARY_API_KEY_ENV",
        default_model=default_model,
        default_api_key_env=default_api_key_env,
    )
    if primary is None:
        raise AssertionError(f"The {task.value} primary model cannot be absent.")

    return ModelRoutingPolicy(
        task=task,
        primary=primary,
        fallback=_model_config(
            f"{variable_prefix}_FALLBACK_MODEL",
            f"{variable_prefix}_FALLBACK_API_BASE",
            f"{variable_prefix}_FALLBACK_API_KEY_ENV",
        ),
        timeout_seconds=_timeout_seconds(
            f"{variable_prefix}_MODEL_TIMEOUT_SECONDS"
        ),
        primary_group=primary_group,
        fallback_group=fallback_group,
    )


def get_model_policy(task: LLMTask) -> ModelRoutingPolicy:
    if task is LLMTask.RESUME_PARSING:
        return _routing_policy(
            task=task,
            variable_prefix="RESUME",
            default_model=DEFAULT_RESUME_PRIMARY_MODEL,
            default_api_key_env=DEFAULT_RESUME_PRIMARY_API_KEY_ENV,
            primary_group="resume-primary",
            fallback_group="resume-fallback",
        )

    if task is LLMTask.QUESTION_GENERATION:
        return _routing_policy(
            task=task,
            variable_prefix="QUESTION_GENERATION",
            default_model=DEFAULT_QUESTION_PRIMARY_MODEL,
            default_api_key_env=DEFAULT_QUESTION_PRIMARY_API_KEY_ENV,
            primary_group="question-primary",
            fallback_group="question-fallback",
        )

    raise ModelPolicyConfigurationError(
        f"No model policy is configured for task '{task.value}'."
    )

