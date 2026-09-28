"""Readiness and the guided path (PRD §4 readiness, §5.3 engagement navigation, §5.4 Draft).

The rules live in `assess`, a pure function of the stored facts and whether the API key is set,
so every rule can be tested on its own. API_CONTRACT.md → Readiness describes them in words.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import quality as quality_action
from app.actions import redaction
from app.actions.engagements import ENGAGEMENT_MISSING
from app.actions.settings import get_settings
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import SourceKind
from app.domain.models import Readiness, ReadinessFacts, SourceFacts
from app.domain.quality import QualityCard
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import readiness as repo
from app.services import quality

Sessions = sessionmaker[Session]

NAV_ORDER = (
    "setup",
    "sources",
    "draft",
    "review",
    "published",
    "matrix",
    "gap_analysis",
    "registers",
    "leadership",
    "exports",
)
OPTIONAL = {"gap_analysis"}
DONE, ATTENTION, NOT_STARTED = "done", "attention", "not_started"

# Kinds that describe the steps of the process. A job description alone describes roles only.
PROCESS_DOCUMENTS = {
    SourceKind.SOP.value,
    SourceKind.MANUAL.value,
    SourceKind.EXECUTED_ARTEFACT.value,
    SourceKind.OTHER.value,
}
TRANSCRIPTS = {SourceKind.INTERVIEW_TRANSCRIPT.value}

ADD_KEY = "Add your Claude API key in Settings"
ADD_TRANSCRIPT = "Add an interview transcript"
ADD_DOCUMENT = "Add a process document such as an SOP or manual"
ONLY_JDS = (
    "Add a process document such as an SOP or manual (job descriptions alone don't describe "
    "the steps)"
)


def _names(sources: list[SourceFacts]) -> str:
    return ", ".join(source.filename for source in sources)


def _kind_missing(
    sources: list[SourceFacts], kinds: set[str], add_message: str, what: str
) -> tuple[bool, str | None, set[str]]:
    """Whether a source of these kinds is ready; if not, what to do and which files it names."""
    matching = [s for s in sources if s.kind in kinds]
    if any(s.text_status == "ready" for s in matching):
        return True, None, set()
    waiting = [s for s in matching if s.text_status == "pending"]
    if waiting:
        return False, f"Wait for the {what} to be read ({_names(waiting)})", set()
    failed = [s for s in matching if s.text_status == "failed"]
    if failed:
        message = f"The {what} couldn't be read ({_names(failed)}). Remove it and upload a new copy"
        return False, message, {s.id for s in failed}
    return False, add_message, set()


def _speaker_items(sources: list[SourceFacts]) -> list[str]:
    items = []
    for source in sources:
        if source.text_status == "ready" and source.unmapped_speakers:
            count = source.unmapped_speakers
            noun = "speaker" if count == 1 else "speakers"
            items.append(f"Map {count} {noun} in {source.filename}")
    return items


def _fails(card: QualityCard, check_id: str) -> bool:
    return any(c.id == check_id and c.status == "fail" for c in card.checks)


def assess(
    facts: ReadinessFacts, *, key_set: bool, blockers: int = 0, other_blockers: int = 0
) -> Readiness:
    """Turn stored facts into nav statuses, the next step and the plain 'missing' list.

    `blockers`: failing hard checks on the draft's quality card; `other_blockers`: those other
    than Q6 "Fully reviewed", which the steps left to review already count on the Review step.
    """
    sources = facts.sources
    transcripts_ready, transcript_item, named_t = _kind_missing(
        sources, TRANSCRIPTS, ADD_TRANSCRIPT, "interview transcript"
    )
    has_jd = any(s.kind == SourceKind.JOB_DESCRIPTION.value for s in sources)
    document_add = ONLY_JDS if has_jd else ADD_DOCUMENT
    documents_ready, document_item, named_d = _kind_missing(
        sources, PROCESS_DOCUMENTS, document_add, "process document"
    )
    speaker_items = _speaker_items(sources)
    source_items = [item for item in (transcript_item, document_item) if item] + speaker_items
    missing = ([] if key_set else [ADD_KEY]) + source_items

    failed_unnamed = [
        s for s in sources if s.text_status == "failed" and s.id not in named_t | named_d
    ]
    source_issues = len(source_items) + len(failed_unnamed)

    draft_exists = facts.version_count > 0
    progress = facts.latest_progress
    left_to_review = progress.total - progress.reviewed

    nav: dict[str, str] = {}
    counts: dict[str, int] = {}

    def attention(key: str, count: int) -> None:
        nav[key] = ATTENTION
        counts[key] = count

    nav["setup"] = DONE if facts.trigger.strip() and facts.end_point.strip() else NOT_STARTED
    if not sources:
        nav["sources"] = NOT_STARTED
    elif source_issues:
        attention("sources", source_issues)
    else:
        nav["sources"] = DONE
    nav["draft"] = DONE if draft_exists else NOT_STARTED
    if not draft_exists or progress.total == 0:
        nav["review"] = NOT_STARTED
    elif left_to_review or blockers:
        attention("review", left_to_review + other_blockers)
    else:
        nav["review"] = DONE
    nav["published"] = DONE if facts.published else NOT_STARTED
    nav["matrix"] = DONE if draft_exists else NOT_STARTED
    nav["gap_analysis"] = DONE if facts.gap_finalised else NOT_STARTED
    nav["registers"] = DONE if draft_exists else NOT_STARTED
    nav["leadership"] = DONE if facts.published else NOT_STARTED
    nav["exports"] = DONE if facts.exported else NOT_STARTED

    next_step = next(
        (key for key in NAV_ORDER if key not in OPTIONAL and nav[key] != DONE),
        None,
    )
    return Readiness(
        key_set=key_set,
        transcripts_ready=transcripts_ready,
        documents_ready=documents_ready,
        speakers_unmapped=sum(s.unmapped_speakers for s in sources if s.text_status == "ready"),
        draft_exists=draft_exists,
        blockers_count=blockers,
        nav={key: nav[key] for key in NAV_ORDER},
        nav_counts=counts,
        next_step=next_step,
        missing=missing,
        ready_to_draft=not missing,
    )


def get_readiness(config: AppConfig, sessions: Sessions, engagement_id: str) -> Result[Readiness]:
    with session_scope(sessions) as session:
        facts = repo.facts(session, engagement_id)
        if facts is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        terms = redaction.name_replacements(session, engagement_id)
        card = quality_action.draft_card(config, session, engagement_id)
    blockers = quality.hard_failures(card) if card else 0
    other_blockers = blockers - (1 if card and _fails(card, "Q6") else 0)
    # File names appear in the "missing" list, so names in them are hidden (G10).
    facts = facts.model_copy(
        update={
            "sources": [
                s.model_copy(update={"filename": redaction.hide(s.filename, terms)})
                for s in facts.sources
            ]
        }
    )
    match get_settings(config):
        case Err() as err:
            return err
        case Ok(value=settings):
            return Ok(
                assess(
                    facts,
                    key_set=settings.key_set,
                    blockers=blockers,
                    other_blockers=other_blockers,
                )
            )
