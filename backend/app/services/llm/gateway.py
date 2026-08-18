import logging
import os
from collections.abc import Callable, Mapping
from functools import lru_cache
from typing import TypeVar

import litellm
import logfire
from litellm import Router
from litellm.exceptions import LITELLM_EXCEPTION_TYPES
from litellm.types.router import RouterRateLimitError, RouterRateLimitErrorBasic
from pydantic import BaseModel, ValidationError

from backend.app.services.llm.policies import (
    LLMTask,
    ModelConfig,
    ModelRoutingPolicy,
    get_model_policy,
)


T = TypeVar("T", bound=BaseModel)


class LLMGatewayError(RuntimeError):
    """Safe public error for a failed structured model request."""


class LLMGatewayConfigurationError(ValueError):
    """Safe public error for invalid gateway credentials or setup."""


class _StructuredResponseError(ValueError):
    """Raised when LiteLLM returns no usable structured content."""


_REQUEST_ERRORS = tuple(LITELLM_EXCEPTION_TYPES) + (
    RouterRateLimitError,
    RouterRateLimitErrorBasic,
    ValidationError,
    _StructuredResponseError,
)


def _deployment(group: str, config: ModelConfig) -> dict[str, object]:
    params: dict[str, object] = {"model": config.model}

    if config.api_base:
        params["api_base"] = config.api_base

    if config.api_key_env:
        api_key = os.getenv(config.api_key_env, "").strip()
        if not api_key:
            raise LLMGatewayConfigurationError(
                f"{config.api_key_env} is required for the configured model."
            )
        params["api_key"] = api_key

    return {"model_name": group, "litellm_params": params}


def _configure_litellm_privacy() -> None:
    litellm.turn_off_message_logging = True
    litellm.redact_messages_in_exceptions = True
    litellm.redact_user_api_key_info = True
    logging.getLogger("LiteLLM Router").disabled = True


@lru_cache(maxsize=len(LLMTask))
def get_litellm_router(
    task: LLMTask = LLMTask.RESUME_PARSING,
) -> Router:
    _configure_litellm_privacy()
    policy = get_model_policy(task)
    model_list = [_deployment(policy.primary_group, policy.primary)]
    router_options: dict[str, object] = {
        "model_list": model_list,
        "num_retries": 0,
        "max_fallbacks": 1,
        "routing_strategy": "simple-shuffle",
        "set_verbose": False,
    }

    if policy.fallback:
        model_list.append(_deployment(policy.fallback_group, policy.fallback))
        router_options["fallbacks"] = [
            {policy.primary_group: [policy.fallback_group]}
        ]

    if policy.timeout_seconds is not None:
        router_options["timeout"] = policy.timeout_seconds

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
    policy: ModelRoutingPolicy,
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
    fallback_used = model_group == policy.fallback_group

    if model_group is None and policy.fallback and isinstance(final_model, str):
        fallback_name = policy.fallback.model.partition("/")[2]
        fallback_used = final_model in {policy.fallback.model, fallback_name}

    return final_model if isinstance(final_model, str) else None, fallback_used


class LLMGateway:
    def __init__(
        self,
        *,
        router: Router | None = None,
        policy_loader: Callable[[LLMTask], ModelRoutingPolicy] = get_model_policy,
    ) -> None:
        self._use_task_routers = router is None
        self._router = router if router is not None else get_litellm_router()
        self._policy_loader = policy_loader

    def generate_structured(
        self,
        *,
        task: LLMTask,
        prompt: str,
        response_model: type[T],
        temperature: float | None = None,
    ) -> T:
        policy = self._policy_loader(task)
        router = (
            get_litellm_router(task)
            if (
                self._use_task_routers
                and task is not LLMTask.RESUME_PARSING
            )
            else self._router
        )
        result: T | None = None
        request_failed = False

        with logfire.span(
            "litellm gateway: structured request",
            task=task.value,
            primary_model=policy.primary.model,
            fallback_configured=policy.fallback is not None,
            timeout_configured=policy.timeout_seconds is not None,
            response_model=response_model.__name__,
            status="started",
            fallback_used=False,
        ) as span:
            try:
                completion_options: dict[str, object] = {
                    "model": policy.primary_group,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": response_model,
                    "enable_json_schema_validation": True,
                    "turn_off_message_logging": True,
                    "num_retries": 0,
                }
                if temperature is not None:
                    completion_options["temperature"] = temperature

                response = router.completion(
                    **completion_options,
                )
                result = _validate_response(response, response_model)
            except _REQUEST_ERRORS as error:
                request_failed = True
                span.set_attribute("status", "error")
                span.set_attribute("error_type", type(error).__name__)
            else:
                final_model, fallback_used = _routing_result(response, policy)
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
