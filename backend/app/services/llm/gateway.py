import logging
import os
from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import Any, Protocol, TypeVar

import litellm
import logfire
from litellm import Router
from litellm.exceptions import LITELLM_EXCEPTION_TYPES
from litellm.types.router import (
    RouterRateLimitError,
    RouterRateLimitErrorBasic,
)
from pydantic import BaseModel, ValidationError

from backend.app.services.llm.policies import (
    LLMTask,
    ModelPolicyConfigurationError,
    ResumeRoutingPolicy,
    get_model_policy,
)


T = TypeVar("T", bound=BaseModel)
PolicyLoader = Callable[[LLMTask], ResumeRoutingPolicy]

_LITELLM_REQUEST_ERRORS = tuple(LITELLM_EXCEPTION_TYPES) + (
    RouterRateLimitError,
    RouterRateLimitErrorBasic,
)


class LLMGatewayError(RuntimeError):
    """Safe public error for a failed structured model request."""


class LLMGatewayConfigurationError(ValueError):
    """Safe public error for invalid gateway credentials or setup."""


class _StructuredResponseError(ValueError):
    """Internal marker for a missing or unsupported response body."""


class CompletionRouter(Protocol):
    def completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> object: ...


def _provider_name(model: str) -> str:
    return model.partition("/")[0].lower()


def _google_api_key(model: str) -> str | None:
    if _provider_name(model) != "gemini":
        return None

    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise LLMGatewayConfigurationError(
            "GOOGLE_API_KEY is required for the configured Gemini model."
        )

    return api_key


def _deployment(model_group: str, model: str) -> dict[str, object]:
    litellm_params: dict[str, object] = {"model": model}
    google_api_key = _google_api_key(model)

    if google_api_key is not None:
        litellm_params["api_key"] = google_api_key

    return {
        "model_name": model_group,
        "litellm_params": litellm_params,
    }


def _configure_litellm_privacy() -> None:
    # LiteLLM's Router error logger can include invalid structured output in
    # its exception text even when verbose mode is disabled. Manual Logfire
    # spans below retain safe failure metadata, so suppress that raw logger.
    litellm.turn_off_message_logging = True
    litellm.redact_messages_in_exceptions = True
    litellm.redact_user_api_key_info = True
    logging.getLogger("LiteLLM Router").disabled = True


@lru_cache(maxsize=1)
def get_litellm_router() -> Router:
    _configure_litellm_privacy()
    policy = get_model_policy(LLMTask.RESUME_PARSING)
    model_list = [
        _deployment(policy.primary_group, policy.primary_model),
    ]
    router_kwargs: dict[str, object] = {
        "model_list": model_list,
        "num_retries": 0,
        "max_fallbacks": 1,
        "routing_strategy": "simple-shuffle",
        "set_verbose": False,
    }

    if policy.fallback_model is not None:
        model_list.append(
            _deployment(policy.fallback_group, policy.fallback_model)
        )
        router_kwargs["fallbacks"] = [
            {
                policy.primary_group: [policy.fallback_group],
            }
        ]

    if policy.timeout_seconds is not None:
        router_kwargs["timeout"] = policy.timeout_seconds

    return Router(**router_kwargs)


def _value(container: object, name: str) -> object | None:
    if isinstance(container, Mapping):
        return container.get(name)
    return getattr(container, name, None)


def _validated_result(
    response: object,
    response_model: type[T],
) -> T:
    choices = _value(response, "choices")
    if not isinstance(choices, (list, tuple)) or not choices:
        raise _StructuredResponseError(
            "The model response did not contain a completion choice."
        )

    message = _value(choices[0], "message")
    if message is None:
        raise _StructuredResponseError(
            "The model response did not contain a completion message."
        )

    content = _value(message, "content")
    if isinstance(content, str):
        if not content.strip():
            raise _StructuredResponseError(
                "The model response content was empty."
            )
        return response_model.model_validate_json(content)

    if isinstance(content, Mapping):
        return response_model.model_validate(dict(content))

    raise _StructuredResponseError(
        "The model response content had an unsupported type."
    )


def _final_model(response: object) -> str | None:
    hidden_params = getattr(response, "_hidden_params", None)
    if isinstance(hidden_params, Mapping):
        litellm_model_name = hidden_params.get("litellm_model_name")
        if isinstance(litellm_model_name, str) and litellm_model_name:
            return litellm_model_name

    model = _value(response, "model")
    if isinstance(model, str) and model:
        return model

    return None


def _final_model_group(response: object) -> str | None:
    hidden_params = getattr(response, "_hidden_params", None)
    if not isinstance(hidden_params, Mapping):
        return None

    additional_headers = hidden_params.get("additional_headers")
    if not isinstance(additional_headers, Mapping):
        return None

    model_group = additional_headers.get("x-litellm-model-group")
    if isinstance(model_group, str) and model_group:
        return model_group

    return None


def _model_identifiers_match(actual: str, configured: str) -> bool:
    configured_name = configured.partition("/")[2]
    return actual == configured or actual == configured_name


def _fallback_used(
    final_model_group: str | None,
    final_model: str | None,
    policy: ResumeRoutingPolicy,
) -> bool:
    if final_model_group is not None:
        return final_model_group == policy.fallback_group

    if final_model is None or policy.fallback_model is None:
        return False

    return _model_identifiers_match(final_model, policy.fallback_model)


class LLMGateway:
    def __init__(
        self,
        *,
        router: CompletionRouter | None = None,
        policy_loader: PolicyLoader = get_model_policy,
    ) -> None:
        self._router = router if router is not None else get_litellm_router()
        self._policy_loader = policy_loader

    def generate_structured(
        self,
        *,
        task: LLMTask,
        prompt: str,
        response_model: type[T],
    ) -> T:
        if task is not LLMTask.RESUME_PARSING:
            raise ModelPolicyConfigurationError(
                f"No model policy is configured for task '{task.value}'."
            )

        policy = self._policy_loader(task)
        if policy.task is not task:
            raise ModelPolicyConfigurationError(
                "The loaded model policy does not match the requested task."
            )

        messages = [{"role": "user", "content": prompt}]
        request_error: Exception | None = None
        programming_error: Exception | None = None
        validated_result: T | None = None

        with logfire.span(
            "litellm gateway: structured request",
            task=task.value,
            primary_model=policy.primary_model,
            fallback_configured=policy.fallback_model is not None,
            timeout_configured=policy.timeout_seconds is not None,
            response_model=response_model.__name__,
            status="started",
            fallback_used=False,
        ) as span:
            try:
                response = self._router.completion(
                    model=policy.primary_group,
                    messages=messages,
                    response_format=response_model,
                    enable_json_schema_validation=True,
                    turn_off_message_logging=True,
                    num_retries=0,
                )
                validated_result = _validated_result(
                    response,
                    response_model,
                )
            except Exception as error:
                span.set_attribute("status", "error")
                span.set_attribute("error_type", type(error).__name__)

                if isinstance(
                    error,
                    _LITELLM_REQUEST_ERRORS
                    + (ValidationError, _StructuredResponseError),
                ):
                    request_error = error
                else:
                    programming_error = error
            else:
                final_model = _final_model(response)
                final_model_group = _final_model_group(response)
                fallback_used = _fallback_used(
                    final_model_group,
                    final_model,
                    policy,
                )
                span.set_attribute("status", "success")
                span.set_attribute("fallback_used", fallback_used)
                span.set_attribute(
                    "response_type",
                    type(validated_result).__name__,
                )
                if final_model is not None:
                    span.set_attribute("final_model", final_model)

        if programming_error is not None:
            raise programming_error

        if request_error is not None:
            # Suppress the provider exception context because it can contain
            # raw model output or request payloads that outer Logfire spans
            # must not capture.
            raise LLMGatewayError(
                "Resume parsing model request failed."
            ) from None

        if validated_result is None:
            raise AssertionError(
                "Structured response validation produced no result."
            )

        return validated_result


@lru_cache(maxsize=1)
def get_llm_gateway() -> LLMGateway:
    return LLMGateway(router=get_litellm_router())
