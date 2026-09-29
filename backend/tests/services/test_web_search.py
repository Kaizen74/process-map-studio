"""ai_service.call_claude_with_web_search (PRD §3.11.2 step 2): the real anthropic SDK against a
fake, streaming Anthropic. Only the brief is sent; every search result and citation is captured;
a paused turn is continued; tool errors are partial results; web search switched off is a plain
error pointing to the README."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2

from app.domain.result import Err, ErrorKind, Ok
from app.services import ai_service
from app.services.ai_service import ResearchCall
from tests.services.test_call_claude import FakeAnthropic, connect

BRIEF = (
    "Process: aircraft load control. Industry: aviation ground handling. Steps: draft a load plan."
)


def research(**changes: object) -> ResearchCall:
    base: dict[str, object] = {
        "stage_id": "GB_research",
        "prompt_version": "1",
        "system": "Use only what the search results say.",
        "brief": BRIEF,
        "model": "claude-opus-5-5",
        "max_uses": 10,
        "effort": "high",
    }
    return ResearchCall(**{**base, **changes})  # type: ignore[arg-type]


def result(url: str, title: str, age: str | None = "March 2024") -> dict[str, Any]:
    return {
        "type": "web_search_result",
        "url": url,
        "title": title,
        "encrypted_content": "ENC",
        "page_age": age,
    }


def cited(text: str, url: str, title: str, quote: str) -> dict[str, Any]:
    return {
        "type": "text",
        "text": text,
        "citations": [
            {
                "type": "web_search_result_location",
                "url": url,
                "title": title,
                "encrypted_index": "IDX",
                "cited_text": quote,
            }
        ],
    }


def sse_message(blocks: list[dict[str, Any]], *, stop: str = "end_turn", searches: int = 1) -> str:
    """A streamed answer whose blocks arrive whole in their content_block_start events."""
    events: list[tuple[str, dict[str, Any]]] = [
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
                    "usage": {"input_tokens": 900, "output_tokens": 1},
                },
            },
        ),
    ]
    for i, block in enumerate(blocks):
        events.append(
            (
                "content_block_start",
                {"type": "content_block_start", "index": i, "content_block": block},
            )
        )
        events.append(("content_block_stop", {"type": "content_block_stop", "index": i}))
    events.append(
        (
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": stop, "stop_sequence": None},
                "usage": {
                    "output_tokens": 300,
                    "server_tool_use": {"web_search_requests": searches, "web_fetch_requests": 0},
                },
            },
        )
    )
    events.append(("message_stop", {"type": "message_stop"}))
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)


def answer(
    blocks: list[dict[str, Any]], **kwargs: Any
) -> Callable[[httpx2.Request], httpx2.Response]:
    return lambda _r: httpx2.Response(
        200,
        text=sse_message(blocks, **kwargs),
        headers={"content-type": "text/event-stream"},  # type: ignore[arg-type]
    )


SEARCH = {
    "type": "server_tool_use",
    "id": "srvtoolu_1",
    "name": "web_search",
    "input": {"query": "aircraft load control approvals"},
}
RESULTS = {
    "type": "web_search_tool_result",
    "tool_use_id": "srvtoolu_1",
    "content": [
        result("https://www.iata.org/ahm", "IATA Airport Handling Manual"),
        result("https://example-vendor.com/blog", "Vendor blog", None),
    ],
}


def test_sends_only_the_brief_with_the_search_tool_and_captures_everything() -> None:
    fake = FakeAnthropic(
        answer(
            [
                SEARCH,
                RESULTS,
                {"type": "text", "text": "Comparable processes include a supervisor check. "},
                cited(
                    "A second person checks the load sheet.",
                    "https://www.iata.org/ahm",
                    "IATA Airport Handling Manual",
                    "the load sheet shall be checked by a second person",
                ),
            ],
            searches=2,
        )
    )
    outcome = ai_service.call_claude_with_web_search(
        connect(fake), research(blocked_domains=("pinterest.com",))
    )
    assert isinstance(outcome, Ok), outcome
    got = outcome.value
    body = fake.body(0)
    assert body["messages"] == [{"role": "user", "content": BRIEF}]
    assert body["tools"] == [
        {
            "type": "web_search_20260318",
            "name": "web_search",
            "max_uses": 10,
            "blocked_domains": ["pinterest.com"],
        }
    ]
    assert [r.url for r in got.results] == [
        "https://www.iata.org/ahm",
        "https://example-vendor.com/blog",
    ]
    assert (got.results[0].page_age, got.results[1].page_age) == ("March 2024", "")
    assert [len(p.citations) for p in got.passages] == [0, 1]
    assert (
        got.passages[1].citations[0].cited_text
        == "the load sheet shall be checked by a second person"
    )
    assert (got.search_count, got.tool_errors, got.stop_reason) == (2, [], "end_turn")
    assert [(c.stage_id, c.status, c.input_tokens, c.output_tokens) for c in got.calls] == [
        ("GB_research", "ok", 900, 300)
    ]
    assert "ENC" not in got.model_dump_json()  # encrypted content is never kept


def test_a_paused_turn_is_continued_by_sending_the_content_back_unchanged() -> None:
    fake = FakeAnthropic(
        answer([SEARCH, RESULTS], stop="pause_turn", searches=1),
        answer(
            [
                cited(
                    "A second person checks the load sheet.",
                    "https://www.iata.org/ahm",
                    "IATA",
                    "checked by a second person",
                )
            ],
            searches=0,
        ),
    )
    outcome = ai_service.call_claude_with_web_search(connect(fake), research())
    assert isinstance(outcome, Ok), outcome
    second = fake.body(1)["messages"]
    assert isinstance(second, list) and len(second) == 2
    assert second[0] == {"role": "user", "content": BRIEF}
    assert second[1]["role"] == "assistant"
    assert [b["type"] for b in second[1]["content"]] == [
        "server_tool_use",
        "web_search_tool_result",
    ]
    assert second[1]["content"][1]["content"][0]["encrypted_content"] == "ENC"  # unchanged
    assert len(outcome.value.calls) == 2 and outcome.value.stop_reason == "end_turn"
    assert outcome.value.search_count == 1 and len(outcome.value.results) == 2


def test_a_tool_error_is_a_partial_result_not_a_crash() -> None:
    error = {
        "type": "web_search_tool_result",
        "tool_use_id": "srvtoolu_2",
        "content": {"type": "web_search_tool_result_error", "error_code": "max_uses_exceeded"},
    }
    fake = FakeAnthropic(answer([SEARCH, RESULTS, error, {"type": "text", "text": "Partial."}]))
    outcome = ai_service.call_claude_with_web_search(connect(fake), research())
    assert isinstance(outcome, Ok), outcome
    assert outcome.value.tool_errors == ["max_uses_exceeded"]
    assert len(outcome.value.results) == 2


def test_web_search_switched_off_for_the_organisation_is_a_plain_message() -> None:
    fake = FakeAnthropic(
        lambda _r: httpx2.Response(
            400,
            json={
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Web search is not enabled for this organization.",
                },
            },
            headers={"request-id": "req_9"},
        )
    )
    outcome = ai_service.call_claude_with_web_search(connect(fake), research())
    assert isinstance(outcome, Err) and outcome.code == "WEB_SEARCH_UNAVAILABLE"
    assert outcome.message == (
        "Web search isn't enabled for your Anthropic organisation. "
        "See the README, 'If something goes wrong'."
    )
    assert outcome.details["calls"][0]["status"] == "error"  # type: ignore[index]


def test_other_errors_keep_their_kind_and_both_domain_lists_are_refused() -> None:
    busy = FakeAnthropic(
        lambda _r: httpx2.Response(
            529,
            json={"type": "error", "error": {"type": "overloaded_error", "message": "busy"}},
            headers={"retry-after-ms": "1"},
        )
    )
    outcome = ai_service.call_claude_with_web_search(connect(busy), research())
    assert isinstance(outcome, Err) and outcome.kind == ErrorKind.AI_RATE_LIMIT
    both = ai_service.call_claude_with_web_search(
        connect(FakeAnthropic()),
        research(allowed_domains=("iata.org",), blocked_domains=("x.com",)),
    )
    assert isinstance(both, Err) and both.kind == ErrorKind.VALIDATION


def test_a_turn_that_keeps_pausing_stops_after_the_limit() -> None:
    fake = FakeAnthropic(answer([SEARCH, RESULTS], stop="pause_turn"))
    outcome = ai_service.call_claude_with_web_search(connect(fake), research())
    assert isinstance(outcome, Ok)
    assert len(fake.requests) == ai_service.MAX_CONTINUATIONS + 1
    assert outcome.value.stop_reason == "pause_turn"


def test_mock_mode_reads_fixtures_by_what_is_sent(tmp_path: Path) -> None:
    call = research()
    folder = tmp_path / "GB_research"
    folder.mkdir()
    message = {
        "id": "m",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [SEARCH, RESULTS],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": 1,
            "output_tokens": 1,
            "server_tool_use": {"web_search_requests": 1, "web_fetch_requests": 0},
        },
    }
    (folder / f"{ai_service.research_key(call)}.json").write_text(
        json.dumps({"responses": [message]})
    )
    outcome = ai_service.call_claude_with_web_search(connect(mock=True, fixtures=tmp_path), call)
    assert isinstance(outcome, Ok) and outcome.value.search_count == 1
    assert [c.status for c in outcome.value.calls] == ["mock"]
    (folder / "default.json").write_text(json.dumps({"error": "web_search_disabled"}))
    other = ai_service.call_claude_with_web_search(
        connect(mock=True, fixtures=tmp_path), research(brief="Another brief.")
    )
    assert isinstance(other, Err) and other.code == "WEB_SEARCH_UNAVAILABLE"
