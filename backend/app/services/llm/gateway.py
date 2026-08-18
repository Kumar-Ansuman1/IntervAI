from collections.abc import Callable
from functools import lru_cache
from typing import Protocol, TypeVar

import httpx
import logfire
from google.genai.errors import APIError, UnknownApiResponseError
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models import LanguageModelInput
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, ValidationError

from backend.app.services.llm.policies import (
    LLMProvider,
    LLMTask,
    ModelConfig,
    ModelPolicy,
    ModelPolicyConfigurationError,
    get_model_policy,
)


T = TypeVar("T", bound=BaseModel)

_RECOVERABLE_PROVIDER_STATUS_CODES = {
    408,
    429,
    500,
    502,
    503,
    504,
}


class LLMGatewayError(RuntimeError):
    """Safe public error for failed structured LLM requests."""


class _StructuredModel(Protocol):
    def invoke(self, input: LanguageModelInput) -> object: ...


class _ModelClient(Protocol):
    def with_structured_output(
        self,
        schema: type[BaseModel],
    ) -> _StructuredModel: ...


ModelPolicyLoader = Callable[[LLMTask], ModelPolicy]
ModelClientFactory = Callable[[ModelConfig], _ModelClient]


@lru_cache(maxsize=8)
def _get_google_model(config: ModelConfig) -> ChatGoogleGenerativeAI:
    if config.provider is not LLMProvider.GOOGLE:
        raise ModelPolicyConfigurationError(
            "Only the Google LLM provider is currently supported."
        )

    return ChatGoogleGenerativeAI(
        model=config.model_name,
        request_timeout=config.request_timeout_seconds,
        # The gateway owns fallback behavior. One SDK attempt keeps the
        # maximum at one primary call plus one optional fallback call.
        retries=1,
    )


def _get_model_client(config: ModelConfig) -> _ModelClient:
    if config.provider is LLMProvider.GOOGLE:
        return _get_google_model(config)

    raise ModelPolicyConfigurationError(
        "Only the Google LLM provider is currently supported."
    )


def _exception_chain(error: Exception):
    current: BaseException | None = error
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        yield current
        current = current.__cause__ or current.__context__


def _is_recoverable_failure(error: Exception) -> bool:
    if isinstance(
        error,
        (
            httpx.TransportError,
            OutputParserException,
            UnknownApiResponseError,
            ValidationError,
        ),
    ):
        return True

    return any(
        isinstance(cause, APIError)
        and cause.code in _RECOVERABLE_PROVIDER_STATUS_CODES
        for cause in _exception_chain(error)
    )


class LLMGateway:
    def __init__(
        self,
        *,
        policy_loader: ModelPolicyLoader = get_model_policy,
        model_factory: ModelClientFactory = _get_model_client,
    ) -> None:
        self._policy_loader = policy_loader
        self._model_factory = model_factory

    def generate_structured(
        self,
        *,
        task: LLMTask,
        prompt: LanguageModelInput,
        response_model: type[T],
    ) -> T:
        policy = self._policy_loader(task)
        attempts = [(policy.primary, False)]

        if policy.fallback is not None:
            attempts.append((policy.fallback, True))

        terminal_error: Exception | None = None

        with logfire.span(
            "llm gateway: structured request",
            task=task.value,
            response_model=response_model.__name__,
            fallback_configured=policy.fallback is not None,
        ):
            for attempt_number, (model_config, fallback_used) in enumerate(
                attempts,
                start=1,
            ):
                attempt_error: Exception | None = None
                validated_result: T | None = None

                with logfire.span(
                    "llm gateway: model attempt",
                    task=task.value,
                    provider=model_config.provider.value,
                    model_name=model_config.model_name,
                    attempt_number=attempt_number,
                    fallback_used=fallback_used,
                    status="started",
                ) as attempt_span:
                    try:
                        model = self._model_factory(model_config)
                        structured_model = model.with_structured_output(
                            response_model
                        )
                        raw_result = structured_model.invoke(prompt)
                        validated_result = response_model.model_validate(
                            raw_result
                        )
                    except Exception as error:
                        attempt_error = error
                        attempt_span.set_attribute("status", "error")
                        attempt_span.set_attribute(
                            "error_type",
                            type(error).__name__,
                        )
                    else:
                        attempt_span.set_attribute("status", "success")
                        attempt_span.set_attribute(
                            "response_type",
                            type(validated_result).__name__,
                        )

                if attempt_error is None:
                    if validated_result is None:
                        raise AssertionError(
                            "Structured model validation produced no result."
                        )
                    return validated_result

                terminal_error = attempt_error

                if not _is_recoverable_failure(attempt_error):
                    break

        raise LLMGatewayError(
            "The structured LLM request could not be completed."
        ) from terminal_error


@lru_cache(maxsize=1)
def get_llm_gateway() -> LLMGateway:
    return LLMGateway()
