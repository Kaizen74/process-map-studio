"""Interview template endpoints (API_CONTRACT.md → Interview templates; PRD v1.10 §4, F.9,
acceptance criteria 77 and 79): no engagement needed, Word and Markdown, stamped with the question
bank version."""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO

import docx
import pytest
from fastapi.testclient import TestClient

from app.config import AppConfig
from app.domain.enums import InterviewType
from app.services import interview_templates as templates
from tests.services.test_question_bank import bank
from tests.unit.test_draft_api import make_client


@pytest.fixture()
def client(settings_config: AppConfig) -> Iterator[TestClient]:
    yield from make_client(settings_config)


def test_the_plans_for_the_screens(client: TestClient) -> None:
    response = client.get("/api/templates/interview/plans")
    assert response.status_code == 200
    body = response.json()
    assert [(t["type"], t["minutes"], t["question_count"]) for t in body] == [
        ("landscape", 60, 16), ("practice", 60, 45), ("follow_up", 30, 13),
    ]  # fmt: skip
    assert [sum(p["minutes"] for p in t["plan"]) for t in body] == [60, 60, 30]
    assert body[1]["plan"][0] == {"label": "M0 — Framing", "minutes": 3}
    assert {t["bank_version"] for t in body} == {"1.0"}


@pytest.mark.parametrize("kind", list(InterviewType))
def test_markdown_downloads_with_no_engagement(client: TestClient, kind: InterviewType) -> None:
    assert client.get("/api/engagements").json() == []  # nothing set up at all
    response = client.get("/api/templates/interview", params={"type": kind, "format": "md"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/markdown; charset=utf-8"
    name = templates.filename(kind, "md")
    assert response.headers["content-disposition"] == f'attachment; filename="{name}"'
    assert response.text == templates.render_markdown(templates.build(bank(), kind))
    assert "Question bank v1.0 · Process Map Studio" in response.text


@pytest.mark.parametrize("kind", list(InterviewType))
def test_word_downloads_and_reopens(client: TestClient, kind: InterviewType) -> None:
    response = client.get("/api/templates/interview", params={"type": kind, "format": "docx"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert response.headers["content-disposition"].endswith(f'-{kind.replace("_", "-")}.docx"')
    reopened = docx.Document(BytesIO(response.content))
    assert reopened.paragraphs[0].text == templates.build(bank(), kind).title


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"type": "workshop", "format": "md"}, "Choose landscape, practice or follow_up."),
        ({"format": "md"}, "Choose landscape, practice or follow_up."),
        ({"type": "practice", "format": "pdf"}, "Choose docx or md."),
        ({"type": "practice"}, "Choose docx or md."),
    ],
)
def test_a_wrong_type_or_format_says_what_to_choose(
    client: TestClient, params: dict[str, str], message: str
) -> None:
    response = client.get("/api/templates/interview", params=params)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == message
