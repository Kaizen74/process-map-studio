"""Standard interview templates (services/interview_templates.py; PRD v1.10 Appendix F.9,
acceptance criteria 77, 78 and 81): built from the question bank only, in the F.9 layout, with
minute plans that add up and wording that passes the non-blaming and anti-anchoring rules."""

from __future__ import annotations

import re
from io import BytesIO

import docx
import pytest
from docx.document import Document as DocxDocument
from docx.shared import Cm

from app.domain.enums import InterviewType
from app.domain.interview import InterviewDocument
from app.services import interview_templates as templates
from app.services import wording
from tests import sample_interview
from tests.services.test_question_bank import bank

KINDS = list(InterviewType)
TOTALS = {"landscape": 60, "practice": 60, "follow_up": 30}
CONTRAST = ("M6 ",)  # the contrast movement's table label starts with "M6 "


def units(label: str) -> int:
    """ "2" → 4, "1½" → 3, "½" → 1 (half minutes)."""
    whole = label.rstrip("½")
    return (int(whole) if whole else 0) * 2 + (1 if label.endswith("½") else 0)


@pytest.mark.parametrize(
    ("minutes", "weights", "expected"),
    [
        (10, [1, 1], [10, 10]),
        (20, [2, 2, 1], [16, 16, 8]),
        (4, [1] * 6, [2, 2, 1, 1, 1, 1]),
        (14, [1, 2, 2, 1, 1, 1], [4, 7, 7, 4, 3, 3]),
        (3, [1], [6]),
    ],
)
def test_minutes_are_shared_by_weight_in_half_minutes(
    minutes: int, weights: list[int], expected: list[int]
) -> None:
    parts = templates.share(minutes, weights)
    assert parts == expected and sum(parts) == minutes * 2 and min(parts) >= 1


@pytest.mark.parametrize(("units_", "label"), [(1, "½"), (2, "1"), (3, "1½"), (14, "7")])
def test_minute_labels(units_: int, label: str) -> None:
    assert templates.minutes_label(units_) == label


@pytest.mark.parametrize("kind", KINDS)
def test_every_question_id_is_there_with_probes_minutes_and_notes(kind: InterviewType) -> None:
    doc = templates.build(bank(), kind)
    rows = [r for t in doc.tables for r in t.rows]
    assert set(bank().template_ids(kind)) == {r.id for r in rows if r.id}
    md = templates.render_markdown(doc)
    for question_id in bank().template_ids(kind):
        line = next(x for x in md.splitlines() if x.startswith(f"| {question_id} |"))
        cells = line.split(" | ")
        assert len(cells) == 5, line  # ID · Question · Probes · Minutes · Notes
        assert cells[2] and cells[3], line  # probes ("—" when none) and minutes are filled
        assert line.endswith("|  |"), line  # an empty Notes cell to write in


@pytest.mark.parametrize("kind", KINDS)
def test_minute_plans_and_rows_add_up(kind: InterviewType) -> None:
    doc = templates.build(bank(), kind)
    assert doc.minutes == TOTALS[kind] == sum(r.minutes for r in doc.plan)
    assert [t.minutes for t in doc.tables] == [r.minutes for r in doc.plan]
    for table in doc.tables:
        timed = [r for r in table.rows if not r.signifier]
        assert sum(units(r.minutes) for r in timed) == table.minutes * 2, table.label
        assert all(r.minutes == templates.IN_STORY for r in table.rows if r.signifier)
    md = templates.render_markdown(doc)
    assert f"## Minute plan ({TOTALS[kind]} min)" in md
    assert f"| **Total** | **{TOTALS[kind]}** |" in md


def test_the_walk_through_gets_the_most_time() -> None:
    doc = templates.build(bank(), InterviewType.PRACTICE)
    m2 = next(t for t in doc.tables if t.label.startswith("M2 "))
    minutes = {r.id: r.minutes for r in m2.rows}
    assert minutes == {"M2.1": "2", "M2.2": "3½", "M2.3": "3½", "M2.4": "2", "M2.5": "1½",
                       "M2.6": "1½"}  # fmt: skip


def test_story_sections_repeat_the_signifiers_under_each_story() -> None:
    practice = templates.build(bank(), InterviewType.PRACTICE)
    stories = next(t for t in practice.tables if t.label.startswith("M5 "))
    assert [r.id for r in stories.rows] == [
        x for s in ("M5.1", "M5.2", "M5.3", "M5.4")
        for x in (s, "M5.s1", "M5.s2", "M5.s3", "M5.s4", "M5.s5")
    ]  # fmt: skip
    landscape = templates.build(bank(), InterviewType.LANDSCAPE)
    two = next(t for t in landscape.tables if t.label.startswith("Two stories"))
    assert [r.id for r in two.rows] == [
        "M5.1", "M5.s1", "M5.s2", "M5.s3", "M5.2", "M5.s1", "M5.s2", "M5.s3"
    ]  # fmt: skip


def test_blank_rows_for_the_role_module_and_reflective_probes() -> None:
    landscape = templates.build(bank(), InterviewType.LANDSCAPE)
    module = next(t for t in landscape.tables if t.label.startswith("Role module"))
    assert [r.id for r in module.rows] == ["", "", "", ""]
    assert [r.minutes for r in module.rows] == ["2", "2", "2", "2"]
    assert "questions for this stakeholder group" in module.note
    follow_up = templates.build(bank(), InterviewType.FOLLOW_UP)
    probes = next(t for t in follow_up.tables if t.label.startswith("F-series"))
    assert [r.id for r in probes.rows] == ["F1", "F2", "F3", "F4", "F5", "F6", "", "", "", "", ""]
    assert probes.rows[1].probes == [
        "Built from: Verified quotes carrying constraints, risks or stated reasons"
    ]


LAYOUT = [
    r"^# (Landscape|Practice|Follow-up) interview template$",  # 1 title
    r"^Question bank v1\.0 · Process Map Studio$",  # 1 version stamp
    r"^## Interview details$",  # 2 header table
    r"^\*\*\[RECORD THE SESSION — confirm consent\]\*\*$",  # 3 opener
    r"^## Minute plan \(\d+ min\)$",  # 4
    r"^## Interviewer principles$",  # 5
    r"^\| ID \| Question \| Probes \| Minutes \| Notes \|$",  # 6 movement tables
    r"^## Coverage checklist$",  # 7
    r"^## Close and next steps$",  # 8
    r"^\*Say or note the question ID \(e\.g\. \[M2\.2\]\) when you ask it",  # 9 footer
]


@pytest.mark.parametrize("kind", KINDS)
def test_the_markdown_follows_the_f9_layout_in_order(kind: InterviewType) -> None:
    lines = templates.render_markdown(templates.build(bank(), kind)).splitlines()
    positions = [next(i for i, x in enumerate(lines) if re.search(p, x)) for p in LAYOUT]
    assert positions == sorted(positions)
    md = "\n".join(lines)
    for field in ("Engagement / process", "Interviewee role", "Stakeholder group", "Date",
                  "Interviewer", "Referred by (role)"):  # fmt: skip
        assert f"| {field} |  |" in md
    assert "| Recording consent | ☐ |" in md
    assert md.count("- [ ] ") == 14
    assert "- Artefacts to send (three completed examples):\n" in md
    assert not [x for x in md.splitlines() if x != x.rstrip()]  # no trailing spaces
    assert "[referrer role] suggested" in md  # placeholders stay in brackets
    assert ("Last time we covered [topics]" in md) == (kind == InterviewType.FOLLOW_UP)
    assert md.count("\n1. Story before explanation.") == 1  # the ten principles, one line each


def rows_before_contrast(doc: InterviewDocument) -> str:
    return " ".join(
        f"{r.lead_in} {r.wording} {' '.join(r.probes)}"
        for t in doc.tables
        if not t.label.startswith(CONTRAST)
        for r in t.rows
    )


@pytest.mark.parametrize("kind", KINDS)
def test_no_sop_claims_before_m6_no_names_no_banned_words(kind: InterviewType) -> None:
    doc = templates.build(bank(), kind)
    md = templates.render_markdown(doc)
    before = rows_before_contrast(doc) + " " + " ".join(doc.opener)
    assert wording.sop_claims(before) == []
    assert wording.banned_words(md) == []
    names = [*sample_interview.NAMES, "Priya", "Nair"]
    assert [n for n in names if re.search(rf"\b{re.escape(n)}\b", md)] == []
    assert "Use roles, not names." in md


def test_the_contrast_movement_is_where_the_documents_come_in() -> None:
    doc = templates.build(bank(), InterviewType.PRACTICE)
    contrast = next(t for t in doc.tables if t.label.startswith("M6 "))
    text = " ".join(f"{r.lead_in} {r.wording}" for r in contrast.rows)
    assert wording.sop_claims(text)  # M6.2 and M6.5 speak about the procedure, as intended


def test_templates_are_the_same_every_time_and_built_from_the_bank_only() -> None:
    first = [templates.render_markdown(templates.build(bank(), k)) for k in KINDS]
    second = [templates.render_markdown(templates.build(bank(), k)) for k in KINDS]
    assert first == second
    # The generator's only inputs are the bank and the type: no engagement data can reach it.
    assert list(templates.build.__annotations__) == ["bank", "kind", "return"]


def test_summaries_for_the_screens() -> None:
    summaries = templates.summaries(bank())
    assert [(s.type, s.title, s.minutes) for s in summaries] == [
        ("landscape", "Landscape", 60), ("practice", "Practice", 60),
        ("follow_up", "Follow-up", 30),
    ]  # fmt: skip
    assert [sum(p.minutes for p in s.plan) for s in summaries] == [60, 60, 30]
    assert [s.question_count for s in summaries] == [16, 45, 13]
    assert {s.bank_version for s in summaries} == {"1.0"}


def test_file_names() -> None:
    assert templates.filename(InterviewType.FOLLOW_UP, "md") == "interview-template-follow-up.md"
    assert templates.filename(InterviewType.PRACTICE, "docx") == "interview-template-practice.docx"


# --- Word -------------------------------------------------------------------------------------


def reopen(kind: InterviewType) -> DocxDocument:
    data = templates.render_docx(templates.build(bank(), kind))
    assert data[:2] == b"PK"  # a Word (zip) file
    return docx.Document(BytesIO(data))


def word_text(document: DocxDocument) -> str:
    parts = [p.text for p in document.paragraphs]
    parts += [c.text for t in document.tables for r in t.rows for c in r.cells]
    return "\n".join(parts)


@pytest.mark.parametrize("kind", KINDS)
def test_the_word_file_reopens_cleanly_with_the_same_content(kind: InterviewType) -> None:
    document = reopen(kind)
    doc = templates.build(bank(), kind)
    headings = [
        p.text for p in document.paragraphs if p.style.name.startswith(("Heading", "Title"))
    ]
    assert headings == [
        doc.title, "Interview details", "Opener (F.3)", f"Minute plan ({doc.minutes} min)",
        "Interviewer principles", *[f"{t.label} ({t.minutes} min)" for t in doc.tables],
        "Coverage checklist", "Close and next steps",
    ]  # fmt: skip
    # Header table (item 2), minute plan (4) and one table per movement or section (6).
    assert len(document.tables) == 2 + len(doc.tables)
    fields = [r.cells[0].text for r in document.tables[0].rows]
    assert fields[-1] == "Recording consent" and document.tables[0].rows[-1].cells[1].text == "☐"
    plan = document.tables[1]
    assert plan.rows[-1].cells[1].text == str(doc.minutes)
    for word_table, table in zip(document.tables[2:], doc.tables, strict=True):
        assert [c.text for c in word_table.rows[0].cells] == [
            "ID", "Question", "Probes", "Minutes", "Notes"
        ]  # fmt: skip
        body = word_table.rows[1:]
        assert [r.cells[0].text for r in body] == [r.id for r in table.rows]
        assert [r.cells[3].text for r in body] == [r.minutes for r in table.rows]
        assert all(r.cells[4].text == "" for r in body)  # notes left to fill in
        assert all(r.height is not None and r.height >= Cm(1.7) for r in body)  # tall rows
    text = word_text(document)
    for question_id in bank().template_ids(kind):
        wording_ = bank().question(question_id).wording
        assert wording_ in text, question_id
    assert sum(p.text.startswith("☐ ") for p in document.paragraphs) == 14  # item 7
    assert document.paragraphs[1].text == "Question bank v1.0 · Process Map Studio"
    footer = document.sections[0].footer.paragraphs[0].text
    assert footer.startswith("Say or note the question ID (e.g. [M2.2]) when you ask it")
    assert document.sections[0].page_width > document.sections[0].page_height  # landscape
    assert wording.banned_words(text) == []
    assert document.core_properties.author == "Process Map Studio"
