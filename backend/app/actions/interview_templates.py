"""Standard interview templates (API_CONTRACT.md → Interview templates; PRD v1.10 F.9, §4).

No engagement and no AI: the files come from the question bank alone, so they are made once and
kept for the life of the app.
"""

from __future__ import annotations

from functools import cache

from app.domain.enums import InterviewType
from app.domain.interview import TemplateFile, TemplateSummary
from app.domain.result import Err, ErrorKind, Ok, Result
from app.services import interview_templates as templates

MEDIA = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown; charset=utf-8",
}
UNKNOWN_TYPE = "Choose landscape, practice or follow_up."
UNKNOWN_FORMAT = "Choose docx or md."


def plans() -> Result[list[TemplateSummary]]:
    """Each template's purpose and minute plan, for the home screen and the Interview screen."""
    bank = templates.load_bank()
    if isinstance(bank, Err):
        return bank
    return Ok(templates.summaries(bank.value))


def template_file(kind: str, fmt: str) -> Result[TemplateFile]:
    if kind not in {k.value for k in InterviewType}:
        return Err(ErrorKind.VALIDATION, UNKNOWN_TYPE, {"field": "type"})
    if fmt not in MEDIA:
        return Err(ErrorKind.VALIDATION, UNKNOWN_FORMAT, {"field": "format"})
    return _made(InterviewType(kind), fmt)


@cache
def _made(kind: InterviewType, fmt: str) -> Result[TemplateFile]:
    bank = templates.load_bank()
    if isinstance(bank, Err):
        return bank
    doc = templates.build(bank.value, kind)
    content = (
        templates.render_docx(doc) if fmt == "docx" else templates.render_markdown(doc).encode()
    )
    return Ok(
        TemplateFile(filename=templates.filename(kind, fmt), media_type=MEDIA[fmt], content=content)
    )
