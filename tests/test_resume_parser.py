import asyncio
import io
from inspect import signature

from fastapi import UploadFile

from backend.app.api.v1.routes import resumes
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


class RecordedSpan:
    def __init__(self, attributes: dict[str, object]) -> None:
        self.attributes = attributes

    def __enter__(self) -> "RecordedSpan":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def set_attribute(self, name: str, value: object) -> None:
        self.attributes[name] = value


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
    assert isinstance(gateway.calls[0]["prompt"], str)
    assert "Private resume text" in gateway.calls[0]["prompt"]


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


def test_resume_spans_do_not_receive_resume_or_prompt_text(
    monkeypatch,
) -> None:
    private_resume = "private@example.com Private Candidate"
    expected = _resume_data()
    gateway = FakeGateway(expected)
    recorded_spans: list[tuple[str, dict[str, object]]] = []

    def record_span(
        name: str,
        **attributes: object,
    ) -> RecordedSpan:
        recorded_spans.append((name, attributes))
        return RecordedSpan(attributes)

    monkeypatch.setattr(
        parser,
        "extract_text_from_pdf",
        lambda _pdf_bytes: private_resume,
    )
    monkeypatch.setattr(parser.logfire, "span", record_span)

    parser.extract_resume_details(b"pdf bytes", gateway=gateway)

    assert [name for name, _attributes in recorded_spans] == [
        "resume: prepare prompt",
        "resume: request structured parsing",
    ]
    assert private_resume not in str(recorded_spans)
    assert gateway.calls[0]["prompt"] not in str(recorded_spans)


def test_upload_resume_contract_still_returns_resume_data(
    monkeypatch,
) -> None:
    expected = _resume_data()
    monkeypatch.setattr(
        resumes.parser,
        "extract_resume_details",
        lambda pdf_bytes: expected if pdf_bytes == b"pdf bytes" else None,
    )
    upload = UploadFile(
        filename="resume.pdf",
        file=io.BytesIO(b"pdf bytes"),
    )

    result = asyncio.run(resumes.upload_resume(upload))

    assert result is expected
    assert result.model_dump() == expected.model_dump()
