from inspect import signature

from backend.app.schemas.resume import ResumeData
from backend.app.services.resume import parser


def _resume_data() -> ResumeData:
    return ResumeData(
        name="Test Candidate",
        skills=["Python"],
        tech_stack=["FastAPI"],
        projects=[],
        experience=[],
    )


class FakeGateway:
    def __init__(self, result: ResumeData) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def generate_structured(self, **kwargs) -> ResumeData:
        self.calls.append(kwargs)
        return self.result


def test_extract_resume_details_delegates_to_resume_policy(
    monkeypatch,
) -> None:
    expected = _resume_data()
    gateway = FakeGateway(expected)
    monkeypatch.setattr(
        parser,
        "extract_text_from_pdf",
        lambda _pdf_bytes: "Private resume text",
    )

    result = parser.extract_resume_details(
        b"pdf bytes",
        gateway=gateway,
    )

    assert result is expected
    assert len(gateway.calls) == 1
    assert gateway.calls[0]["task"] is parser.LLMTask.RESUME_PARSING
    assert gateway.calls[0]["response_model"] is ResumeData
    assert "Private resume text" in str(gateway.calls[0]["prompt"])


def test_extract_resume_details_keeps_one_argument_usage(
    monkeypatch,
) -> None:
    expected = _resume_data()
    gateway = FakeGateway(expected)
    monkeypatch.setattr(
        parser,
        "extract_text_from_pdf",
        lambda _pdf_bytes: "Resume text",
    )
    monkeypatch.setattr(parser, "get_llm_gateway", lambda: gateway)

    result = parser.extract_resume_details(b"pdf bytes")

    assert result is expected
    assert len(gateway.calls) == 1
    assert signature(parser.extract_resume_details).parameters[
        "gateway"
    ].default is None
