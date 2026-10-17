"""The data request template (API_CONTRACT.md → GET /templates/data-request; PRD §3.13.2, R1).
No engagement and no AI: made once and kept for the life of the app."""

from __future__ import annotations

from functools import cache

from app.domain.interview import TemplateFile
from app.domain.result import Err, ErrorKind, Ok, Result
from app.services import data_request

MEDIA = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "md": "text/markdown; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
}
UNKNOWN_FORMAT = "Choose docx, md or csv."


def template_file(fmt: str) -> Result[TemplateFile]:
    if fmt not in MEDIA:
        return Err(ErrorKind.VALIDATION, UNKNOWN_FORMAT, {"field": "format"})
    return Ok(_made(fmt))


@cache
def _made(fmt: str) -> TemplateFile:
    doc = data_request.build()
    content = {
        "docx": lambda: data_request.render_docx(doc),
        "md": lambda: data_request.render_markdown(doc).encode("utf-8"),
        "csv": data_request.render_csv,
    }[fmt]()
    return TemplateFile(filename=data_request.filename(fmt), media_type=MEDIA[fmt], content=content)
