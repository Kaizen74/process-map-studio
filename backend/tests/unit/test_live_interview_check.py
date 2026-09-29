"""The interview-only live check's scoring (tests/live/interview.py; P12), run offline on a small
hand-made map: a sound map passes, and each check fails on a map crafted to miss it."""

from __future__ import annotations

import copy
from typing import Any

from tests.live import interview
from tests.live.interview import InterviewRun

NAMES = ["Pei Fen", "Steve"]
LIMITED = {"level": "limited", "label": "Limited", "score": 1, "detail": "…"}


def step(sid: str, label: str, kind: str = "activity", minutes: int | None = 10) -> dict[str, Any]:
    return {
        "id": sid, "label": label, "kind": kind, "lane_role_id": "r1", "phase_id": "p1",
        "time": {"work_min": minutes, "wait_min": None, "text": ""}, "provenance": "O",
        "source_state": "practiced_only", "confidence": 0.6,
        "evidence": [{"segment_id": f"g-{sid}", "stance": "supports", "verified": True}],
    }  # fmt: skip


def sample_run() -> InterviewRun:
    graph = {
        "roles": [{"id": "r1", "name": "Supervisor"}],
        "phases": [{"id": "p1", "name": "Assess"}],
        "elements": [
            step("a", "Print the quick scan sheet"),
            step("b", "Discuss current level", minutes=30),
            step("c", "Level met?", kind="decision", minutes=None),
        ],
        "edges": [
            {"from": "a", "to": "b", "kind": "sequence", "label": ""},
            {"from": "b", "to": "c", "kind": "sequence", "label": ""},
        ],
    }
    segments = {"g-a": {"text": "we print the sheet"}, "g-b": {"text": "about 10 or 30 minutes"}}
    return InterviewRun(
        graph=graph,
        segments=segments,
        signal=LIMITED,
        questions=[{"question": "Who keeps the sheets?"}],
        rejected={"items": [], "total": 2},
    )


def results(run: InterviewRun) -> dict[str, bool | None]:
    return {c.code: c.passed for c in interview.evaluate(run, NAMES)}


def test_a_sound_interview_only_map_meets_every_check() -> None:
    run = sample_run()
    checks = interview.evaluate(run, NAMES)
    assert all(c.passed for c in checks)
    report = interview.render(run, checks, "mocked")
    assert "result: all checks met" in report
    assert "1. Print the quick scan sheet · activity · Supervisor · Assess · 0.6" in report
    assert "- Print the quick scan sheet → Discuss current level" in report
    assert "Lanes: Supervisor (3)" in report
    assert "Validation questions: 1 · rejected claims: 2" in report


def test_each_check_fails_when_missed() -> None:
    run = copy.deepcopy(sample_run())
    run.graph["elements"] = run.graph["elements"][:2]  # too few steps
    run.graph["elements"][0]["time"]["work_min"] = 45  # no source says 45
    run.graph["elements"][1]["evidence"][0]["verified"] = False
    run.graph["elements"][1]["source_state"] = "corroborated"
    run.questions.append({"question": "Ask pei fen who signs"})
    run.signal = {**LIMITED, "level": "strong"}
    assert results(run) == {
        "I1": False, "E1": False, "E2": False, "I2": False, "I3": False, "I4": False,
    }  # fmt: skip
    checks = interview.evaluate(run, NAMES)
    detail = {c.code: c.detail for c in checks}
    assert detail["I4"] == "found: Pei Fen"
    assert detail["I3"] == "not practiced only: Discuss current level"
    assert "a check was missed" in interview.render(run, checks, "crafted")


def test_unusual_calls_and_format_problems_are_reported() -> None:
    run = sample_run()
    run.calls = [
        {"stage_id": "S1_extract_interview", "status": "ok", "output_tokens": 900},
        {"stage_id": "S4_assemble", "status": "truncated", "output_tokens": 32000},
    ]
    run.format_problems = ["S4Output: Does not match the schema: elements.0.kind: …"]
    report = interview.render(run, interview.evaluate(run, NAMES), "live")
    assert "- S4_assemble · truncated · 32000" in report
    assert "S1_extract_interview" not in report
    assert "- S4Output: Does not match the schema: elements.0.kind: …" in report
