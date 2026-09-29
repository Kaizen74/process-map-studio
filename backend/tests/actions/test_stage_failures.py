"""How a failed AI stage of the gap analyses is reported (pipeline/context.call_stage; PRD §3.7
"then a plain-language error"). Found by the first live run (P12): a cut-off or declined answer
was reported as "didn't match the expected format twice", which hid the real cause."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.domain import ai_schemas
from app.domain.result import Err, ErrorKind
from app.pipeline import context
from app.services import ai_service

CTX = context.AiContext(
    conn=ai_service.AiConnection(api_key="", mock=True, fixtures_dir=Path("x")),
    model="claude-opus-5-5",
    effort="high",
    structured_outputs=True,
    pdf_input=True,
)


def failing(message: str, **details: Any) -> Any:
    return lambda _conn, _call: Err(ErrorKind.AI_FORMAT, message, {"calls": [], **details})


@pytest.mark.parametrize(
    ("stop", "expected"),
    [
        (
            "max_tokens",
            "Claude's answer for 'Explaining the differences' was too long and was cut off. "
            "Nothing was saved. Try again, or use Copy details to report it.",
        ),
        (
            "refusal",
            "Claude declined to answer 'Explaining the differences'. Nothing was saved. "
            "Try again, or use Copy details to report it.",
        ),
        (
            None,
            "Claude's answer for 'Explaining the differences' didn't match the expected format "
            "twice. Nothing was saved. Try again, or use Copy details to report it.",
        ),
    ],
)
def test_the_failure_says_what_actually_happened(
    sessions: Any, monkeypatch: pytest.MonkeyPatch, stop: str | None, expected: str
) -> None:
    details = {"stop_reason": stop} if stop else {}
    monkeypatch.setattr(ai_service, "call_claude", failing("from the service", **details))
    result = context.call_stage(
        sessions,
        CTX,
        "GA_internal",
        "Explaining the differences",
        [{"type": "text", "text": "<divergence/>"}],
        ai_schemas.GAInternalOutput,
        None,
    )
    assert isinstance(result, Err) and result.kind is ErrorKind.AI_FORMAT
    assert result.message == expected
