from typing import Any

import httpx
import pytest

from backend.app.schemas.resume import ResumeData
from backend.app.services.llm import gateway as gateway_module
from backend.app.services.llm.gateway import LLMGateway, LLMGatewayError
from backend.app.services.llm.policies import (
    DEFAULT_RESUME_MODEL,
    LLMProvider,
    LLMTask,
    ModelConfig,
    ModelPolicy,
    ModelPolicyConfigurationError,
    get_model_policy,
)


def _resume_data() -> ResumeData:
    return ResumeData(
        name="Test Candidate",
        skills=["Python"],
        tech_stack=["FastAPI"],
        projects=[],
        experience=[],
    )


class FakeModelClient:
    def __init__(self, outcome: object | Exception) -> None:
        self.outcome = outcome
        self.invoke_count = 0
        self.response_models: list[type[ResumeData]] = []

    def with_structured_output(
        self,
        response_model: type[ResumeData],
    ) -> "FakeModelClient":
        self.response_models.append(response_model)
        return self

    def invoke(self, _prompt: object) -> object:
        self.invoke_count += 1

        if isinstance(self.outcome, Exception):
            raise self.outcome

        return self.outcome


def _gateway_with_clients(
    *,
    primary: FakeModelClient,
    fallback: FakeModelClient | None = None,
) -> LLMGateway:
    primary_config = ModelConfig(
        provider=LLMProvider.GOOGLE,
        model_name="primary-model",
    )
    fallback_config = (
        ModelConfig(
            provider=LLMProvider.GOOGLE,
            model_name="fallback-model",
        )
        if fallback is not None
        else None
    )
    policy = ModelPolicy(
        task=LLMTask.RESUME_PARSING,
        primary=primary_config,
        fallback=fallback_config,
    )
    clients = {"primary-model": primary}

    if fallback is not None:
        clients["fallback-model"] = fallback

    return LLMGateway(
        policy_loader=lambda _task: policy,
        model_factory=lambda config: clients[config.model_name],
    )


def _timeout_error(message: str = "request timed out") -> httpx.ReadTimeout:
    return httpx.ReadTimeout(
        message,
        request=httpx.Request("POST", "https://example.invalid"),
    )


def test_primary_model_succeeds_without_calling_fallback() -> None:
    expected = _resume_data()
    primary = FakeModelClient(expected)
    fallback = FakeModelClient(_resume_data())
    gateway = _gateway_with_clients(
        primary=primary,
        fallback=fallback,
    )

    result = gateway.generate_structured(
        task=LLMTask.RESUME_PARSING,
        prompt="resume prompt",
        response_model=ResumeData,
    )

    assert result == expected
    assert primary.invoke_count == 1
    assert primary.response_models == [ResumeData]
    assert fallback.invoke_count == 0


def test_recoverable_primary_failure_uses_fallback_once(
    monkeypatch,
) -> None:
    expected = _resume_data()
    primary = FakeModelClient(_timeout_error())
    fallback = FakeModelClient(expected)
    recorded_spans: list[tuple[str, dict[str, object]]] = []

    def record_span(name: str, **attributes) -> "RecordedSpan":
        recorded_spans.append((name, attributes))
        return RecordedSpan(attributes)

    monkeypatch.setattr(gateway_module.logfire, "span", record_span)
    gateway = _gateway_with_clients(
        primary=primary,
        fallback=fallback,
    )

    result = gateway.generate_structured(
        task=LLMTask.RESUME_PARSING,
        prompt="resume prompt",
        response_model=ResumeData,
    )

    assert result == expected
    assert primary.invoke_count == 1
    assert fallback.invoke_count == 1
    attempt_spans = [
        attributes
        for name, attributes in recorded_spans
        if name == "llm gateway: model attempt"
    ]
    assert attempt_spans[0]["attempt_number"] == 1
    assert attempt_spans[0]["fallback_used"] is False
    assert attempt_spans[1]["attempt_number"] == 2
    assert attempt_spans[1]["fallback_used"] is True
    assert attempt_spans[1]["status"] == "success"


def test_nonrecoverable_failure_does_not_use_fallback() -> None:
    primary = FakeModelClient(ValueError("programming error"))
    fallback = FakeModelClient(_resume_data())
    gateway = _gateway_with_clients(
        primary=primary,
        fallback=fallback,
    )

    with pytest.raises(LLMGatewayError):
        gateway.generate_structured(
            task=LLMTask.RESUME_PARSING,
            prompt="resume prompt",
            response_model=ResumeData,
        )

    assert primary.invoke_count == 1
    assert fallback.invoke_count == 0


def test_primary_and_fallback_failure_raise_safe_gateway_error() -> None:
    primary = FakeModelClient(_timeout_error("private primary payload"))
    fallback = FakeModelClient(_timeout_error("private fallback payload"))
    gateway = _gateway_with_clients(
        primary=primary,
        fallback=fallback,
    )

    with pytest.raises(LLMGatewayError) as error_info:
        gateway.generate_structured(
            task=LLMTask.RESUME_PARSING,
            prompt="private resume prompt",
            response_model=ResumeData,
        )

    assert primary.invoke_count == 1
    assert fallback.invoke_count == 1
    assert str(error_info.value) == (
        "The structured LLM request could not be completed."
    )
    assert "private" not in str(error_info.value)


def test_no_fallback_configured_makes_only_primary_attempt() -> None:
    primary = FakeModelClient(_timeout_error())
    gateway = _gateway_with_clients(primary=primary)

    with pytest.raises(LLMGatewayError):
        gateway.generate_structured(
            task=LLMTask.RESUME_PARSING,
            prompt="resume prompt",
            response_model=ResumeData,
        )

    assert primary.invoke_count == 1


def test_invalid_structured_output_is_validated_before_fallback() -> None:
    primary = FakeModelClient({"name": "Missing required fields"})
    fallback = FakeModelClient(_resume_data().model_dump())
    gateway = _gateway_with_clients(
        primary=primary,
        fallback=fallback,
    )

    result = gateway.generate_structured(
        task=LLMTask.RESUME_PARSING,
        prompt="resume prompt",
        response_model=ResumeData,
    )

    assert isinstance(result, ResumeData)
    assert primary.invoke_count == 1
    assert fallback.invoke_count == 1


def test_model_factory_reuses_client_and_configures_supported_timeout(
    monkeypatch,
) -> None:
    created_clients: list[dict[str, Any]] = []
    sentinel = object()

    def fake_google_client(**kwargs):
        created_clients.append(kwargs)
        return sentinel

    monkeypatch.setattr(
        gateway_module,
        "ChatGoogleGenerativeAI",
        fake_google_client,
    )
    gateway_module._get_google_model.cache_clear()
    config = ModelConfig(
        provider=LLMProvider.GOOGLE,
        model_name="configured-model",
        request_timeout_seconds=45.5,
    )

    try:
        first = gateway_module._get_google_model(config)
        second = gateway_module._get_google_model(config)
    finally:
        gateway_module._get_google_model.cache_clear()

    assert first is sentinel
    assert second is sentinel
    assert created_clients == [
        {
            "model": "configured-model",
            "request_timeout": 45.5,
            "retries": 1,
        }
    ]


def test_resume_policy_defaults_to_current_model_without_fallback(
    monkeypatch,
) -> None:
    monkeypatch.delenv("RESUME_PRIMARY_MODEL", raising=False)
    monkeypatch.delenv("RESUME_FALLBACK_MODEL", raising=False)
    monkeypatch.delenv("RESUME_MODEL_TIMEOUT_SECONDS", raising=False)

    policy = get_model_policy(LLMTask.RESUME_PARSING)

    assert policy.primary.model_name == DEFAULT_RESUME_MODEL
    assert policy.primary.request_timeout_seconds is None
    assert policy.fallback is None


def test_resume_policy_loads_configured_models_and_timeout(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RESUME_PRIMARY_MODEL", "primary-configured")
    monkeypatch.setenv("RESUME_FALLBACK_MODEL", "fallback-configured")
    monkeypatch.setenv("RESUME_MODEL_TIMEOUT_SECONDS", "60")

    policy = get_model_policy(LLMTask.RESUME_PARSING)

    assert policy.primary.model_name == "primary-configured"
    assert policy.primary.request_timeout_seconds == 60
    assert policy.fallback is not None
    assert policy.fallback.model_name == "fallback-configured"
    assert policy.fallback.request_timeout_seconds == 60


@pytest.mark.parametrize("invalid_timeout", ["invalid", "0", "-1", "nan"])
def test_resume_policy_rejects_invalid_timeout(
    monkeypatch,
    invalid_timeout: str,
) -> None:
    monkeypatch.setenv("RESUME_MODEL_TIMEOUT_SECONDS", invalid_timeout)

    with pytest.raises(
        ModelPolicyConfigurationError,
        match="must be a positive number",
    ):
        get_model_policy(LLMTask.RESUME_PARSING)


class RecordedSpan:
    def __init__(self, attributes: dict[str, object]) -> None:
        self.attributes = attributes

    def __enter__(self) -> "RecordedSpan":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def set_attribute(self, name: str, value: object) -> None:
        self.attributes[name] = value


def test_gateway_spans_and_public_error_do_not_expose_private_values(
    monkeypatch,
) -> None:
    private_resume = "Private Candidate private@example.com +91-9999999999"
    private_api_key = "private-api-key-value"
    recorded_spans: list[tuple[str, dict[str, object]]] = []

    def record_span(name: str, **attributes) -> RecordedSpan:
        recorded_spans.append((name, attributes))
        return RecordedSpan(attributes)

    monkeypatch.setattr(gateway_module.logfire, "span", record_span)
    primary = FakeModelClient(
        _timeout_error(f"{private_resume} {private_api_key}")
    )
    gateway = _gateway_with_clients(primary=primary)

    with pytest.raises(LLMGatewayError) as error_info:
        gateway.generate_structured(
            task=LLMTask.RESUME_PARSING,
            prompt=private_resume,
            response_model=ResumeData,
        )

    logged_metadata = repr(recorded_spans)
    assert private_resume not in logged_metadata
    assert private_api_key not in logged_metadata
    assert private_resume not in str(error_info.value)
    assert private_api_key not in str(error_info.value)
    assert recorded_spans[0] == (
        "llm gateway: structured request",
        {
            "task": "resume_parsing",
            "response_model": "ResumeData",
            "fallback_configured": False,
        },
    )
    assert recorded_spans[1][0] == "llm gateway: model attempt"
    assert recorded_spans[1][1]["attempt_number"] == 1
    assert recorded_spans[1][1]["fallback_used"] is False
    assert recorded_spans[1][1]["status"] == "error"
    assert recorded_spans[1][1]["error_type"] == "ReadTimeout"
