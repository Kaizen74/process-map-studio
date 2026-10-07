"""The data request template (API_CONTRACT.md → GET /templates/data-request; PRD §3.13.2, R1).

What Eric sends to a system owner to ask for an event-log extract. Pure and deterministic: no
engagement, no AI; the same file every time, with [bracketed] placeholders to fill in.
"""

from __future__ import annotations

from io import BytesIO

from docx import Document

from app.domain.enums import SystemLogColumn as LogColumn
from app.domain.system_records import ColumnSpec, DataRequestDocument

TITLE = "System records: data request"
SUBTITLE = "Process Map Studio · event-log extract request"


# PRD §3.13.1, in the order of B.40; case attributes are any extra columns.
COLUMNS = [
    ColumnSpec(name=LogColumn.CASE_ID.value, required=True,
               meaning="The work item each event belongs to (for example a flight, purchase "
                       "order or contract)", sample="PO-10421"),
    ColumnSpec(name=LogColumn.ACTIVITY.value, required=True,
               meaning="The recorded event or status change, as the system names it",
               sample="Order approved"),
    ColumnSpec(name=LogColumn.TIMESTAMP.value, required=True,
               meaning="When the event happened (its start, if end_timestamp is given), with "
                       "date and time", sample="2026-03-02 09:15"),
    ColumnSpec(name=LogColumn.END_TIMESTAMP.value, required=False,
               meaning="When the activity finished, if the system records it (lets work and "
                       "waiting time be told apart)", sample="2026-03-02 09:40"),
    ColumnSpec(name=LogColumn.RESOURCE.value, required=False,
               meaning="The user ID in the system; only if no role can be given (converted to a "
                       "role on import and discarded)", sample=""),
    ColumnSpec(name=LogColumn.ROLE.value, required=False,
               meaning="The role or team that performed the event (preferred over user IDs)",
               sample="Buyer"),
    ColumnSpec(name=LogColumn.SYSTEM.value, required=False,
               meaning="The source system's name, if the extract combines several systems",
               sample="ERP"),
    ColumnSpec(name="case attributes", required=False,
               meaning="Any extra columns useful as filters (for example region, product or "
                       "amount band); no personal data", sample="Region: North"),
]  # fmt: skip
HEADER = [c.name for c in COLUMNS if c.name != "case attributes"]
APPROVAL_FIELDS = [
    "Data owner name",
    "Data owner role",
    "Date approved",
    "Approved for this purpose ☐",
]
TABLE_HEAD = ("Column", "Required", "What it holds", "Sample row")


def build() -> DataRequestDocument:
    return DataRequestDocument(
        title=TITLE,
        subtitle=SUBTITLE,
        purpose=[
            "We are mapping how the [process] process works today. We would like an extract of "
            "the system's event records to measure volumes and waiting times in [process].",
            "The records are used for the process only: no individual performance analysis, "
            "and no figure is ever shown for a person.",
        ],
        scope=[
            "Process: [process].",
            "Start event: [the event that starts a case, for example 'order created'].",
            "End event: [the event that ends a case, for example 'invoice paid'].",
            "Please include every event a case goes through between the two, including any "
            "loops, corrections or cancellations.",
        ],
        window=[
            "From [date] to [date].",
            "3 to 6 months is ideal; at least 4 weeks. Cases that start before the window or "
            "end after it may be included as they are.",
        ],
        columns=COLUMNS,
        column_note="Required columns are marked Yes. One row per event; the sample row shows "
        "the expected form.",
        privacy=[
            "Please give the role or team for each event rather than user IDs wherever the "
            "system allows it.",
            "If user IDs are included, they are converted to roles when the file is imported and "
            "then discarded: they are never stored.",
            "No free-text comment fields.",
            "No customer personal data (names, addresses, contact details or account numbers).",
        ],
        format=[
            "CSV (UTF-8) or Excel (.xlsx), with the column names in the first row.",
            "One file per system. If the same case has different IDs in different systems, "
            "please add a small file that links the IDs.",
            "Dates and times in one consistent format; please tell us the time zone.",
        ],
        approval_fields=APPROVAL_FIELDS,
        retention="The extract is stored only on the analyst's computer and deleted with the "
        "engagement. It is not shared with anyone else.",
    )


def filename(fmt: str) -> str:
    return "data-request-header.csv" if fmt == "csv" else f"data-request-template.{fmt}"


def render_csv() -> bytes:
    """The header row only, ready for the system owner to fill."""
    return (",".join(HEADER) + "\n").encode("utf-8")


def _md_cell(text: str) -> str:
    return text.replace("|", "/") or "—"


def render_markdown(doc: DataRequestDocument) -> str:
    lines = [f"# {doc.title}", "", doc.subtitle, "", "## 1. Purpose", ""]
    lines += [*doc.purpose, "", "## 2. Process scope", ""]
    lines += [f"- {x}" for x in doc.scope]
    lines += ["", "## 3. Date window", "", *[f"- {x}" for x in doc.window]]
    lines += ["", "## 4. Columns", "", doc.column_note, ""]
    lines += ["| " + " | ".join(TABLE_HEAD) + " |", "|---|---|---|---|"]
    lines += [f"| {c.name} | {'Yes' if c.required else 'No'} | {_md_cell(c.meaning)} "
              f"| {_md_cell(c.sample)} |" for c in doc.columns]  # fmt: skip
    lines += ["", "## 5. Privacy requirements", "", *[f"- {x}" for x in doc.privacy]]
    lines += ["", "## 6. Format", "", *[f"- {x}" for x in doc.format]]
    lines += ["", "## 7. Data owner approval", ""]
    lines += [f"- {field}: " + ("" if field.endswith("☐") else "______") for field in
              doc.approval_fields]  # fmt: skip
    lines += ["", doc.retention, ""]
    return "\n".join(line.rstrip() for line in lines)


def render_docx(doc: DataRequestDocument) -> bytes:
    """The same content as the Markdown, editable in Word."""
    word = Document()
    properties = word.core_properties
    properties.title, properties.author = doc.title, "Process Map Studio"
    word.add_heading(doc.title, level=0)
    word.add_paragraph(doc.subtitle)
    word.add_heading("1. Purpose", level=1)
    for paragraph in doc.purpose:
        word.add_paragraph(paragraph)
    for heading, items in (("2. Process scope", doc.scope), ("3. Date window", doc.window)):
        word.add_heading(heading, level=1)
        for item in items:
            word.add_paragraph(item, style="List Bullet")
    word.add_heading("4. Columns", level=1)
    word.add_paragraph(doc.column_note)
    table = word.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    for cell, text in zip(table.rows[0].cells, TABLE_HEAD, strict=True):
        cell.text = ""
        cell.paragraphs[0].add_run(text).bold = True
    for c in doc.columns:
        cells = table.add_row().cells
        cells[0].text, cells[1].text = c.name, "Yes" if c.required else "No"
        cells[2].text, cells[3].text = c.meaning, c.sample
    for heading, items in (("5. Privacy requirements", doc.privacy), ("6. Format", doc.format)):
        word.add_heading(heading, level=1)
        for item in items:
            word.add_paragraph(item, style="List Bullet")
    word.add_heading("7. Data owner approval", level=1)
    approval = word.add_table(rows=0, cols=2)
    approval.style = "Table Grid"
    for field in doc.approval_fields:
        cells = approval.add_row().cells
        cells[0].text = field.removesuffix(" ☐")
        cells[1].text = "☐" if field.endswith("☐") else ""
    word.add_paragraph(doc.retention)
    out = BytesIO()
    word.save(out)
    return out.getvalue()
