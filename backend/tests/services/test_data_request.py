"""The data request template (API_CONTRACT.md → GET /templates/data-request; PRD §3.13.2,
criterion 82, R1): the seven items in Markdown and Word, the CSV header, no engagement data."""

from __future__ import annotations

from io import BytesIO

from docx import Document

from app.services import data_request, wording


def test_the_markdown_has_the_seven_items_in_order() -> None:
    md = data_request.render_markdown(data_request.build())
    headings = [line for line in md.splitlines() if line.startswith("## ")]
    assert headings == ["## 1. Purpose", "## 2. Process scope", "## 3. Date window",
                        "## 4. Columns", "## 5. Privacy requirements", "## 6. Format",
                        "## 7. Data owner approval"]  # fmt: skip
    assert "to measure volumes and waiting times in [process]" in md
    assert "no individual performance analysis" in md
    assert "3 to 6 months is ideal; at least 4 weeks" in md
    assert "converted to roles when the file is imported and then discarded" in md
    assert "No free-text comment fields." in md and "No customer personal data" in md
    assert "CSV (UTF-8) or Excel (.xlsx)" in md and "One file per system." in md
    assert "stored only on the analyst's computer and deleted with the engagement" in md
    assert wording.banned_words(md) == []


def test_the_column_table_marks_the_required_columns_with_a_sample_row() -> None:
    md = data_request.render_markdown(data_request.build())
    rows = [line for line in md.splitlines() if line.startswith("| ") and "---" not in line]
    by_name = {r.split(" | ")[0].removeprefix("| "): r for r in rows[1:]}
    assert list(by_name) == ["case_id", "activity", "timestamp", "end_timestamp", "resource",
                             "role", "system", "case attributes"]  # fmt: skip
    required = [name for name, row in by_name.items() if row.split(" | ")[1] == "Yes"]
    assert required == ["case_id", "activity", "timestamp"]
    assert "PO-10421" in by_name["case_id"] and "Buyer" in by_name["role"]
    assert by_name["resource"].endswith("| — |")  # no user ID in the sample row, ever


def test_word_carries_the_same_content_editable() -> None:
    word = Document(BytesIO(data_request.render_docx(data_request.build())))
    headings = [p.text for p in word.paragraphs if p.style is not None
                and p.style.name.startswith("Heading")]  # fmt: skip
    assert headings[0] == "1. Purpose" and headings[-1] == "7. Data owner approval"
    columns, approval = word.tables
    assert [c.text for c in columns.rows[0].cells] == ["Column", "Required", "What it holds",
                                                       "Sample row"]  # fmt: skip
    assert len(columns.rows) == 1 + 8
    assert [r.cells[0].text for r in approval.rows] == [
        "Data owner name",
        "Data owner role",
        "Date approved",
        "Approved for this purpose",
    ]
    assert approval.rows[-1].cells[1].text == "☐"


def test_the_csv_is_the_header_row_only() -> None:
    assert data_request.render_csv() == (
        b"case_id,activity,timestamp,end_timestamp,resource,role,system\n"
    )
    assert data_request.filename("csv") == "data-request-header.csv"
    assert data_request.filename("docx") == "data-request-template.docx"
