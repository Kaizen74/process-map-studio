"""Tailored interview guides (services/interview_templates.tailor; PRD Appendix F.8 rules 1, 2, 5,
7 and 8, F.9 layout, criterion 80): the standard template with its brackets, header and probe rows
filled in, and nothing else changed — question IDs, wording, order and minutes stay the bank's."""

from __future__ import annotations

import re
from io import BytesIO

import docx
import pytest
from docx.document import Document as DocxDocument

from app.domain.enums import InterviewType
from app.domain.interview import DocumentRow, GuideContext, InterviewDocument
from app.services import interview_templates as templates
from app.services import wording
from tests.services.test_interview_templates import LAYOUT, TOTALS, rows_before_contrast, units
from tests.services.test_question_bank import bank

PRACTICE = GuideContext(
    interview_type=InterviewType.PRACTICE,
    who="Ramp agent · Ramp",
    process="Load control",
    scope="Load control process, from Flight scheduled to Final load sheet issued",
    business="Load control",
    area="Ramp",
    referrer_role="Load controller",
    role="Ramp agent",
    stakeholder_group="Ramp",
    sop_steps=[
        "Check dangerous goods",
        "Weigh bags",
        "Sign the plan",
        "Count seats",
        "File the sheet",
        "Archive the sheet",
    ],
    hidden_terms=["Priya"],
)
FOLLOW_UP = PRACTICE.model_copy(update={
    "interview_type": InterviewType.FOLLOW_UP,
    "topics": "trigger, decisions",
    "follow_ups": [("F2", "You mentioned previously that “we wait for the fuel figure”. How do "
                          "you manage that today, and where do you see the biggest risk?"),
                   ("F6", "Who signs the plan when the controller is away?"),
                   ("F5", "What happens between weighing and signing?")],
})  # fmt: skip


def rows(doc: InterviewDocument) -> list[tuple[str, str, str]]:
    return [(r.id, r.wording, r.minutes) for t in doc.tables for r in t.rows]


def m6_row(doc: InterviewDocument) -> DocumentRow:
    contrast = next(t for t in doc.tables if t.label.startswith("M6 "))
    return next(r for r in contrast.rows if r.id == "M6.5")


def m6(doc: InterviewDocument) -> list[str]:
    """M6.5's probes as printed (the bank's, then those held back for M6)."""
    return templates.printed_probes(m6_row(doc))


def test_rule_1_and_2_the_title_header_and_opener_are_filled_in() -> None:
    doc = templates.tailor(bank(), PRACTICE)
    assert doc.kind == InterviewType.PRACTICE
    assert doc.title == "Practice interview guide: Ramp agent · Ramp"
    assert doc.header_values == {"Engagement / process": "Load control",
                                 "Interviewee role": "Ramp agent", "Stakeholder group": "Ramp",
                                 "Referred by (role)": "Load controller"}  # fmt: skip
    opener = doc.opener[0]
    assert opener.startswith("We're mapping the Load control process, from Flight scheduled to "
                             "Final load sheet issued for Load control.")  # fmt: skip
    assert "a key role in Ramp, so Load controller suggested" in opener
    assert "[" not in opener
    md = templates.render_markdown(doc)
    assert "| Interviewee role | Ramp agent |" in md
    assert "| Date |  |" in md and "| Interviewer |  |" in md  # left for the interviewer
    assert "| Recording consent | ☐ |" in md


def test_question_ids_wording_order_and_minutes_are_the_templates() -> None:
    for ctx in (PRACTICE, FOLLOW_UP):
        standard = templates.build(bank(), ctx.interview_type)
        guide = templates.tailor(bank(), ctx)
        asked = [(i, w, m) for i, w, m in rows(standard) if i]
        assert [(i, w, m) for i, w, m in rows(guide) if (i, w, m) in asked] == asked
        assert [m for _, _, m in rows(guide)] == [m for _, _, m in rows(standard)]
        assert guide.minutes == TOTALS[ctx.interview_type] == sum(p.minutes for p in guide.plan)
        for table in guide.tables:
            timed = [r for r in table.rows if not r.signifier]
            assert sum(units(r.minutes) for r in timed) == table.minutes * 2


def test_rule_5_sop_probes_only_in_m6_and_at_most_five() -> None:
    doc = templates.tailor(bank(), PRACTICE)
    standard = m6(templates.build(bank(), InterviewType.PRACTICE))
    added = m6(doc)[len(standard) :]
    assert added == [templates.SOP_PROBE.format(step=s) for s in PRACTICE.sop_steps[:5]]
    # Kept apart from the bank's probes, so the editor can show them as held back (§5.4).
    assert m6_row(doc).held_back == added
    assert m6_row(doc).probes == m6_row(templates.build(bank(), InterviewType.PRACTICE)).probes
    assert all(not r.held_back for t in doc.tables for r in t.rows if r.id != "M6.5")
    assert "Archive the sheet" not in templates.render_markdown(doc)  # the sixth is left out
    assert wording.sop_claims(rows_before_contrast(doc) + " " + " ".join(doc.opener)) == []
    assert m6(templates.tailor(bank(), PRACTICE.model_copy(update={"sop_steps": []}))) == standard


def test_rule_7_follow_up_rows_and_topics() -> None:
    doc = templates.tailor(bank(), FOLLOW_UP)
    probes = next(t for t in doc.tables if t.label.startswith("F-series"))
    assert [r.id for r in probes.rows] == ["F1", "F2", "F3", "F4", "F5", "F6", "F2", "F6", "F5",
                                           "", ""]  # fmt: skip
    assert probes.rows[8].wording == "What happens between weighing and signing?"
    assert doc.opener[1] == "Last time we covered trigger, decisions; today I'd like to pick up " \
        "where we left off."  # fmt: skip
    practice = templates.tailor(
        bank(), PRACTICE.model_copy(update={"follow_ups": FOLLOW_UP.follow_ups})
    )
    assert "What happens between weighing" not in templates.render_markdown(practice)


def test_rule_8_blaming_words_and_hidden_names_are_never_filled_in() -> None:
    ctx = FOLLOW_UP.model_copy(update={
        "who": "Priya's team", "referrer_role": "Priya", "area": "error by the ramp",
        "follow_ups": [("F6", "Why did Priya sign it?"), ("F6", "Was it a violation?"),
                       ("F5", "What happens next?")],
        "sop_steps": ["Ask Priya"],
    })  # fmt: skip
    doc = templates.tailor(bank(), ctx)
    md = templates.render_markdown(doc)
    assert "Priya" not in md and wording.banned_words(md) == []
    assert doc.title == "Follow-up interview guide"
    assert "[referrer role] suggested" in md and "[area]" in md  # left as the bracket
    assert "Referred by (role)" not in doc.header_values
    probes = next(t for t in doc.tables if t.label.startswith("F-series"))
    assert [r.wording for r in probes.rows if r.id == "F5"][-1] == "What happens next?"


def test_an_empty_context_leaves_the_brackets() -> None:
    ctx = GuideContext(interview_type=InterviewType.LANDSCAPE, who="")
    doc = templates.tailor(bank(), ctx)
    standard = templates.build(bank(), InterviewType.LANDSCAPE)
    assert doc.opener == standard.opener and doc.tables == standard.tables
    assert doc.header_values == {} and doc.title == "Landscape interview guide"


@pytest.mark.parametrize("ctx", [PRACTICE, FOLLOW_UP])
def test_the_guide_keeps_the_f9_layout_and_reopens_in_word(ctx: GuideContext) -> None:
    doc = templates.tailor(bank(), ctx)
    lines = templates.render_markdown(doc).splitlines()
    layout = [r"^# (Practice|Follow-up) interview guide: Ramp agent · Ramp$", *LAYOUT[1:]]
    positions = [next(i for i, x in enumerate(lines) if re.search(p, x)) for p in layout]
    assert positions == sorted(positions)
    word: DocxDocument = docx.Document(BytesIO(templates.render_docx(doc)))
    assert word.paragraphs[0].text == doc.title
    header = word.tables[0]
    entries = {r.cells[0].text: r.cells[1].text for r in header.rows[1:]}
    assert entries["Interviewee role"] == "Ramp agent" and entries["Date"] == ""
    text = "\n".join(c.text for t in word.tables for r in t.rows for c in r.cells)
    for question_id in bank().template_ids(ctx.interview_type):
        assert question_id in text


def test_the_standard_templates_are_unchanged() -> None:
    for kind in InterviewType:
        doc = templates.build(bank(), kind)
        assert doc.header_values == {}
        assert "| Interviewee role |  |" in templates.render_markdown(doc)


def test_guide_file_names() -> None:
    assert templates.guide_filename(InterviewType.PRACTICE, "Ramp agent", "docx") == (
        "interview-guide-practice-ramp-agent.docx")  # fmt: skip
    assert templates.guide_filename(InterviewType.FOLLOW_UP, "", "md") == (
        "interview-guide-follow-up-interviewee.md")  # fmt: skip


@pytest.mark.parametrize("ctx", [PRACTICE, FOLLOW_UP, PRACTICE.model_copy(update={
    "interview_type": InterviewType.LANDSCAPE})])  # fmt: skip
def test_every_guide_question_stores_its_movement_targets_and_priority(ctx: GuideContext) -> None:
    """F.8 rule 9 and criterion 61: what each question is for travels with it in the guide (the
    editor shows it). Probes are the bank's own: where Appendix F gives none (the framing line,
    the story prompts, M6 and M7) none are invented; generated questions must carry probes."""
    doc = templates.tailor(bank(), ctx)
    asked = [r for t in doc.tables for r in t.rows if r.id]
    assert asked
    for row in asked:
        q = bank().question(row.id)
        assert row.movement == q.movement and row.priority == q.priority, row.id
        assert row.targets and row.targets == (q.targets or [q.translation]), row.id
        bank_probes = [f"Built from: {q.built_from}"] if q.built_from else q.probes
        if row.wording == q.wording:  # a bank question (a filled-in F-series row is reworded)
            assert row.probes == bank_probes, row.id
    files = templates.render_markdown(doc)
    assert (
        "Flow (roles, lanes)" not in files and "Stated reasons; risks" not in files
    )  # not printed
