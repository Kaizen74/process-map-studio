"""Standard interview templates (PRD v1.10 Appendix F.9): built from the question bank only
(no AI, no engagement data), rendered as Markdown and Word with the same content.

Explicit inputs (the bank and the interview type) and structured results; no files, no database.
"""

from __future__ import annotations

from app.domain.enums import InterviewType
from app.domain.interview import (
    DocumentRow,
    DocumentTable,
    InterviewDocument,
    QuestionBank,
    TemplatePlanRow,
    TemplateSection,
    TemplateSummary,
)

ORDER = (InterviewType.LANDSCAPE, InterviewType.PRACTICE, InterviewType.FOLLOW_UP)
IN_STORY = "in story"
CORE_WEIGHT = 2  # core questions (never dropped, F.8 rule 6) get twice a standard share
FORMATS = ("docx", "md")


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
    )


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
        entry = "☐" if field.endswith("☐") else ""
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
            probes = " · ".join(row.probes) if row.probes else ("—" if row.id else "")
            lines.append(f"| {row.id} | {_cell(question)} | {_cell(probes)} | {row.minutes} |  |")
    lines += ["", "## Coverage checklist", ""]
    lines += [f"- [ ] {item}" for item in doc.coverage_checklist]
    lines += ["", "## Close and next steps", ""]
    lines += [f"- {item}:" for item in doc.close_items]
    lines += ["", "---", "", f"*{doc.footer}*", ""]
    return "\n".join(lines)
