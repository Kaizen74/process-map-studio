"""Scoring the interview-only live check (P12, Eric's request 2026-09-29): his sample interview
drafted on its own. There is no answer key for it, so the checks are the guardrails that must
hold for any map (evidence verified, numbers in the source, no names, Limited signal, every step
practiced only), and the report lists the steps in order, their lanes and the flow for Eric to
judge how Claude sequenced and organised the activities. Labels and counts only, never quotes."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from tests.live.evaluation import Check, _evidence_check, _lanes, _mark, _numbers_check, steps

MIN_STEPS = 3


@dataclass
class InterviewRun:
    graph: dict[str, Any]
    segments: dict[str, dict[str, Any]]
    signal: dict[str, Any] | None
    questions: list[dict[str, Any]] = field(default_factory=list)
    rejected: dict[str, Any] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)
    format_problems: list[str] = field(default_factory=list)


def _names_found(run: InterviewRun, names: Iterable[str]) -> list[str]:
    text = " ".join(json.dumps(part) for part in (run.graph, run.questions, run.rejected))
    return sorted(
        {name for name in names if re.search(rf"\b{re.escape(name)}\b", text, re.IGNORECASE)}
    )


def evaluate(run: InterviewRun, names: Iterable[str]) -> list[Check]:
    found = steps(run.graph)
    level = (run.signal or {}).get("level")
    not_practiced = sorted({e["label"] for e in found if e["source_state"] != "practiced_only"})
    hits = _names_found(run, names)
    lanes = {e["lane_role_id"] for e in found}
    return [
        Check(
            "I1",
            "A map was drafted",
            len(found) >= MIN_STEPS,
            f"{len(found)} steps in {len(lanes)} lanes",
        ),
        _evidence_check(run.graph),
        _numbers_check(run.graph, run.segments),
        Check("I2", "Signal strength is Limited", level == "limited", f"signal: {level}"),
        Check(
            "I3",
            "Every step is practiced only",
            not not_practiced,
            f"not practiced only: {', '.join(not_practiced)}"
            if not_practiced
            else "every step rests on the interview alone",
        ),
        Check(
            "I4",
            "No names",
            not hits,
            f"found: {', '.join(hits)}"
            if hits
            else "no name in the map, questions or rejected claims",
        ),
    ]


def _flow(graph: Mapping[str, Any]) -> list[str]:
    label = {e["id"]: e["label"] for e in graph["elements"]}
    return [
        f"- {label.get(e['from'], '?')} → {label.get(e['to'], '?')}"
        + (f" ({e['label']})" if e.get("label") else "")
        for e in graph["edges"]
    ]


def render(run: InterviewRun, checks: Sequence[Check], model: str) -> str:
    """The report as Markdown: checks, then the steps in order, lanes and flow."""
    ok = all(c.passed is not False for c in checks)
    lanes = _lanes(run.graph)
    phases = {p["id"]: p["name"] for p in run.graph.get("phases", [])}
    found = steps(run.graph)
    lines = [
        "# Interview-only live check (P12)",
        "",
        f"Model: {model} · result: " + ("all checks met" if ok else "a check was missed"),
        "",
        "| Check | Result | Detail |",
        "|---|---|---|",
        *[f"| {c.code} {c.name} | {_mark(c)} | {c.detail} |" for c in checks],
        "",
        "Steps in order (label · kind · lane · phase · confidence):",
        *[
            f"{n}. {e['label']} · {e['kind']} · {lanes.get(e['lane_role_id'] or '', 'no lane')} · "
            f"{phases.get(e['phase_id'] or '', 'no phase')} · {e.get('confidence')}"
            for n, e in enumerate(found, start=1)
        ],
        "",
        "Lanes: " + ", ".join(f"{name} ({sum(1 for e in found if e['lane_role_id'] == rid)})"
                              for rid, name in lanes.items()),
        "",
        "Flow:",
        *_flow(run.graph),
        "",
        f"Validation questions: {len(run.questions)} · rejected claims: "
        f"{run.rejected.get('total', 0)}",
    ]  # fmt: skip
    unusual = [c for c in run.calls if c["status"] not in ("ok", "repaired")]
    if unusual:
        lines += ["", "AI calls that did not end normally (stage · status · output tokens):"]
        lines += [f"- {c['stage_id']} · {c['status']} · {c['output_tokens']}" for c in unusual]
    if run.format_problems:
        lines += ["", "Why answers failed the format check (field and rule only):"]
        lines += [f"- {problem}" for problem in run.format_problems]
    return "\n".join([*lines, ""])
