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
from app.domain.interview import (
    DocumentRow,
    FollowUp,
    GuideContext,
    GuideEdit,
    InterviewDocument,
    RoleQuestion,
    RowEdit,
    TableEdit,
)
from app.domain.result import Err, Ok
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
    "follow_ups": [
        FollowUp(question_id="F2", wording="You mentioned previously that “we wait for the fuel "
                 "figure”. How do you manage that today, and where do you see the biggest risk?"),
        FollowUp(question_id="M4.8", wording="If a new colleague had to make this call tomorrow, "
                 "what would they need to know?", about="Special loads OK?"),
        FollowUp(question_id="F6", wording="Who signs the plan when the controller is away?"),
        FollowUp(question_id="F5", wording="What happens between weighing and signing?"),
    ],
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
    assert [r.id for r in probes.rows] == ["F1", "F2", "F3", "F4", "F5", "F6", "F2", "M4.8", "F6",
                                           "F5", ""]  # fmt: skip
    assert probes.rows[9].wording == "What happens between weighing and signing?"
    thin = probes.rows[7]  # a coverage question keeps its bank ID, targets and what it is about
    assert (thin.note, thin.movement) == ("about Special loads OK?", "M4")
    assert thin.targets == bank().question("M4.8").targets
    md = templates.render_markdown(doc)
    assert "| M4.8 | If a new colleague had to make this call tomorrow, what would they need to " \
        "know? (about Special loads OK?) |" in md  # fmt: skip
    assert doc.opener[1] == "Last time we covered trigger, decisions; today I'd like to pick up " \
        "where we left off."  # fmt: skip
    practice = templates.tailor(
        bank(), PRACTICE.model_copy(update={"follow_ups": FOLLOW_UP.follow_ups})
    )
    assert "What happens between weighing" not in templates.render_markdown(practice)


def test_rule_8_blaming_words_and_hidden_names_are_never_filled_in() -> None:
    ctx = FOLLOW_UP.model_copy(update={
        "who": "Priya's team", "referrer_role": "Priya", "area": "error by the ramp",
        "follow_ups": [FollowUp(question_id="F6", wording="Why did Priya sign it?"),
                       FollowUp(question_id="F6", wording="Was it a violation?"),
                       FollowUp(question_id="M4.8", wording="What would they need to know?",
                                about="Ask Priya"),
                       FollowUp(question_id="F5", wording="What happens next?")],
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


# --- Role modules (F.4, F.8 rule 3; IG_generate, C5b) -----------------------------------------

GOOD = RoleQuestion(based_on="L3", wording="How does the Ramp team hand the report back?",
                    probes=["What passes across?"])  # fmt: skip


@pytest.mark.parametrize(
    ("question", "reason"),
    [
        (GOOD.model_copy(update={"based_on": "L6"}), "isn't based on L3, L4 or L5"),
        (GOOD.model_copy(update={"wording": "Tell me about handoffs."}), "ending with a question"),
        (GOOD.model_copy(update={"wording": "How?\nWhy?"}), "ending with a question"),
        (GOOD.model_copy(update={"wording": "x" * 300 + "?"}), "ending with a question"),
        (GOOD.model_copy(update={"probes": []}), "one to three short probes"),
        (GOOD.model_copy(update={"probes": ["a?", "b?", "c?", "d?"]}), "one to three"),
        (GOOD.model_copy(update={"probes": [" "]}), "one to three short probes"),
        (GOOD.model_copy(update={"wording": "Where was the violation at handover?"}), "blaming"),
        (GOOD.model_copy(update={"probes": ["Was it an error by the crew?"]}), "blaming"),
        (GOOD.model_copy(update={"wording": "The SOP says ten minutes. Is that right?"}),
         "what the documents say"),
        (GOOD.model_copy(update={"probes": ["What does the procedure say?"]}),
         "what the documents say"),
        (GOOD.model_copy(update={"wording": "How does Priya hand the report back?"}),
         "hidden-names list"),
    ],
)  # fmt: skip
def test_a_role_question_failing_a_check_is_left_out(question: RoleQuestion, reason: str) -> None:
    checked = templates.check_role_questions(bank(), [question, GOOD], ["Priya"])
    assert [r.wording for r in checked.kept] == [GOOD.wording]
    assert checked.kept[0].id == "RM1"
    [(_, why)] = checked.left_out
    assert reason in why


def test_kept_role_questions_are_numbered_and_carry_their_base_s_targets() -> None:
    proposed = [GOOD.model_copy(update={"based_on": b, "wording": f"Question {n} about {b}?"})
                for n, b in enumerate(["L3", "L4", "L5", "L3", "L4", "L5"])]  # fmt: skip
    proposed.insert(2, proposed[0].model_copy(update={"wording": "question 0 ABOUT l3 ?"}))
    checked = templates.check_role_questions(bank(), proposed, [])
    assert [r.id for r in checked.kept] == ["RM1", "RM2", "RM3", "RM4", "RM5"]
    assert [why for _, why in checked.left_out] == [
        "It repeats another question.", "The module already has five questions."]  # fmt: skip
    for row, base in zip(checked.kept, ["L3", "L4", "L5", "L3", "L4"], strict=True):
        assert row.targets == bank().question(base).targets
        assert (row.movement, row.priority) == ("L", "standard")
        assert row.probes == ["What passes across?"]


@pytest.mark.parametrize("kept", [0, 2, 4, 5])
def test_the_role_module_keeps_its_eight_minutes_and_the_plan_adds_up(kept: int) -> None:
    rows = templates.check_role_questions(
        bank(), [GOOD.model_copy(update={"wording": f"Question {n}?"}) for n in range(kept)], []
    ).kept
    doc = templates.with_role_module(
        templates.tailor(
            bank(), PRACTICE.model_copy(update={"interview_type": InterviewType.LANDSCAPE})
        ),
        rows,
        "" if kept else "left blank",
    )
    module = next(t for t in doc.tables if t.label.startswith(templates.ROLE_MODULE))
    assert [r.id for r in module.rows] == [r.id for r in rows] + [""] * max(0, 4 - kept)
    assert sum(units(r.minutes) for r in module.rows) == module.minutes * 2 == 16
    assert sum(p.minutes for p in doc.plan) == 60
    assert doc.generation_note == ("" if kept else "left blank")
    md = templates.render_markdown(doc)
    assert all(f"| {r.id} | {r.wording} |" in md for r in rows)
    assert "left blank" not in md  # the note is for the screen, not the file


# --- Editing a guide (C5c) -----------------------------------------------------------------


def as_edit(doc: InterviewDocument) -> GuideEdit:
    return GuideEdit(tables=[TableEdit(label=t.label, rows=[
        RowEdit(id=r.id, wording=r.wording, probes=list(r.probes), held_back=list(r.held_back))
        for r in t.rows]) for t in doc.tables])  # fmt: skip


def place(doc: InterviewDocument, question_id: str) -> tuple[int, int]:
    return next((ti, ri) for ti, t in enumerate(doc.tables) for ri, r in enumerate(t.rows)
                if r.id == question_id)  # fmt: skip


def edited(doc: InterviewDocument, ti: int, ri: int, **fields: object) -> GuideEdit:
    edit = as_edit(doc)
    row = edit.tables[ti].rows[ri]
    edit.tables[ti].rows[ri] = row.model_copy(update=fields)
    return edit


def test_unchanged_edits_change_nothing() -> None:
    doc = templates.tailor(bank(), PRACTICE)
    result = templates.apply_edits(doc, as_edit(doc), [])
    assert result == Ok((doc, []))


def test_wording_and_probes_are_edited_ids_and_minutes_kept() -> None:
    doc = templates.tailor(bank(), PRACTICE)
    ti, ri = place(doc, "M2.2")
    edit = edited(doc, ti, ri, wording="  Walk me through the last flight, step by step. ",
                  probes=["And then?", " ", "Who did that?"])  # fmt: skip
    result = templates.apply_edits(doc, edit, [])
    assert isinstance(result, Ok)
    new, changed = result.value
    row = new.tables[ti].rows[ri]
    assert (row.id, row.wording, row.probes) == (
        "M2.2",
        "Walk me through the last flight, step by step.",
        ["And then?", "Who did that?"],
    )
    assert row.targets == doc.tables[ti].rows[ri].targets and row.minutes == "3½"
    assert changed == ["M2.2"]
    assert [[r.minutes for r in t.rows] for t in new.tables] == [
        [r.minutes for r in t.rows] for t in doc.tables]  # fmt: skip


def test_own_questions_fill_blank_rows_and_can_be_emptied_again() -> None:
    doc = templates.tailor(bank(), FOLLOW_UP)
    ti, ri = next((ti, ri) for ti, t in enumerate(doc.tables) for ri, r in enumerate(t.rows)
                  if not r.id)  # fmt: skip
    first = templates.apply_edits(doc, edited(doc, ti, ri, wording="How is the new crew doing?",
                                              probes=["What helps?"]), [])  # fmt: skip
    assert isinstance(first, Ok)
    new, changed = first.value
    assert changed == ["E1"]
    row = new.tables[ti].rows[ri]
    assert (row.id, row.targets, row.minutes) == ("E1", [], doc.tables[ti].rows[ri].minutes)
    again = templates.apply_edits(new, edited(new, ti, ri, wording="", probes=[]), [])
    assert isinstance(again, Ok)
    assert again.value[0].tables[ti].rows[ri].id == "" and again.value[1] == ["E1"]


@pytest.mark.parametrize(
    ("ctx", "question_id", "fields", "field", "words"),
    [
        (PRACTICE, "M2.2", {"wording": ""}, "wording", "can't be empty"),
        (PRACTICE, "M2.2", {"id": "M9"}, "id", "keep their IDs"),
        (PRACTICE, "M2.2", {"wording": "Line one?\nLine two?"}, "wording", "one line"),
        (PRACTICE, "M2.2", {"wording": "x" * 301}, "wording", "up to 300"),
        (PRACTICE, "M2.2", {"probes": ["a", "b", "c", "d", "e", "f"]}, "probes", "Up to 5"),
        (PRACTICE, "M2.2", {"probes": ["Was it a violation?"]}, "probes[0]", "Avoid “violation”"),
        (PRACTICE, "M2.2", {"wording": "Was it non-compliance?"}, "wording", "Avoid"),
        (PRACTICE, "M2.2", {"wording": "The SOP says ten minutes. Is that so?"}, "wording",
         "Keep what the documents say for M6"),
        (PRACTICE, "M2.2", {"wording": "How does Priya do it?"}, "wording", "names to hide"),
        (PRACTICE, "M2.2", {"held_back": ["The procedure mentions it."]}, "held_back",
         "Only the probes held back"),
        (PRACTICE.model_copy(update={"interview_type": InterviewType.LANDSCAPE}), "L3",
         {"wording": "What does the procedure say about handoffs?"}, "wording", "for M6"),
    ],
)  # fmt: skip
def test_each_editing_rule_names_its_field(
    ctx: GuideContext, question_id: str, fields: dict[str, object], field: str, words: str
) -> None:
    doc = templates.tailor(bank(), ctx)
    ti, ri = place(doc, question_id)
    result = templates.apply_edits(doc, edited(doc, ti, ri, **fields), ["Priya"])
    assert isinstance(result, Err), result
    assert result.details["field"] == f"tables[{ti}].rows[{ri}].{field}"
    assert words in result.message


def test_documents_may_be_named_from_m6_on_and_in_follow_ups() -> None:
    sop = "The SOP says ten minutes. What happens in practice?"
    practice = templates.tailor(bank(), PRACTICE)
    ti, ri = place(practice, "M6.1")
    assert isinstance(templates.apply_edits(practice, edited(practice, ti, ri, wording=sop), []),
                      Ok)  # fmt: skip
    ti, ri = place(practice, "M6.5")
    held = edited(practice, ti, ri, held_back=["The procedure mentions “Weigh bags”. Where?"])
    assert isinstance(templates.apply_edits(practice, held, []), Ok)
    follow_up = templates.tailor(bank(), FOLLOW_UP)
    ti, ri = place(follow_up, "F1")
    assert isinstance(templates.apply_edits(follow_up, edited(follow_up, ti, ri, wording=sop),
                                            []), Ok)  # fmt: skip


def test_sections_and_rows_cant_be_added_moved_or_removed() -> None:
    doc = templates.tailor(bank(), PRACTICE)
    fewer = as_edit(doc)
    fewer.tables[0].rows.pop()
    swapped = as_edit(doc)
    swapped.tables[0], swapped.tables[1] = swapped.tables[1], swapped.tables[0]
    for edit in (fewer, swapped):
        result = templates.apply_edits(doc, edit, [])
        assert isinstance(result, Err) and result.details["field"] == "tables"


def test_follow_ups_take_one_of_each_kind_in_turn() -> None:
    """F.8 rule 7 (criterion 68): the few blank rows go to every source, not the first only."""

    def kind(qid: str, n: int) -> list[FollowUp]:
        return [FollowUp(question_id=qid, wording=f"{qid} question {i}?") for i in range(n)]

    mixed = templates.interleave(kind("F2", 3), kind("M2.1", 1), [], kind("F5", 2))
    assert [f.wording for f in mixed] == [
        "F2 question 0?", "M2.1 question 0?", "F5 question 0?", "F2 question 1?",
        "F5 question 1?", "F2 question 2?"]  # fmt: skip
    assert templates.interleave() == [] and templates.interleave([], []) == []
