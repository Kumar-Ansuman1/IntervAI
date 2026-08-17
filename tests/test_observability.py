from types import SimpleNamespace

from backend.app.core.observability import (
    _safe_request_attributes,
    _send_to_logfire_setting,
)


def test_safe_request_attributes_omit_request_values() -> None:
    request = SimpleNamespace(
        url=SimpleNamespace(path="/adaptive-interview/answer")
    )
    attributes = {
        "values": {
            "candidate_name": "Private name",
            "candidate_answer": "Private answer",
        },
        "errors": [],
    }

    result = _safe_request_attributes(request, attributes)

    assert result == {
        "route": "/adaptive-interview/answer",
    }
    assert "values" not in result


def test_safe_request_attributes_remove_invalid_input() -> None:
    request = SimpleNamespace(
        url=SimpleNamespace(path="/adaptive-interview/answer")
    )
    attributes = {
        "values": {},
        "errors": [
            {
                "type": "string_too_short",
                "loc": ("body", "candidate_answer"),
                "msg": "String should have at least 1 character",
                "input": "Private answer",
            }
        ],
    }

    result = _safe_request_attributes(request, attributes)

    assert result["validation_error_count"] == 1
    assert result["errors"] == [
        {
            "type": "string_too_short",
            "location": "body.candidate_answer",
            "message": "String should have at least 1 character",
        }
    ]
    assert "Private answer" not in str(result)


def test_send_to_logfire_defaults_to_token_aware_mode(
    monkeypatch,
) -> None:
    monkeypatch.delenv("LOGFIRE_SEND_TO_LOGFIRE", raising=False)

    assert _send_to_logfire_setting() == "if-token-present"


def test_send_to_logfire_supports_boolean_values(
    monkeypatch,
) -> None:
    monkeypatch.setenv("LOGFIRE_SEND_TO_LOGFIRE", "false")
    assert _send_to_logfire_setting() is False

    monkeypatch.setenv("LOGFIRE_SEND_TO_LOGFIRE", "true")
    assert _send_to_logfire_setting() is True
