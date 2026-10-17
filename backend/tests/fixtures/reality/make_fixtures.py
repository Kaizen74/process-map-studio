"""Builds the Reality fixture's charter (PRD Appendix A.12; phase P13a).

ILLUSTRATIVE ONLY: not SATS data. Run from backend/:
    python tests/fixtures/reality/make_fixtures.py
The generated file is committed; this script makes it reproducible.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document

HERE = Path(__file__).resolve().parent

CHARTER = [
    ("heading", "Load control service charter"),
    ("para", "§1 Preliminary load plans are ready by T-120 so that widebody configurations can "
             "be checked."),
    ("para", "§2 Every load plan is approved before release to Ramp."),
    ("para", "§3 The loading report reaches Load Control within 10 minutes of loading completion."),
    ("para", "§4 Load sheets are issued without delaying the departure slot."),
]  # fmt: skip


def write_docx(name: str, blocks: list[tuple[str, str]]) -> None:
    document = Document()
    for kind, content in blocks:
        if kind == "heading":
            document.add_heading(content, level=1)
        else:
            document.add_paragraph(content)
    document.core_properties.author = "Illustrative fixture"
    document.save(HERE / name)


def main() -> None:
    write_docx("charter_load_control.docx", CHARTER)
    (HERE / "README.md").write_text(
        "# Reality fixture (PRD Appendix A.12)\n\n"
        "ILLUSTRATIVE ONLY — not SATS data. Built by `make_fixtures.py`.\n\n"
        "- `charter_load_control.docx` (source kind `policy_or_charter`): the four charter clauses "
        "§1 to §4 of Appendix A.12. The owner-stated target (Load control lead, 2026-10-01) is "
        "entered by the tests, not stored here.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
