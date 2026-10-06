"""Standard interview templates (PRD v1.10 Appendix F.9): built from the question bank only
(no AI, no engagement data), rendered as Markdown and as Word (python-docx) with the same content.

Explicit inputs (the bank and the interview type) and structured results; no files, no database.
"""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.document import Document as WordDocument
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_ROW_HEIGHT_RULE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm
from docx.table import _Cell, _Row
from pydantic import ValidationError

from app.domain.enums import InterviewType
from app.domain.interview import (
    BankQuestion,
    DocumentRow,
    DocumentTable,
    FollowUp,
    GuideContext,
    GuideEdit,
    InterviewDocument,
    QuestionBank,
    RoleModuleCheck,
    RoleQuestion,
    TemplatePlanRow,
    TemplateSection,
    TemplateSummary,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.services import grounding, wording

BANK_FILE = Path(__file__).resolve().parent.parent / "prompts" / "question_bank.json"
ORDER = (InterviewType.LANDSCAPE, InterviewType.PRACTICE, InterviewType.FOLLOW_UP)
IN_STORY = "in story"
CORE_WEIGHT = 2  # core questions (never dropped, F.8 rule 6) get twice a standard share
FORMATS = ("docx", "md")


def load_bank(path: Path = BANK_FILE) -> Result[QuestionBank]:
    """The question bank the templates are made from (a file shipped with the app)."""
    try:
        return Ok(QuestionBank.model_validate_json(path.read_text(encoding="utf-8")))
    except (OSError, ValidationError):
        return Err(ErrorKind.IO, "The interview question bank is missing or damaged in the app.")


def minutes_label(half_minutes: int) -> str:
    """3 → "1½", 4 → "2", 1 → "½"."""
    whole, half = divmod(half_minutes, 2)
    if not half:
        return str(whole)
    return f"{whole}½" if whole else "½"


def share(minutes: int, weights: list[int]) -> list[int]:
    """`minutes` shared by weight in half minutes (largest remainder); each gets at least one."""
    units = minutes * 2
    if not weights:
        return []
    total = sum(weights)
    exact = [units * w / total for w in weights]
    parts = [max(1, int(x)) for x in exact]
    by_remainder = sorted(range(len(weights)), key=lambda i: (-(exact[i] - int(exact[i])), i))
    left = units - sum(parts)
    for i in by_remainder:
        if left <= 0:
            break
        parts[i] += 1
        left -= 1
    assert sum(parts) == units, "each row needs at least half a minute"
    return parts


def _weight(bank: QuestionBank, question_id: str) -> int:
    return CORE_WEIGHT if bank.question(question_id).priority == "core" else 1


def _row(
    bank: QuestionBank, question_id: str, minutes: str, signifier: bool = False
) -> DocumentRow:
    q = bank.question(question_id)
    return DocumentRow(
        id=q.id,
        lead_in=q.lead_in,
        wording=q.wording,
        note=q.note,
        probes=[f"Built from: {q.built_from}"] if q.built_from else list(q.probes),
        minutes=minutes,
        signifier=signifier,
        movement=q.movement,
        targets=purpose(q),
        priority=q.priority,
    )


def purpose(q: BankQuestion) -> list[str]:
    """What a question is for: its targets, or for the F-series and the framing line (which the
    bank gives none) its translation, as in the F.6 table."""
    return list(q.targets) or ([q.translation] if q.translation else [])


def printed_probes(row: DocumentRow) -> list[str]:
    """The probes as printed: the bank's, then any held back for M6 (F.8 rule 5)."""
    return [*row.probes, *row.held_back]


def _table(bank: QuestionBank, section: TemplateSection) -> DocumentTable:
    asked = section.rows + section.stories
    weights = [_weight(bank, q) for q in asked] + [1] * section.blank_rows
    parts = [minutes_label(p) for p in share(section.minutes, weights)]
    rows = [_row(bank, q, parts[i]) for i, q in enumerate(section.rows)]
    for i, story in enumerate(section.stories, start=len(section.rows)):
        rows.append(_row(bank, story, parts[i]))
        rows += [_row(bank, s, IN_STORY, signifier=True) for s in section.signifiers]
    rows += [DocumentRow(minutes=p) for p in parts[len(asked) :]]
    return DocumentTable(label=section.label, minutes=section.minutes, note=section.note, rows=rows)


def build(bank: QuestionBank, kind: InterviewType) -> InterviewDocument:
    """The standard template of this type, in the F.9 layout order."""
    spec = bank.templates[kind]
    opener = [bank.opener.text]
    if kind == InterviewType.FOLLOW_UP:
        opener.append(bank.opener.follow_up)
    return InterviewDocument(
        kind=kind,
        title=f"{spec.title} interview template",
        stamp=f"Question bank v{bank.version} · Process Map Studio",
        header_fields=bank.header_fields,
        record=bank.opener.record,
        opener=opener,
        opener_note=bank.opener.note,
        minutes=spec.minutes,
        plan=[TemplatePlanRow(label=s.label, minutes=s.minutes) for s in spec.sections],
        principles=bank.principles,
        tables=[_table(bank, s) for s in spec.sections],
        coverage_checklist=bank.coverage_checklist,
        close_items=bank.close_items,
        footer=bank.footer,
    )


def summaries(bank: QuestionBank) -> list[TemplateSummary]:
    return [
        TemplateSummary(
            type=kind,
            title=bank.templates[kind].title,
            minutes=bank.templates[kind].minutes,
            who=bank.templates[kind].who,
            purpose=bank.templates[kind].purpose,
            plan=[
                TemplatePlanRow(label=s.label, minutes=s.minutes)
                for s in bank.templates[kind].sections
            ],
            question_count=len(bank.template_ids(kind)),
            bank_version=bank.version,
        )
        for kind in ORDER
    ]


def filename(kind: InterviewType, fmt: str) -> str:
    return f"interview-template-{kind.value.replace('_', '-')}.{fmt}"


# --- Markdown ---------------------------------------------------------------------------------


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def question_text(row: DocumentRow) -> str:
    """The question as printed: the cue in italics, the spoken words, the label in brackets."""
    parts = [f"*{row.lead_in}*" if row.lead_in else "", row.wording]
    text = " ".join(p for p in parts if p)
    return f"{text} ({row.note})" if row.note else text


def render_markdown(doc: InterviewDocument) -> str:
    lines = [f"# {doc.title}", "", doc.stamp, "", "## Interview details", ""]
    lines += ["| Field | Entry |", "|---|---|"]
    for field in doc.header_fields:
        entry = "☐" if field.endswith("☐") else _cell(doc.header_values.get(field, ""))
        lines.append(f"| {field.removesuffix(' ☐')} | {entry} |")
    lines += ["", "## Opener (F.3)", "", f"**{doc.record}**", ""]
    for n, paragraph in enumerate(doc.opener):
        lines += [">"] if n else []
        lines.append(f"> {paragraph}")
    lines += ["", doc.opener_note, "", f"## Minute plan ({doc.minutes} min)", ""]
    lines += ["| Section | Minutes |", "|---|---|"]
    lines += [f"| {_cell(r.label)} | {r.minutes} |" for r in doc.plan]
    lines += [f"| **Total** | **{sum(r.minutes for r in doc.plan)}** |", ""]
    lines += ["## Interviewer principles", ""]
    lines += [f"{n}. {p}" for n, p in enumerate(doc.principles, start=1)]
    for table in doc.tables:
        lines += ["", f"## {table.label} ({table.minutes} min)", ""]
        if table.note:
            lines += [table.note, ""]
        lines += ["| ID | Question | Probes | Minutes | Notes |", "|---|---|---|---|---|"]
        for row in table.rows:
            question = question_text(row)
            if row.signifier:
                question = f"↳ {question}"
            shown = printed_probes(row)
            probes = " · ".join(shown) if shown else ("—" if row.id else "")
            lines.append(f"| {row.id} | {_cell(question)} | {_cell(probes)} | {row.minutes} |  |")
    lines += ["", "## Coverage checklist", ""]
    lines += [f"- [ ] {item}" for item in doc.coverage_checklist]
    lines += ["", "## Close and next steps", ""]
    lines += [f"- {item}:" for item in doc.close_items]
    lines += ["", "---", "", f"*{doc.footer}*", ""]
    return "\n".join(lines)


# --- Word (python-docx 1.2; MIT licence) ----------------------------------------------------

# Landscape A4 with 1.5 cm margins leaves 26.7 cm: wide Question and Notes columns for writing.
COLUMNS_CM = (1.6, 8.6, 6.0, 1.7, 8.8)
HEADINGS = ("ID", "Question", "Probes", "Minutes", "Notes")
NOTES_ROW_CM = 1.8  # a tall row, so each answer has room for handwritten or typed notes


def _repeat_header(row: _Row) -> None:
    """Repeat a table's header row at the top of every page it runs onto."""
    properties = row._tr.get_or_add_trPr()
    header = OxmlElement("w:tblHeader")
    header.set(qn("w:val"), "true")
    properties.append(header)


def _cell_text(cell: _Cell, text: str, *, bold: bool = False, italic_prefix: str = "") -> None:
    paragraph = cell.paragraphs[0]
    if italic_prefix:
        paragraph.add_run(f"{italic_prefix} ").italic = True
    run = paragraph.add_run(text)
    run.bold = bold


def _question_table(doc: WordDocument, table: DocumentTable) -> None:
    grid = doc.add_table(rows=1, cols=len(COLUMNS_CM))
    grid.style = "Table Grid"
    grid.autofit = False
    for cell, heading in zip(grid.rows[0].cells, HEADINGS, strict=True):
        _cell_text(cell, heading, bold=True)
    _repeat_header(grid.rows[0])
    for row in table.rows:
        cells = grid.add_row().cells
        cells[0].text = row.id
        question = f"↳ {row.wording}" if row.signifier else row.wording
        if row.note:
            question = f"{question} ({row.note})"
        _cell_text(cells[1], question, italic_prefix=row.lead_in)
        probes = printed_probes(row) or (["—"] if row.id else [])
        cells[2].text = "\n".join(probes)
        cells[3].text = row.minutes
        grid.rows[-1].height = Cm(NOTES_ROW_CM)
        grid.rows[-1].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    for r in grid.rows:
        for cell, width in zip(r.cells, COLUMNS_CM, strict=True):
            cell.width = Cm(width)


def render_docx(doc: InterviewDocument) -> bytes:
    """The same content as the Markdown, laid out for Word (editable), footer on every page."""
    word = Document()
    section = word.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Cm(29.7), Cm(21.0)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Cm(1.5))
    section.footer.paragraphs[0].text = doc.footer  # item 9, on every page
    section.footer.paragraphs[0].runs[0].italic = True
    properties = word.core_properties
    properties.title, properties.author = doc.title, "Process Map Studio"
    properties.comments = doc.stamp

    word.add_heading(doc.title, level=0)  # item 1
    word.add_paragraph(doc.stamp)
    word.add_heading("Interview details", level=1)  # item 2
    header = word.add_table(rows=0, cols=2)
    header.style = "Table Grid"
    for field in doc.header_fields:
        cells = header.add_row().cells
        _cell_text(cells[0], field.removesuffix(" ☐"), bold=True)
        cells[1].text = "☐" if field.endswith("☐") else doc.header_values.get(field, "")
    word.add_heading("Opener (F.3)", level=1)  # item 3
    word.add_paragraph().add_run(doc.record).bold = True
    for paragraph in doc.opener:
        word.add_paragraph(paragraph, style="Quote")
    word.add_paragraph(doc.opener_note)
    word.add_heading(f"Minute plan ({doc.minutes} min)", level=1)  # item 4
    plan = word.add_table(rows=1, cols=2)
    plan.style = "Table Grid"
    _cell_text(plan.rows[0].cells[0], "Section", bold=True)
    _cell_text(plan.rows[0].cells[1], "Minutes", bold=True)
    for item in doc.plan:
        cells = plan.add_row().cells
        cells[0].text, cells[1].text = item.label, str(item.minutes)
    total = plan.add_row().cells
    _cell_text(total[0], "Total", bold=True)
    _cell_text(total[1], str(sum(item.minutes for item in doc.plan)), bold=True)
    word.add_heading("Interviewer principles", level=1)  # item 5
    for principle in doc.principles:
        word.add_paragraph(principle, style="List Number")
    for table in doc.tables:  # item 6
        word.add_heading(f"{table.label} ({table.minutes} min)", level=1)
        if table.note:
            word.add_paragraph(table.note)
        _question_table(word, table)
    word.add_heading("Coverage checklist", level=1)  # item 7
    for check in doc.coverage_checklist:
        word.add_paragraph(f"☐ {check}")
    word.add_heading("Close and next steps", level=1)  # item 8
    for close in doc.close_items:
        word.add_paragraph(f"{close}:")
    out = BytesIO()
    word.save(out)
    return out.getvalue()


# --- Tailored guides (F.8 rules 1, 2, 5, 7; G1): the template, filled in --------------------

MAX_SOP_PROBES = 5  # F.8 rule 5
SOP_PROBE = "The procedure mentions “{step}”. Where does that happen in practice?"
FILLED_HEADER = ("Engagement / process", "Interviewee role", "Stakeholder group",
                 "Referred by (role)")  # fmt: skip


def _safe(text: str, hidden: list[str]) -> bool:
    """Plain, non-blaming and without a hidden name (F.8 rule 8)."""
    return bool(text.strip()) and not wording.banned_words(text) and not (
        grounding.scan_redaction_terms(text, hidden))  # fmt: skip


def _fill(text: str, bracket: str, value: str, hidden: list[str]) -> str:
    return text.replace(bracket, value) if _safe(value, hidden) else text


def tailor(bank: QuestionBank, ctx: GuideContext) -> InterviewDocument:
    """The standard template of the profile's type with its brackets, header and probe rows filled
    in from the engagement; question IDs, wording, order and minutes stay the bank's."""
    doc = build(bank, ctx.interview_type)
    hidden = ctx.hidden_terms
    values = dict(zip(FILLED_HEADER, (ctx.process, ctx.role, ctx.stakeholder_group,
                                      ctx.referrer_role), strict=True))  # fmt: skip
    header = {k: v for k, v in values.items() if _safe(v, hidden)}
    opener = []
    for paragraph in doc.opener:
        text = paragraph
        scope = re.search(r"\[end-to-end scope[^\]]*\]", text)
        if scope:
            text = _fill(text, scope.group(0), ctx.scope, hidden)
        text = _fill(text, "[business]", ctx.business, hidden)
        text = _fill(text, "[area]", ctx.area, hidden)
        text = _fill(text, "[referrer role]", ctx.referrer_role, hidden)
        text = _fill(text, "[topics]", ctx.topics, hidden)
        opener.append(text)
    tables = [_tailored_table(bank, t, ctx, hidden) for t in doc.tables]
    spec = bank.templates[ctx.interview_type]
    title = f"{spec.title} interview guide" + (f": {ctx.who}" if _safe(ctx.who, hidden) else "")
    return doc.model_copy(update={"title": title, "header_values": header, "opener": opener,
                                  "tables": tables})  # fmt: skip


def _tailored_table(
    bank: QuestionBank, table: DocumentTable, ctx: GuideContext, hidden: list[str]
) -> DocumentTable:
    rows = []
    sop = [SOP_PROBE.format(step=s) for s in ctx.sop_steps if _safe(s, hidden)][:MAX_SOP_PROBES]
    follow_ups = [
        f
        for f in ctx.follow_ups
        if _safe(f.wording, hidden) and (not f.about or _safe(f.about, hidden))
    ]
    for row in table.rows:
        if row.id == "M6.5" and sop:  # rule 5: only in M6, where the documents come in
            row = row.model_copy(update={"held_back": sop})
        elif not row.id and ctx.interview_type == InterviewType.FOLLOW_UP and follow_ups:
            follow_up = follow_ups.pop(0)  # rule 7: the blank reflective-probe rows, in order
            qid, text = follow_up.question_id, follow_up.wording
            q = bank.question(qid)
            row = row.model_copy(
                update={
                    "id": qid,
                    "wording": text,
                    "movement": q.movement,
                    "note": f"about {follow_up.about}" if follow_up.about else "",
                    "targets": purpose(q),
                    "priority": q.priority,
                }
            )
        rows.append(row)
    return table.model_copy(update={"rows": rows})


def guide_filename(kind: InterviewType, who: str, fmt: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", who.lower()).strip("-") or "interviewee"
    return f"interview-guide-{kind.value.replace('_', '-')}-{slug}.{fmt}"


# --- Role modules (F.4, F.8 rule 3; IG_generate, C5b): Claude's questions, checked here ---------

ROLE_MODULE = "Role module"  # the Landscape table whose blank rows the module fills
ROLE_BASES = ("L3", "L4", "L5")
MAX_ROLE_QUESTIONS = 5
MAX_QUESTION = 300
MAX_PROBE = 200


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _role_problem(q: RoleQuestion, hidden: list[str], seen: set[str]) -> str:
    """Why a proposed role-module question can't be used (plain words), or "" if it can."""
    if q.based_on not in ROLE_BASES:
        return "It isn't based on L3, L4 or L5."
    text = q.wording.strip()
    if not text or "\n" in text or len(text) > MAX_QUESTION or not text.endswith("?"):
        return "It isn't one plain question ending with a question mark."
    probes = [p.strip() for p in q.probes]
    if not 1 <= len(probes) <= 3 or any(not p or "\n" in p or len(p) > MAX_PROBE for p in probes):
        return "It needs one to three short probes."
    every = " ".join([text, *probes])
    if wording.banned_words(every):
        return "It uses a blaming word."
    if wording.sop_claims(every):
        return "It says what the documents say (that waits for M6)."
    if grounding.scan_redaction_terms(every, hidden):
        return "It contains a name from the hidden-names list."
    if _key(text) in seen:
        return "It repeats another question."
    return ""


def check_role_questions(
    bank: QuestionBank, proposed: list[RoleQuestion], hidden: list[str]
) -> RoleModuleCheck:
    """The proposed questions that pass every check, as guide rows `RM1`… (at most five, in the
    order proposed), each with the targets of the L-question it is based on; and the others with
    the reason they were left out."""
    kept: list[DocumentRow] = []
    left_out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for q in proposed:
        reason = _role_problem(q, hidden, seen)
        if not reason and len(kept) == MAX_ROLE_QUESTIONS:
            reason = "The module already has five questions."
        if reason:
            left_out.append((q.wording, reason))
            continue
        seen.add(_key(q.wording))
        base = bank.question(q.based_on)
        kept.append(DocumentRow(
            id=f"RM{len(kept) + 1}", wording=q.wording.strip(),
            probes=[p.strip() for p in q.probes], minutes="", movement=base.movement,
            targets=purpose(base), priority="standard",
        ))  # fmt: skip
    return RoleModuleCheck(kept=kept, left_out=left_out)


def with_role_module(
    doc: InterviewDocument, rows: list[DocumentRow], note: str = ""
) -> InterviewDocument:
    """The role-module table with these questions first, then blank rows up to the template's
    count; the module's minutes shared among its rows (the plan still adds up)."""
    tables = []
    for table in doc.tables:
        if table.label.startswith(ROLE_MODULE):
            blanks = max(0, len(table.rows) - len(rows))
            every = [*rows, *(DocumentRow(minutes="") for _ in range(blanks))]
            parts = [minutes_label(p) for p in share(table.minutes, [1] * len(every))]
            every = [r.model_copy(update={"minutes": m}) for r, m in zip(every, parts, strict=True)]
            table = table.model_copy(update={"rows": every})
        tables.append(table)
    return doc.model_copy(update={"tables": tables, "generation_note": note})


# --- Editing a guide (C5c; PRD §5.4 Guide tab, F.8 rules 6 and 8) -----------------------------

CONTRAST = "M6 "  # the Practice movement where the documents come in
MAX_PROBES = 5
OWN = re.compile(r"E\d+")  # questions Eric writes into blank rows: E1, E2, …


def _sop_allowed(doc: InterviewDocument, table_index: int) -> bool:
    """Claims about what the documents say: from M6 on in a Practice guide, never in a Landscape
    guide; a Follow-up builds on them (F.8 rules 5, 7 and 8)."""
    if doc.kind == InterviewType.FOLLOW_UP:
        return True
    first = next((i for i, t in enumerate(doc.tables) if t.label.startswith(CONTRAST)), None)
    return first is not None and table_index >= first


def _text_problem(text: str, limit: int, hidden: list[str], sop_ok: bool) -> str:
    if "\n" in text or len(text) > limit:
        return f"Keep it to one line of up to {limit} characters."
    if found := wording.banned_words(text):
        return (f"Avoid “{found[0]}”: describe what happens instead (for example an adaptation, "
                "a workaround or a rule that no longer fits).")  # fmt: skip
    if not sop_ok and wording.sop_claims(text):
        return ("Keep what the documents say for M6, after the interviewee has described the work "
                "in their own words.")  # fmt: skip
    if grounding.scan_redaction_terms(text, hidden):
        return "This contains a name from your list of names to hide. Use the role instead."
    return ""


def apply_edits(
    doc: InterviewDocument, edit: GuideEdit, hidden: list[str]
) -> Result[tuple[InterviewDocument, list[str]]]:
    """The guide with Eric's wording and probes, and the IDs of the questions he changed; or the
    first problem, naming its field. Sections, rows, IDs and minutes stay as they are."""

    def invalid(field: str, message: str) -> Err:
        return Err(ErrorKind.VALIDATION, message, {"field": field})

    if [t.label for t in edit.tables] != [t.label for t in doc.tables] or any(
        len(e.rows) != len(t.rows) for e, t in zip(edit.tables, doc.tables, strict=True)
    ):
        return invalid("tables", "The guide's sections and rows can't be added, moved or removed.")
    own = max((int(r.id[1:]) for t in doc.tables for r in t.rows if OWN.fullmatch(r.id)), default=0)
    changed: list[str] = []
    tables = []
    for ti, (table, edited) in enumerate(zip(doc.tables, edit.tables, strict=True)):
        sop_ok = _sop_allowed(doc, ti)
        rows = []
        for ri, (row, new) in enumerate(zip(table.rows, edited.rows, strict=True)):
            at = f"tables[{ti}].rows[{ri}]"
            if new.id != row.id:
                return invalid(f"{at}.id", "Questions keep their IDs.")
            text = new.wording.strip()
            probes = [p.strip() for p in new.probes if p.strip()]
            held = [p.strip() for p in new.held_back if p.strip()]
            if row.id and not OWN.fullmatch(row.id) and not text:
                return invalid(f"{at}.wording", "A question can't be empty. Leave it in and skip "
                               "it in the interview if it doesn't fit.")  # fmt: skip
            if held and not row.held_back:
                return invalid(f"{at}.held_back", "Only the probes held back for M6 go here.")
            if len(probes) > MAX_PROBES:
                return invalid(f"{at}.probes", f"Up to {MAX_PROBES} probes per question.")
            if problem := _text_problem(text, MAX_QUESTION, hidden, sop_ok):
                return invalid(f"{at}.wording", problem)
            for pi, probe in enumerate(probes):
                if problem := _text_problem(probe, MAX_PROBE, hidden, sop_ok):
                    return invalid(f"{at}.probes[{pi}]", problem)
            for probe in held:  # held back for M6, where the documents come in
                if problem := _text_problem(probe, MAX_PROBE, hidden, True):
                    return invalid(f"{at}.held_back", problem)
            if (text, probes, held) == (row.wording, row.probes, row.held_back):
                rows.append(row)
                continue
            update: dict[str, object] = {"wording": text, "probes": probes, "held_back": held}
            if not text:  # an own question emptied: a blank row again
                update |= {"id": "", "probes": [], "movement": "", "targets": [], "priority": ""}
            elif not row.id:  # Eric's own question in a blank row
                own += 1
                update |= {"id": f"E{own}", "movement": "", "targets": [], "priority": "standard"}
            changed.append(str(update.get("id") or row.id))
            rows.append(row.model_copy(update=update))
        tables.append(table.model_copy(update={"rows": rows}))
    return Ok((doc.model_copy(update={"tables": tables}), changed))


def interleave(*lists: list[FollowUp]) -> list[FollowUp]:
    """One from each list in turn (F.8 rule 7: every kind of follow-up gets its share of the few
    blank rows), each list in its own order; empty lists are skipped."""
    out: list[FollowUp] = []
    for n in range(max((len(x) for x in lists), default=0)):
        out += [x[n] for x in lists if n < len(x)]
    return out
