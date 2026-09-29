"""Eric's sample interview (tests/sample_interview.py; P12): an Otter.ai export used exactly as it
is. Read into speaker turns, it makes an interview-only engagement that can be drafted at Limited
signal strength, with every person named in it hidden."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.actions.readiness import ADD_DOCUMENT
from app.config import AppConfig
from app.domain.result import Ok
from app.services import parsing
from tests import sample_interview
from tests.unit.test_draft_api import make_client, with_key


@pytest.fixture()
def client(settings_config: AppConfig) -> Iterator[TestClient]:
    for c in make_client(settings_config):
        yield with_key(c)


def test_the_sample_is_the_otter_export_as_it_was_given() -> None:
    raw = (sample_interview.FOLDER / sample_interview.FILE).read_bytes()
    assert raw.startswith(b"Speaker 1  0:06  \r\n")
    assert raw.rstrip().endswith(b"Transcribed by https://otter.ai")


def test_the_sample_is_read_into_speaker_turns() -> None:
    parsed = parsing.parse_transcript_text(sample_interview.FOLDER / sample_interview.FILE)
    assert isinstance(parsed, Ok)
    turns = parsed.value.segments
    assert len(turns) == 237
    assert Counter(t.speaker_label for t in turns) == {
        "Speaker 2": 100, "Speaker 3": 84, "Speaker 1": 30, "Speaker 5": 12,
        "Speaker 4": 8, "Speaker 6": 2, "Unknown Speaker": 1,
    }  # fmt: skip
    assert (turns[0].start_ms, turns[-1].start_ms) == (6_000, 4_915_000)  # 0:06 … 1:21:55
    assert all(t.start_ms is not None and t.text.strip() for t in turns)
    assert not any("otter.ai" in t.text for t in turns)


def test_an_interview_alone_can_be_drafted_at_limited_signal(client: TestClient) -> None:
    sample = sample_interview.build(client)
    readiness = client.get(f"/api/engagements/{sample.engagement_id}/readiness").json()
    assert readiness["transcripts_ready"] is True
    assert readiness["documents_ready"] is False
    assert readiness["speakers_unmapped"] == 0
    assert (readiness["missing"], readiness["ready_to_draft"]) == ([], True)
    assert readiness["recommended"] == [ADD_DOCUMENT]
    assert readiness["signal"]["level"] == "limited"
    assert readiness["signal"]["label"] == "Limited"


def test_no_name_in_the_sample_shows_outside_the_owner_only_places(client: TestClient) -> None:
    sample = sample_interview.build(client)
    page = client.get(f"/api/sources/{sample.source_id}/segments", params={"page_size": 500})
    text = " ".join(s["text"] for s in page.json()["segments"])
    names = re.compile(r"\b(" + "|".join(map(re.escape, sample_interview.NAMES)) + r")\b", re.I)
    assert names.findall(text) == []
    assert "[name]" in text
    speakers = client.get(f"/api/sources/{sample.source_id}/speakers").json()
    by_label = {s["label"]: s for s in speakers}
    assert by_label[sample_interview.SME]["role_id"] == sample.role_id
    assert all(by_label[label]["is_interviewer"] for label in sample_interview.OTHERS)
