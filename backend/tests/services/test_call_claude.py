"""ai_service.call_claude (PRD §3.7): the real anthropic SDK against a fake, streaming Anthropic."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest
from pydantic import BaseModel

from app.domain.result import Err, ErrorKind, Ok
from app.services import ai_service
from app.services.ai_service import AiConnection, StageCall

KEY = "sk-" + "ant-" + "api03-" + "C" * 40 + "q7w2"


class Step(BaseModel):
    label: str
    minutes: int = 0


class Answer(BaseModel):
    steps: list[Step]
    note: str = ""


GOOD = {"steps": [{"label": "Draft load plan", "minutes": 20}], "note": ""}


def sse(
    text: str, *, stop: str = "end_turn", input_tokens: int = 120, output_tokens: int = 42
) -> str:
    """The server-sent events of one streamed Messages API answer."""
    events = [
        (
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": "msg_1",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-opus-5-5",
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": input_tokens, "output_tokens": 1},
                },
            },
        ),
        (
            "content_block_start",
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "text", "text": ""},
            },
        ),
        (
            "content_block_delta",
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "text_delta", "text": text},
            },
        ),
        ("content_block_stop", {"type": "content_block_stop", "index": 0}),
        (
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop, "stop_sequence": None},
                "usage": {"output_tokens": output_tokens},
            },
        ),
        ("message_stop", {"type": "message_stop"}),
    ]
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)


class FakeAnthropic:
    def __init__(self, *answers: Callable[[httpx2.Request], httpx2.Response]) -> None:
        self.requests: list[httpx2.Request] = []
        self._answers = list(answers)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self._answers[min(len(self.requests), len(self._answers)) - 1](request)

    def body(self, index: int) -> dict[str, object]:
        return dict(json.loads(self.requests[index].content))


def stream(text: str, **kwargs: object) -> Callable[[httpx2.Request], httpx2.Response]:
    return lambda _r: httpx2.Response(
        200,
        text=sse(text, **kwargs),
        headers={"content-type": "text/event-stream"},  # type: ignore[arg-type]
    )


def status(code: int, error_type: str) -> Callable[[httpx2.Request], httpx2.Response]:
    return lambda _r: httpx2.Response(
        code,
        json={"type": "error", "error": {"type": error_type, "message": "fake"}},
        headers={"retry-after-ms": "1", "request-id": "req_9"},
    )


def connect(
    fake: FakeAnthropic | None = None, *, mock: bool = False, fixtures: Path = Path("x")
) -> AiConnection:
    client = httpx2.Client(transport=httpx2.MockTransport(fake or FakeAnthropic()))
    return AiConnection(api_key=KEY, mock=mock, fixtures_dir=fixtures, http_client=client)


BLOCKS = [
    {
        "type": "text",
        "text": '<source id="s1" kind="sop"><segment id="p1">§3.1 …</segment></source>',
    }
]


def stage(**changes: object) -> StageCall:
    base: dict[str, object] = {
        "stage_id": "S1_extract_document",
        "prompt_version": "1",
        "system": "Use only the supplied segments.",
        "blocks": BLOCKS,
        "output_model": Answer,
        "model": "claude-opus-5-5",
        "repair_prompt": "Fix the JSON so it matches the schema.",
        "effort": "high",
    }
    return StageCall(**{**base, **changes})  # type: ignore[arg-type]


def test_a_valid_answer_is_validated_and_its_usage_reported() -> None:
    fake = FakeAnthropic(stream(json.dumps(GOOD)))
    result = ai_service.call_claude(connect(fake), stage())
    assert isinstance(result, Ok)
    assert result.value.data == GOOD
    (call,) = result.value.calls
    assert (call.stage_id, call.status, call.input_tokens, call.output_tokens) == (
        "S1_extract_document",
        "ok",
        120,
        42,
    )
    assert call.input_hash == ai_service.input_hash("S1_extract_document", BLOCKS)
    body = fake.body(0)
    assert body["model"] == "claude-opus-5-5" and body["stream"] is True
    assert body["system"] == "Use only the supplied segments."
    assert body["messages"] == [{"role": "user", "content": BLOCKS}]
    config = body["output_config"]
    assert isinstance(config, dict) and config["effort"] == "high"
    assert config["format"]["type"] == "json_schema"
    assert config["format"]["schema"]["additionalProperties"] is False
    assert not {"temperature", "top_p", "thinking"} & set(body)
    assert fake.requests[0].headers["x-api-key"] == KEY and KEY not in json.dumps(body)


def test_a_malformed_answer_gets_one_repair_call() -> None:
    fake = FakeAnthropic(stream('{"steps": [{"label": 5}]'), stream(json.dumps(GOOD)))
    result = ai_service.call_claude(connect(fake), stage())
    assert isinstance(result, Ok) and result.value.data == GOOD
    assert [c.status for c in result.value.calls] == ["invalid", "repaired"]
    assert [c.stage_id for c in result.value.calls] == ["S1_extract_document", "R_repair"]
    repair = fake.body(1)
    assert repair["system"] == "Fix the JSON so it matches the schema."
    text = repair["messages"][0]["content"][0]["text"]  # type: ignore[index]
    assert "<validation_error>" in text and '{"steps": [{"label": 5}]' in text


def test_two_malformed_answers_are_a_plain_format_error() -> None:
    fake = FakeAnthropic(stream("not json"), stream('{"steps": "no"}'))
    result = ai_service.call_claude(connect(fake), stage())
    assert isinstance(result, Err) and result.kind is ErrorKind.AI_FORMAT
    assert result.message == "Claude's answer didn't match the expected format twice."
    assert [c["status"] for c in result.details["calls"]] == ["invalid", "invalid"]  # type: ignore[index, union-attr]
    assert len(fake.requests) == 2


@pytest.mark.parametrize(
    ("stop", "message", "record"),
    [
        ("refusal", "Claude declined this part of the sources.", "refused"),
        ("max_tokens", "Claude's answer was cut off before it was complete.", "truncated"),
    ],
)
def test_refusals_and_cut_off_answers_are_not_repaired(
    stop: str, message: str, record: str
) -> None:
    fake = FakeAnthropic(stream('{"steps": [', stop=stop))
    result = ai_service.call_claude(connect(fake), stage())
    assert isinstance(result, Err) and result.message == message
    assert result.details["stop_reason"] == stop
    assert [c["status"] for c in result.details["calls"]] == [record]  # type: ignore[index, union-attr]
    assert len(fake.requests) == 1


@pytest.mark.parametrize(
    ("code", "error_type", "kind", "attempts"),
    [
        (401, "authentication_error", ErrorKind.AI_AUTH, 1),
        (429, "rate_limit_error", ErrorKind.AI_RATE_LIMIT, 2),
        (529, "overloaded_error", ErrorKind.AI_RATE_LIMIT, 2),
    ],
)
def test_api_errors_retry_only_when_busy(
    code: int, error_type: str, kind: ErrorKind, attempts: int
) -> None:
    fake = FakeAnthropic(status(code, error_type))
    result = ai_service.call_claude(connect(fake), stage())
    assert isinstance(result, Err) and result.kind is kind
    assert len(fake.requests) == attempts
    assert [c["status"] for c in result.details["calls"]] == ["error"]  # type: ignore[index, union-attr]
    assert KEY not in str(result)


def test_a_failing_repair_call_keeps_both_usage_records() -> None:
    fake = FakeAnthropic(stream("not json"), status(401, "authentication_error"))
    result = ai_service.call_claude(connect(fake), stage())
    assert isinstance(result, Err) and result.kind is ErrorKind.AI_AUTH
    assert [c["status"] for c in result.details["calls"]] == ["invalid", "error"]  # type: ignore[index, union-attr]


def test_without_structured_outputs_the_schema_goes_into_the_instructions() -> None:
    fake = FakeAnthropic(stream(json.dumps(GOOD)))
    result = ai_service.call_claude(connect(fake), stage(structured_outputs=False, effort=None))
    assert isinstance(result, Ok)
    body = fake.body(0)
    assert "output_config" not in body
    assert "Return only JSON that matches this JSON schema" in str(body["system"])


def test_an_unknown_effort_level_is_not_sent() -> None:
    fake = FakeAnthropic(stream(json.dumps(GOOD)))
    ai_service.call_claude(connect(fake), stage(effort="extreme"))
    assert "effort" not in fake.body(0)["output_config"]  # type: ignore[operator]


def test_pdf_blocks_are_sent_unchanged() -> None:
    pdf = {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": "JVBERi0="},
    }
    fake = FakeAnthropic(stream(json.dumps(GOOD)))
    ai_service.call_claude(connect(fake), stage(blocks=[pdf, {"type": "text", "text": "Page 2"}]))
    assert fake.body(0)["messages"] == [
        {"role": "user", "content": [pdf, {"type": "text", "text": "Page 2"}]}
    ]


# --- Mock mode ---------------------------------------------------------------------------------


def write_fixture(root: Path, stage_id: str, key: str, data: object) -> None:
    (root / stage_id).mkdir(parents=True, exist_ok=True)
    (root / stage_id / f"{key}.json").write_text(json.dumps(data), encoding="utf-8")


def test_mock_mode_answers_from_the_fixture_named_by_the_input_hash(tmp_path: Path) -> None:
    key = ai_service.input_hash("S1_extract_document", BLOCKS)
    write_fixture(tmp_path, "S1_extract_document", key, GOOD)
    write_fixture(tmp_path, "S1_extract_document", "default", {"steps": []})
    fake = FakeAnthropic(status(500, "api_error"))
    exact = ai_service.call_claude(connect(fake, mock=True, fixtures=tmp_path), stage())
    other = ai_service.call_claude(
        connect(fake, mock=True, fixtures=tmp_path), stage(blocks=[{"type": "text", "text": "x"}])
    )
    assert isinstance(exact, Ok) and exact.value.data == GOOD
    assert exact.value.calls[0].status == "mock" and exact.value.calls[0].input_tokens == 0
    assert isinstance(other, Ok) and other.value.data == {"steps": [], "note": ""}
    assert fake.requests == []


def test_mock_mode_can_exercise_the_repair_path(tmp_path: Path) -> None:
    key = ai_service.input_hash("S1_extract_document", BLOCKS)
    write_fixture(tmp_path, "S1_extract_document", key, {"steps": "not a list"})
    write_fixture(tmp_path, "R_repair", key, GOOD)
    result = ai_service.call_claude(connect(mock=True, fixtures=tmp_path), stage())
    assert isinstance(result, Ok) and result.value.data == GOOD
    assert [c.stage_id for c in result.value.calls] == ["S1_extract_document", "R_repair"]


def test_mock_mode_without_a_fixture_is_a_plain_error(tmp_path: Path) -> None:
    result = ai_service.call_claude(connect(mock=True, fixtures=tmp_path), stage())
    assert isinstance(result, Err) and result.message == "No mock fixture for this call."


# --- Helpers -----------------------------------------------------------------------------------


def test_input_hash_depends_on_the_data_not_the_prompt_wording() -> None:
    a = ai_service.input_hash("S1_extract_document", BLOCKS)
    assert a == ai_service.input_hash("S1_extract_document", [dict(BLOCKS[0])])
    assert a != ai_service.input_hash("S1_extract_interview", BLOCKS)
    assert a != ai_service.input_hash("S1_extract_document", [{"type": "text", "text": "other"}])
    assert len(a) == 64


def test_strict_schema_inlines_references_and_closes_every_object() -> None:
    schema = ai_service.strict_schema(Answer)
    assert schema["type"] == "object" and schema["additionalProperties"] is False
    assert schema["required"] == ["steps", "note"]
    item = schema["properties"]["steps"]["items"]  # type: ignore[index]
    assert item["additionalProperties"] is False and item["required"] == ["label", "minutes"]
    assert "$ref" not in json.dumps(schema) and "$defs" not in schema
    assert '"default"' not in json.dumps(schema) and '"title"' not in json.dumps(schema)


def test_the_sdk_never_logs_the_key_even_at_debug_level(caplog: pytest.LogCaptureFixture) -> None:
    """(The SDK does log request bodies at DEBUG; the app keeps it at WARNING: test_app.py.)"""
    import logging

    caplog.set_level(logging.DEBUG)
    caplog.set_level(logging.DEBUG, logger="anthropic")
    ai_service.call_claude(connect(FakeAnthropic(stream(json.dumps(GOOD)))), stage())
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert caplog.records and KEY not in logged and KEY[-20:] not in logged
