"""Run records: how each draft was made, and what a refresh would do differently (anti-drift).

Claude's answers can differ between runs made at different times: a new model chosen in Settings,
a different effort, the independent verifier switched off, or reworded instructions after an app
update (each wording is pinned to its version by the instruction lock). Every draft and refresh
stamps its version with a run record; before a refresh, `refresh_check` compares that record with
what a refresh would use now and says what changed in plain words. It warns and never blocks:
Eric decides (API_CONTRACT → Run record, GET /versions/{vid}/refresh-check).
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions.settings import effective_settings
from app.config import APP_VERSION, AppConfig
from app.db import session_scope
from app.domain.models import RefreshCheck, RunRecord
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext
from app.repositories import versions
from app.services import prompts

Sessions = sessionmaker[Session]

VERSION_MISSING = "That version doesn't exist."
NO_RECORD = (
    "This draft was made before the app kept a record of how drafts are made, so a refresh "
    "can't be compared with it. Fresh suggestions may differ from the ones already on the map."
)

# The instructions a draft or refresh uses, in plain words (the gap analyses' own prompts don't
# change what a refresh drafts).
DRAFT_INSTRUCTIONS = {
    "S0_ocr_page": "reading scanned pages",
    "S1_extract_interview": "extracting steps from interviews",
    "S1_extract_document": "extracting steps from documents",
    "S1_extract_jd": "extracting roles from job descriptions",
    "S2_canonicalise": "grouping claims into steps",
    "S3_calibrate": "comparing each source with the steps",
    "S3b_verify": "the independent verification",
    "S4_assemble": "building the map",
    "S5_questions": "writing validation questions",
    "R_repair": "fixing an answer's format",
}


def _flag(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def made_with(ctx: AiContext) -> RunRecord:
    """The record of a run about to be made with this context (effort as actually sent)."""
    return RunRecord(
        model=ctx.model,
        effort=ctx.effort,
        verifier=ctx.verifier_enabled,
        instructions=prompts.instruction_versions(),
        app_version=APP_VERSION,
    )


def planned(config: AppConfig) -> Result[RunRecord]:
    """What a run started now would use, from Settings alone (no AI call)."""
    match effective_settings(config):
        case Err() as err:
            return err
        case Ok(value=values):
            pass
    return Ok(
        RunRecord(
            model=values["ANTHROPIC_MODEL"],
            effort=values["ANTHROPIC_EFFORT"] or None,
            verifier=_flag(values["VERIFIER_ENABLED"]),
            instructions=prompts.instruction_versions(),
            app_version=APP_VERSION,
        )
    )


def differences(before: RunRecord | None, now: RunRecord) -> list[str]:
    """What differs between the run that made a draft and a run started now, in plain words."""
    if before is None:
        return [NO_RECORD]
    changes: list[str] = []
    if before.model != now.model:
        changes.append(
            f"The model changed: this draft was made with {before.model}; "
            f"a refresh now uses {now.model}."
        )
    if before.effort and now.effort and before.effort != now.effort:
        changes.append(f"The effort setting changed from {before.effort} to {now.effort}.")
    if before.verifier and not now.verifier:
        changes.append(
            "The independent verifier checked this draft, but it is now switched off in "
            "Settings, so fresh suggestions would reach the map without that second check."
        )
    elif now.verifier and not before.verifier:
        changes.append(
            "The independent verifier was off for this draft and is now on, so fresh "
            "suggestions get a second check this draft didn't have."
        )
    reworded = [
        f"{label} (version {before.instructions.get(name, 'none')} → "
        f"{now.instructions.get(name, 'none')})"
        for name, label in DRAFT_INSTRUCTIONS.items()
        if before.instructions.get(name) != now.instructions.get(name)
    ]
    if reworded:
        changes.append(
            "Claude's instructions changed since this draft was made (an app update): "
            + "; ".join(reworded)
            + "."
        )
    return changes


def refresh_check(config: AppConfig, sessions: Sessions, version_id: str) -> Result[RefreshCheck]:
    with session_scope(sessions) as session:
        if versions.get(session, version_id) is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        stored = versions.run_record(session, version_id)
    match planned(config):
        case Err() as err:
            return err
        case Ok(value=now):
            pass
    before = RunRecord.model_validate(stored) if stored else None
    return Ok(RefreshCheck(made_with=before, now=now, changes=differences(before, now)))
