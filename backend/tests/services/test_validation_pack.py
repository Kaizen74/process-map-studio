"""The validation session pack (services/validation_pack.py; PRD Appendix F.7, criterion 75):
the four F.7 parts in order, the open questions, plain non-blaming wording, nothing judged."""

from __future__ import annotations

import re

from app.domain.sensemaking import PackContrast, PackStep, ValidationPackInput
from app.services import validation_pack as pack
from app.services import wording

FULL = ValidationPackInput(
    process="Load control",
    version_label="v0.1",
    steps=[PackStep(label="Draft load plan", role="Load controller"), PackStep(label="Busy wave?")],
    gaps=[("Load and return LIR", "Read report at aircraft")],
    contrasts=[
        PackContrast(step=f"Step {n}", done=f"done {n}", documented=f"doc {n}") for n in range(5)
    ],
    strengths=["Experienced controllers"],
    weaknesses=["Paper loading report"],
    questions=[("Approve load plan", "Who approves the plan?"), ("", "Which role issues it?")],
    stamp="Process Map Studio · Load control v0.1",
)

HEADINGS = [
    r"^# Validation session pack: Load control \(v0\.1\)$",
    r"^## 1\. Walk the As done view$",
    r"^## 2\. Dissent round, then assent round$",
    r"^## 3\. Contrast without evaluation$",
    r"^## 4\. Preserve / improve check$",
    r"^## Open validation questions$",
]


def test_the_four_f7_parts_in_order_then_the_open_questions() -> None:
    text = pack.render_validation_pack(FULL)
    lines = text.splitlines()
    positions = [next(i for i, x in enumerate(lines) if re.search(h, x)) for h in HEADINGS]
    assert positions == sorted(positions)
    assert "1. Draft load plan (Load controller)" in lines
    assert "2. Busy wave? (no role yet)" in lines
    assert "- Between “Load and return LIR” and “Read report at aircraft”: not described" in lines
    assert f"- Dissent: “{pack.DISSENT}”" in lines and f"- Assent: “{pack.ASSENT}”" in lines
    assert text.count("  - As done: ") == 3  # at most three contrasts
    assert f"For each, ask: “{pack.CONTRAST}”" in text
    assert "- Experienced controllers" in lines and "- Paper loading report" in lines
    assert "- **Approve load plan**: Who approves the plan?" in lines
    assert "- Which role issues it?" in lines
    assert lines[-1] == "*Process Map Studio · Load control v0.1*"
    assert wording.banned_words(text) == []


def test_empty_parts_say_so_plainly() -> None:
    text = pack.render_validation_pack(ValidationPackInput(process="Load control",
                                                           version_label="v0.2"))  # fmt: skip
    assert "The As done view has no steps yet." in text
    assert "The two views tell the same story on this map; skip this part." in text
    assert "The interviews named no strengths or weaknesses yet" in text
    assert "None open." in text
    assert "not described" not in text
