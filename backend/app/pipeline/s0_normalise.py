"""S0 Normalise, AI part (PRD §3.7): read scanned PDF pages with `S0_ocr_page`.

Files are split into passages when they are uploaded (the reading job). PDF pages with almost no
text are listed in `sources.ocr_pages`; here each one is sent to Claude as a single-page PDF and the
transcribed lines become passages of that page. A page Claude can't read stays listed (the draft
continues without it); a problem with the key or the connection stops the run.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.config import AppConfig
from app.db import session_scope
from app.domain import ai_schemas
from app.domain.models import AiCallRecord
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls
from app.repositories import sources as sources_repo
from app.services import ai_service, grounding, parsing, prompts

Sessions = sessionmaker[Session]

STAGE_ID = "S0_ocr_page"


@dataclass(slots=True)
class S0Tally:
    pages_read: int = 0
    pages_unreadable: list[int] = field(default_factory=list)
    skipped_no_pdf_input: bool = False


def page_blocks(pdf: bytes, page: int) -> list[dict[str, object]]:
    return [
        {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.b64encode(pdf).decode("ascii"),
            },
        },
        {"type": "text", "text": f"This is page {page} of the document."},
    ]


def read_scanned_pages(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    source_id: str,
    job_id: str | None = None,
) -> Result[S0Tally]:
    tally = S0Tally()
    with session_scope(sessions) as session:
        info = sources_repo.reading_info(session, source_id)
        pages = sources_repo.ocr_pages(session, source_id) if info else []
    if info is None or info.format != "pdf" or not pages:
        return Ok(tally)
    if not ctx.pdf_input:
        tally.skipped_no_pdf_input = True
        return Ok(tally)
    match prompts.load_prompt(STAGE_ID):
        case Err() as err:
            return err
        case Ok(value=prompt):
            pass
    match prompts.load_prompt(ai_service.REPAIR_STAGE):
        case Err() as err:
            return err
        case Ok(value=repair):
            pass
    for page in pages:
        match parsing.split_pdf_page(Path(info.stored_path), page):
            case Err():
                tally.pages_unreadable.append(page)
                continue
            case Ok(value=pdf):
                pass
        call = ai_service.StageCall(
            stage_id=STAGE_ID,
            prompt_version=prompt.version,
            system=prompt.text,
            blocks=page_blocks(pdf, page),
            output_model=ai_schemas.S0OcrOutput,
            model=ctx.model,
            repair_prompt=repair.text,
            effort=ctx.effort,
            structured_outputs=ctx.structured_outputs,
        )
        result = ai_service.call_claude(ctx.conn, call)
        used: list[AiCallRecord] = (
            result.value.calls if isinstance(result, Ok) else calls_in(result)
        )
        with session_scope(sessions) as session:
            record_calls(session, job_id, used)
        match result:
            case Err(kind=ErrorKind.AI_FORMAT):
                tally.pages_unreadable.append(page)
                continue
            case Err() as err:
                return ai_failure(err)
            case Ok(value=answer):
                pass
        lines = [
            (text, grounding.detect_instruction_like(text))
            for line in ai_schemas.S0OcrOutput.model_validate(answer.data).lines
            if (text := " ".join(line.split()))
        ]
        if not lines:
            tally.pages_unreadable.append(page)
            continue
        with session_scope(sessions) as session:
            sources_repo.add_page_text(session, source_id, page, lines)
        tally.pages_read += 1
    return Ok(tally)
