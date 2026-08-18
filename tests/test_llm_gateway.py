import logging
import os
from types import SimpleNamespace
from typing import Any


os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import pytest
from litellm.exceptions import APIConnectionError

from backend.app.schemas.resume import ResumeData
from backend.app.services.llm import gateway as gateway_module
from backend.app.services.llm.gateway import (
    LLMGateway,
    LLMGatewayConfigurationError,
    LLMGatewayError,
    LLMTask,
    TASK_MODELS,
    TaskModelConfig,
    get_task_model_config,
)


def _resume_data(name: str = "Test Candidate") -> ResumeData:
    return ResumeData(
        name=name,
        skills=["Python"],
        tech_stack=["FastAPI"],
        projects=[],
        experience=[],
    )


def _policy(
    *,
    fallback_model: str | None = None,
    timeout_seconds: float | None = None,
) -> TaskModelConfig:
    return TaskModelConfig(
        env_prefix="TEST_RESUME",
        primary_model="gemini/primary-model",
        fallback_model=fallback_model,
        timeout_seconds=timeout_seconds,
        primary_group="resume-primary",
        fallback_group="resume-fallback",
    )


def _response(
    content: object,
    *,
    model: str = "gemini/primary-model",
) -> SimpleNamespace:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content),
            )
        ],
        model=model,
    )
    response._hidden_params = {"litellm_model_name": model}
    return response


def _provider_error(message: str) -> APIConnectionError:
    return APIConnectionError(
        message=message,
        llm_provider="gemini",
        model="gemini/primary-model",
    )


class FakeRouter:
    def __init__(self, outcome: object | Exception) -> None:
        self.outcome = outcome
        self.calls: list[dict[str, Any]] = []

    def completion(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)

        if isinstance(self.outcome, Exception):
            raise self.outcome

        return self.outcome


class RouterOwnedFallback:
    def __init__(
        self,
        *,
        fallback_configured: bool,
        fallback_outcome: object | Exception | None = None,
    ) -> None:
        self.fallback_configured = fallback_configured
        self.fallback_outcome = fallback_outcome
        self.calls: list[dict[str, Any]] = []
        self.upstream_attempts: list[str] = []

    def completion(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        self.upstream_attempts.append("resume-primary")

        if not self.fallback_configured:
            raise _provider_error("private primary provider payload")

        self.upstream_attempts.append("resume-fallback")
        if isinstance(self.fallback_outcome, Exception):
            raise self.fallback_outcome
        if self.fallback_outcome is None:
            raise AssertionError("A fallback outcome must be configured.")

        return self.fallback_outcome


class RecordedSpan:
    def __init__(self, attributes: dict[str, object]) -> None:
        self.attributes = attributes

    def __enter__(self) -> "RecordedSpan":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def set_attribute(self, name: str, value: object) -> None:
        self.attributes[name] = value


@pytest.fixture(autouse=True)
def clear_gateway_caches():
    router_logger = logging.getLogger("LiteLLM Router")
    previous_logger_disabled = router_logger.disabled
    previous_turn_off_message_logging = (
        gateway_module.litellm.turn_off_message_logging
    )
    previous_redact_messages = (
        gateway_module.litellm.redact_messages_in_exceptions
    )
    previous_redact_api_key = (
        gateway_module.litellm.redact_user_api_key_info
    )
    gateway_module.get_llm_gateway.cache_clear()
    gateway_module.get_litellm_router.cache_clear()
    yield
    gateway_module.get_llm_gateway.cache_clear()
    gateway_module.get_litellm_router.cache_clear()
    router_logger.disabled = previous_logger_disabled
    gateway_module.litellm.turn_off_message_logging = (
        previous_turn_off_message_logging
    )
    gateway_module.litellm.redact_messages_in_exceptions = (
        previous_redact_messages
    )
    gateway_module.litellm.redact_user_api_key_info = (
        previous_redact_api_key
    )


def test_resume_policy_defaults_to_provider_prefixed_primary(
    monkeypatch,
) -> None:
    monkeypatch.delenv("RESUME_PRIMARY_MODEL", raising=False)
    monkeypatch.delenv("RESUME_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("RESUME_PRIMARY_API_BASE", raising=False)
    monkeypatch.delenv("RESUME_PRIMARY_API_KEY_ENV", raising=False)
    monkeypatch.delenv("RESUME_FALLBACK_API_BASE", raising=False)
    monkeypatch.delenv("RESUME_FALLBACK_API_KEY_ENV", raising=False)
    monkeypatch.delenv("RESUME_MODEL_TIMEOUT_SECONDS", raising=False)

    policy = get_task_model_config(LLMTask.RESUME_PARSING)

    assert policy.primary_model == TASK_MODELS[LLMTask.RESUME_PARSING].primary_model
    assert policy.primary_model == "gemini/gemini-3.5-flash"
    assert policy.primary_api_base is None
    assert policy.primary_api_key_env == "GOOGLE_API_KEY"
    assert policy.fallback_model is None
    assert policy.timeout_seconds is None
    assert policy.primary_group == "resume-primary"
    assert policy.fallback_group == "resume-fallback"


def test_empty_fallback_is_absent(monkeypatch) -> None:
    monkeypatch.setenv("RESUME_FALLBACK_MODEL", "   ")

    policy = get_task_model_config(LLMTask.RESUME_PARSING)

    assert policy.fallback_model is None


@pytest.mark.parametrize(
    "invalid_timeout",
    ["invalid", "0", "-1", "nan", "inf"],
)
def test_invalid_timeout_is_rejected(
    monkeypatch,
    invalid_timeout: str,
) -> None:
    monkeypatch.setenv(
        "RESUME_MODEL_TIMEOUT_SECONDS",
        invalid_timeout,
    )

    with pytest.raises(
        LLMGatewayConfigurationError,
        match="must be a positive number",
    ):
        get_task_model_config(LLMTask.RESUME_PARSING)


def test_model_identifiers_require_litellm_provider_syntax(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RESUME_FALLBACK_MODEL", "unprefixed-model")

    with pytest.raises(
        LLMGatewayConfigurationError,
        match="provider/model syntax",
    ):
        get_task_model_config(LLMTask.RESUME_PARSING)


def test_router_factory_builds_only_primary_without_fallback(
    monkeypatch,
    capsys,
) -> None:
    captured_kwargs: list[dict[str, object]] = []
    sentinel_router = object()
    api_key = "private-google-key"

    def fake_router(**kwargs: object) -> object:
        captured_kwargs.append(kwargs)
        return sentinel_router

    monkeypatch.setenv("GOOGLE_API_KEY", api_key)
    monkeypatch.delenv("RESUME_PRIMARY_MODEL", raising=False)
    monkeypatch.delenv("RESUME_PRIMARY_API_BASE", raising=False)
    monkeypatch.delenv("RESUME_PRIMARY_API_KEY_ENV", raising=False)
    monkeypatch.setenv("RESUME_FALLBACK_MODEL", "")
    monkeypatch.setenv("RESUME_FALLBACK_API_BASE", "")
    monkeypatch.setenv("RESUME_FALLBACK_API_KEY_ENV", "")
    monkeypatch.delenv("RESUME_MODEL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setattr(gateway_module, "Router", fake_router)

    router = gateway_module.get_litellm_router()

    assert router is sentinel_router
    assert len(captured_kwargs) == 1
    router_config = captured_kwargs[0]
    assert router_config["num_retries"] == 0
    assert router_config["max_fallbacks"] == 1
    assert router_config["routing_strategy"] == "simple-shuffle"
    assert router_config["set_verbose"] is False
    assert "fallbacks" not in router_config
    assert "timeout" not in router_config
    assert router_config["model_list"] == [
        {
            "model_name": "resume-primary",
            "litellm_params": {
                "model": "gemini/gemini-3.5-flash",
                "api_key": api_key,
            },
        }
    ]
    captured_output = capsys.readouterr()
    assert api_key not in captured_output.out
    assert api_key not in captured_output.err
    assert gateway_module.litellm.turn_off_message_logging is True
    assert gateway_module.litellm.redact_messages_in_exceptions is True
    assert gateway_module.litellm.redact_user_api_key_info is True
    assert logging.getLogger("LiteLLM Router").disabled is True


def test_router_factory_adds_optional_fallback_and_timeout(
    monkeypatch,
) -> None:
    captured_kwargs: list[dict[str, object]] = []
    sentinel_router = object()

    def fake_router(**kwargs: object) -> object:
        captured_kwargs.append(kwargs)
        return sentinel_router

    monkeypatch.setenv("GOOGLE_API_KEY", "private-google-key")
    monkeypatch.setenv("RESUME_FALLBACK_MODEL", "ollama_chat/test-model")
    monkeypatch.setenv(
        "RESUME_FALLBACK_API_BASE",
        "http://localhost:11434",
    )
    monkeypatch.setenv("RESUME_FALLBACK_API_KEY_ENV", "")
    monkeypatch.setenv("RESUME_MODEL_TIMEOUT_SECONDS", "45.5")
    monkeypatch.setattr(gateway_module, "Router", fake_router)

    gateway_module.get_litellm_router()

    router_config = captured_kwargs[0]
    assert router_config["fallbacks"] == [
        {"resume-primary": ["resume-fallback"]}
    ]
    assert router_config["timeout"] == 45.5
    assert router_config["model_list"] == [
        {
            "model_name": "resume-primary",
            "litellm_params": {
                "model": "gemini/gemini-3.5-flash",
                "api_key": "private-google-key",
            },
        },
        {
            "model_name": "resume-fallback",
            "litellm_params": {
                "model": "ollama_chat/test-model",
                "api_base": "http://localhost:11434",
            },
        },
    ]


def test_router_factory_uses_generic_credential_variable(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RESUME_PRIMARY_MODEL", "custom/test-model")
    monkeypatch.setenv("RESUME_PRIMARY_API_KEY_ENV", "CUSTOM_MODEL_KEY")
    monkeypatch.delenv("CUSTOM_MODEL_KEY", raising=False)

    with pytest.raises(
        LLMGatewayConfigurationError,
        match="CUSTOM_MODEL_KEY is required",
    ):
        gateway_module.get_litellm_router()


def test_router_factory_supports_local_model_without_api_key(
    monkeypatch,
) -> None:
    captured_kwargs: list[dict[str, object]] = []

    def fake_router(**kwargs: object) -> object:
        captured_kwargs.append(kwargs)
        return object()

    monkeypatch.setenv("RESUME_PRIMARY_MODEL", "ollama_chat/test-model")
    monkeypatch.setenv(
        "RESUME_PRIMARY_API_BASE",
        "http://localhost:11434",
    )
    monkeypatch.setenv("RESUME_PRIMARY_API_KEY_ENV", "")
    monkeypatch.setenv("RESUME_FALLBACK_MODEL", "")
    monkeypatch.setattr(gateway_module, "Router", fake_router)

    gateway_module.get_litellm_router()

    assert captured_kwargs[0]["model_list"] == [
        {
            "model_name": "resume-primary",
            "litellm_params": {
                "model": "ollama_chat/test-model",
                "api_base": "http://localhost:11434",
            },
        }
    ]


def test_structured_request_uses_litellm_messages_and_validation() -> None:
    expected = _resume_data()
    router = FakeRouter(_response(expected.model_dump_json()))
    gateway = LLMGateway(
        router=router,
        config_loader=lambda _task: _policy(),
    )

    result = gateway.generate_structured(
        task=LLMTask.RESUME_PARSING,
        prompt="resume prompt",
        response_model=ResumeData,
    )

    assert result == expected
    assert isinstance(result, ResumeData)
    assert router.calls == [
        {
            "model": "resume-primary",
            "messages": [
                {"role": "user", "content": "resume prompt"},
            ],
            "response_format": ResumeData,
            "enable_json_schema_validation": True,
            "turn_off_message_logging": True,
            "num_retries": 0,
        }
    ]


def test_dictionary_content_is_still_locally_validated() -> None:
    expected = _resume_data()
    router = FakeRouter(_response(expected.model_dump()))
    gateway = LLMGateway(
        router=router,
        config_loader=lambda _task: _policy(),
    )

    result = gateway.generate_structured(
        task=LLMTask.RESUME_PARSING,
        prompt="resume prompt",
        response_model=ResumeData,
    )

    assert result == expected
    assert isinstance(result, ResumeData)


def test_router_owned_fallback_is_bounded_to_two_attempts() -> None:
    expected = _resume_data()
    router = RouterOwnedFallback(
        fallback_configured=True,
        fallback_outcome=_response(
            expected.model_dump_json(),
            model="anthropic/fallback-model",
        ),
    )
    gateway = LLMGateway(
        router=router,
        config_loader=lambda _task: _policy(
            fallback_model="anthropic/fallback-model"
        ),
    )

    result = gateway.generate_structured(
        task=LLMTask.RESUME_PARSING,
        prompt="resume prompt",
        response_model=ResumeData,
    )

    assert result == expected
    assert router.upstream_attempts == [
        "resume-primary",
        "resume-fallback",
    ]
    assert len(router.calls) == 1


def test_litellm_router_falls_back_for_invalid_structured_output(
    monkeypatch,
) -> None:
    expected = _resume_data(name="Fallback Candidate")
    recorded_spans: list[tuple[str, dict[str, object]]] = []

    def record_span(
        name: str,
        **attributes: object,
    ) -> RecordedSpan:
        recorded_spans.append((name, attributes))
        return RecordedSpan(attributes)

    monkeypatch.setattr(gateway_module.logfire, "span", record_span)
    router = gateway_module.Router(
        model_list=[
            {
                "model_name": "resume-primary",
                "litellm_params": {
                    "model": "openai/gpt-4o-mini",
                    "api_key": "offline-test-key",
                    "mock_response": '{"name":"Incomplete"}',
                },
            },
            {
                "model_name": "resume-fallback",
                "litellm_params": {
                    "model": "openai/gpt-4o",
                    "api_key": "offline-test-key",
                    "mock_response": expected.model_dump_json(),
                },
            },
        ],
        fallbacks=[{"resume-primary": ["resume-fallback"]}],
        num_retries=0,
        max_fallbacks=1,
        routing_strategy="simple-shuffle",
        set_verbose=False,
    )
    gateway = LLMGateway(
        router=router,
        config_loader=lambda _task: TaskModelConfig(
            env_prefix="TEST_RESUME",
            primary_model="openai/gpt-4o-mini",
            fallback_model="openai/gpt-4o",
            timeout_seconds=None,
            primary_group="resume-primary",
            fallback_group="resume-fallback",
        ),
    )

    result = gateway.generate_structured(
        task=LLMTask.RESUME_PARSING,
        prompt="offline test prompt",
        response_model=ResumeData,
    )

    assert result == expected
    assert len(recorded_spans) == 1
    assert recorded_spans[0][1]["fallback_used"] is True
    assert recorded_spans[0][1]["final_model"] == "openai/gpt-4o"


def test_primary_and_fallback_failure_raise_safe_error() -> None:
    router = RouterOwnedFallback(
        fallback_configured=True,
        fallback_outcome=_provider_error(
            "private fallback provider payload"
        ),
    )
    gateway = LLMGateway(
        router=router,
        config_loader=lambda _task: _policy(
            fallback_model="anthropic/fallback-model"
        ),
    )

    with pytest.raises(LLMGatewayError) as error_info:
        gateway.generate_structured(
            task=LLMTask.RESUME_PARSING,
            prompt="private resume prompt",
            response_model=ResumeData,
        )

    assert router.upstream_attempts == [
        "resume-primary",
        "resume-fallback",
    ]
    assert str(error_info.value) == "Resume parsing model request failed."
    assert "private" not in str(error_info.value)
    assert error_info.value.__cause__ is None


def test_no_fallback_makes_only_primary_attempt() -> None:
    router = RouterOwnedFallback(fallback_configured=False)
    gateway = LLMGateway(
        router=router,
        config_loader=lambda _task: _policy(),
    )

    with pytest.raises(LLMGatewayError):
        gateway.generate_structured(
            task=LLMTask.RESUME_PARSING,
            prompt="resume prompt",
            response_model=ResumeData,
        )

    assert router.upstream_attempts == ["resume-primary"]
    assert len(router.calls) == 1


@pytest.mark.parametrize("content", [None, "", "not json"])
def test_empty_or_invalid_content_raises_safe_error(
    content: object,
) -> None:
    router = FakeRouter(_response(content))
    gateway = LLMGateway(
        router=router,
        config_loader=lambda _task: _policy(),
    )

    with pytest.raises(LLMGatewayError) as error_info:
        gateway.generate_structured(
            task=LLMTask.RESUME_PARSING,
            prompt="private resume text",
            response_model=ResumeData,
        )

    assert str(error_info.value) == "Resume parsing model request failed."
    assert "private resume text" not in str(error_info.value)


def test_invalid_dictionary_is_never_returned() -> None:
    router = FakeRouter(_response({"name": "Incomplete"}))
    gateway = LLMGateway(
        router=router,
        config_loader=lambda _task: _policy(),
    )

    with pytest.raises(LLMGatewayError):
        gateway.generate_structured(
            task=LLMTask.RESUME_PARSING,
            prompt="resume prompt",
            response_model=ResumeData,
        )


def test_gateway_logfire_span_uses_only_privacy_safe_attributes(
    monkeypatch,
) -> None:
    private_prompt = "private@example.com secret resume content"
    private_result = _resume_data(name="Private Candidate")
    api_key = "private-google-key"
    recorded_spans: list[tuple[str, dict[str, object]]] = []

    def record_span(
        name: str,
        **attributes: object,
    ) -> RecordedSpan:
        recorded_spans.append((name, attributes))
        return RecordedSpan(attributes)

    monkeypatch.setattr(gateway_module.logfire, "span", record_span)
    router = FakeRouter(_response(private_result.model_dump_json()))
    gateway = LLMGateway(
        router=router,
        config_loader=lambda _task: _policy(),
    )

    gateway.generate_structured(
        task=LLMTask.RESUME_PARSING,
        prompt=private_prompt,
        response_model=ResumeData,
    )

    assert [name for name, _attributes in recorded_spans] == [
        "litellm gateway: structured request"
    ]
    logged_attributes = str(recorded_spans[0][1])
    assert private_prompt not in logged_attributes
    assert "Private Candidate" not in logged_attributes
    assert api_key not in logged_attributes
    assert "generated result" not in logged_attributes
    assert recorded_spans[0][1]["status"] == "success"


def test_litellm_failure_logging_does_not_expose_model_content(
    capsys,
) -> None:
    private_result = "PRIVATE-CANDIDATE-MARKER"
    private_prompt = "PRIVATE-PROMPT-MARKER"
    private_api_key = "PRIVATE-API-KEY-MARKER"
    gateway_module._configure_litellm_privacy()
    router = gateway_module.Router(
        model_list=[
            {
                "model_name": "resume-primary",
                "litellm_params": {
                    "model": "openai/gpt-4o-mini",
                    "api_key": private_api_key,
                    "mock_response": (
                        f'{{"name":"{private_result}"}}'
                    ),
                },
            },
            {
                "model_name": "resume-fallback",
                "litellm_params": {
                    "model": "openai/gpt-4o",
                    "api_key": private_api_key,
                    "mock_response": (
                        f'{{"name":"{private_result}"}}'
                    ),
                },
            },
        ],
        fallbacks=[{"resume-primary": ["resume-fallback"]}],
        num_retries=0,
        max_fallbacks=1,
        routing_strategy="simple-shuffle",
        set_verbose=False,
    )
    gateway = LLMGateway(
        router=router,
        config_loader=lambda _task: TaskModelConfig(
            env_prefix="TEST_RESUME",
            primary_model="openai/gpt-4o-mini",
            fallback_model="openai/gpt-4o",
            timeout_seconds=None,
            primary_group="resume-primary",
            fallback_group="resume-fallback",
        ),
    )

    with pytest.raises(LLMGatewayError):
        gateway.generate_structured(
            task=LLMTask.RESUME_PARSING,
            prompt=private_prompt,
            response_model=ResumeData,
        )

    captured_output = capsys.readouterr()
    emitted_output = captured_output.out + captured_output.err
    assert private_result not in emitted_output
    assert private_prompt not in emitted_output
    assert private_api_key not in emitted_output


def test_gateway_factory_reuses_router_and_gateway(monkeypatch) -> None:
    sentinel_router = FakeRouter(_response(_resume_data().model_dump_json()))
    router_calls = 0

    def fake_router_factory() -> FakeRouter:
        nonlocal router_calls
        router_calls += 1
        return sentinel_router

    monkeypatch.setattr(
        gateway_module,
        "get_litellm_router",
        fake_router_factory,
    )

    first = gateway_module.get_llm_gateway()
    second = gateway_module.get_llm_gateway()

    assert first is second
    assert router_calls == 1

