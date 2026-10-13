"""The intent AI jobs (API_CONTRACT.md → Intent; PRD §3.16, G16; P13a-2): S1 intent proposes
statements from policies and charters; IX_compare proposes design gaps between confirmed intent and
the documented process. Both are checked (G3-G5, IX1) and verified (IX_verify) before anything is
stored, and nothing counts until Eric confirms it. Rejected proposals are kept, with the check
that turned them down, so he can see them."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.actions import intent as intent_actions
from app.actions import lenses, redaction
from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.actions.versions import VERSION_MISSING
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import IntentOrigin, SourceKind, VerificationStatus, VersionState
from app.domain.models import NameReplacement
from app.domain.reality import (
    ConflictPatch,
    IntentConflictRecord,
    IntentConflictView,
    IntentJobStarted,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline import intent_ai as ai
from app.pipeline import s1_extract
from app.pipeline.context import ai_context, role_groups
from app.repositories import audit
from app.repositories import elements as elements_repo
from app.repositories import engagements as engagements_repo
from app.repositories import intent as repo
from app.repositories import jobs as jobs_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo

Sessions = sessionmaker[Session]
Enqueue = Callable[[str], None]

EXTRACT_JOB = "intent_extract"
COMPARE_JOB = "intent_compare"
INTENT_JOBS = (EXTRACT_JOB, COMPARE_JOB)
NO_INTENT_SOURCE = "Add a policy or charter and wait for it to be read first."
NOT_A_DRAFT = "This version is published and can't be changed. Reopen it as a new draft."
NOTHING_CONFIRMED = "Confirm at least one intent statement first."
NO_DOCUMENTS = "Add an SOP or manual and wait for it to be read first."
CONFLICT_MISSING = "That design gap doesn't exist."
CONFLICT_REJECTED = "This design gap failed the checks, so it can't be used."
UNEXPECTED = (
    "Something went wrong while working on the intent statements. Nothing was saved. Try again, "
    "or use Copy details to report it."
)
CONFLICT_ACTIONS = {"confirmed": "Confirmed design gap", "dismissed": "Dismissed design gap",
                    "proposed": "Reopened design gap"}  # fmt: skip
POLICY = SourceKind.POLICY_OR_CHARTER.value
DOCUMENTED = (SourceKind.SOP.value, SourceKind.MANUAL.value)


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _summary(proposed: int, rejected: int, one: str, many: str) -> str:
    """'Claude proposed 6 intent statements: 4 passed the checks; 2 were turned down and are
    listed as rejected.'"""
    head = f"Claude proposed {_plural(proposed, one, many)}"
    if proposed == 0:
        return head + "."
    kept = proposed - rejected
    parts = []
    if kept:
        parts.append("it passed the checks" if proposed == 1 else f"{kept} passed the checks")
    if rejected:
        was = "was" if rejected == 1 else "were"
        are = "is" if rejected == 1 else "are"
        who = "it" if proposed == 1 else str(rejected)
        parts.append(f"{who} {was} turned down and {are} listed as rejected")
    return f"{head}: {'; '.join(parts)}."


def _places(session: Session, engagement_id: str) -> ai.MapPlaces:
    version_id = versions_repo.current_map_id(session, engagement_id)
    if version_id is None:
        return ai.MapPlaces()
    steps = {e.stable_key: e.label for e in elements_repo.elements(session, version_id)
             if e.kind not in ("start", "end") and e.review_status != "rejected"}  # fmt: skip
    return ai.MapPlaces(steps, [p.name for p in elements_repo.phases(session, version_id)])


def _passages(
    session: Session, source_id: str, terms: list[NameReplacement]
) -> ai.SourcePassages | None:
    info = sources_repo.reading_info(session, source_id)
    if info is None:
        return None
    stored = sources_repo.stored_segments(session, source_id)
    segments = s1_extract.prompt_segments(stored, info.format, terms)
    return ai.SourcePassages(info.id, redaction.hide(info.filename, terms), info.kind, segments)


def _intent_sources(session: Session, engagement_id: str) -> list[ai.SourcePassages]:
    """Every ready policy or charter, and the purpose clauses of ready SOPs and manuals."""
    terms = redaction.name_replacements(session, engagement_id)
    out = []
    for source in sources_repo.list_for_engagement(session, engagement_id):
        if source.text_status != "ready" or source.kind not in (POLICY, *DOCUMENTED):
            continue
        src = _passages(session, source.id, terms)
        if src is None:
            continue
        if src.kind != POLICY:
            src = ai.SourcePassages(src.source_id, src.source_name, src.kind,
                                    ai.purpose_clauses(src.segments))  # fmt: skip
        if src.segments:
            out.append(src)
    return out


def _documented(session: Session, engagement_id: str) -> list[ai.SourcePassages]:
    terms = redaction.name_replacements(session, engagement_id)
    found = [_passages(session, s.id, terms)
             for s in sources_repo.list_for_engagement(session, engagement_id)
             if s.text_status == "ready" and s.kind in DOCUMENTED]  # fmt: skip
    return ai.documented_refs([d for d in found if d is not None and d.segments])


# --- S1 intent -------------------------------------------------------------------------------


def start_extract(
    sessions: Sessions, engagement_id: str, enqueue: Enqueue
) -> Result[IntentJobStarted]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        if not _intent_sources(session, engagement_id):
            return Err(ErrorKind.CONFLICT, NO_INTENT_SOURCE)
        job = jobs_repo.create(session, engagement_id=engagement_id, job_type=EXTRACT_JOB,
                               target_id=engagement_id)  # fmt: skip
    enqueue(job.id)
    return Ok(IntentJobStarted(job_id=job.id, engagement_id=engagement_id))


def run_extract(config: AppConfig, sessions: Sessions, job_id: str) -> Result[str]:
    """The S1 intent job: proposals from each source, checked and verified, stored for Eric."""
    with session_scope(sessions) as session:
        job = jobs_repo.get(session, job_id)
        engagement_id = (job.target_id or "") if job else ""
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        sources = _intent_sources(session, engagement_id)
        places = _places(session, engagement_id)
        groups = role_groups(session, engagement_id)
        terms = redaction.name_replacements(session, engagement_id)
    if not sources:
        return Ok(NO_INTENT_SOURCE)
    match ai_context(config):
        case Err() as err:
            return err
        case Ok(value=ctx):
            pass
    checked: list[ai.Checked] = []
    for src in sources:
        match ai.extract(sessions, ctx, src, places, job_id):
            case Err() as err:
                return err
            case Ok(value=proposals):
                checked += [ai.check_statement(p, src, places, groups, terms) for p in proposals]
    kinds = {s.segment_id: src.kind for src in sources for s in src.segments}
    match ai.verify(sessions, ctx, checked, kinds, terms, job_id):
        case Err() as err:
            return err
        case Ok():
            pass
    with session_scope(sessions) as session:
        repo.delete_proposed_documents(session, engagement_id)
        decided = {(r.source_id, r.text) for r in repo.for_engagement(session, engagement_id)
                   if r.origin == IntentOrigin.DOCUMENT.value}  # fmt: skip
        for c in checked:
            fields = {k: v for k, v in c.fields.items() if k != "verifier_verdict"}
            if (fields["source_id"], fields["text"]) in decided:
                continue  # Eric already confirmed or dismissed this statement
            repo.add(session, {
                **fields, "engagement_id": engagement_id, "origin": IntentOrigin.DOCUMENT.value,
                "verification_status": (VerificationStatus.VERIFIED.value if c.kept
                                        else VerificationStatus.REJECTED.value),
                "rejection_guardrail": c.guardrail, "status": "proposed", "note": "",
            })  # fmt: skip
    rejected = sum(1 for c in checked if not c.kept)
    return Ok(_summary(len(checked), rejected, "intent statement", "intent statements"))


# --- IX_compare --------------------------------------------------------------------------------


def _items(session: Session, engagement_id: str) -> list[ai.IntentItem]:
    """The confirmed statements as sent: names hidden, with the words a conflict may quote."""
    rows = [r for r in repo.for_engagement(session, engagement_id) if r.status == "confirmed"]
    views = {v.id: v for v in intent_actions.views(session, engagement_id, rows)}
    return [
        ai.IntentItem(
            ref=f"i{n}", intent_id=r.id, kind=r.kind, label=views[r.id].label,
            words=views[r.id].quote if r.origin == IntentOrigin.DOCUMENT.value
            else views[r.id].text,
        )
        for n, r in enumerate(rows, start=1)
    ]  # fmt: skip


def start_compare(
    sessions: Sessions, version_id: str, enqueue: Enqueue
) -> Result[IntentJobStarted]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        if version.state != VersionState.DRAFT.value:
            return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
        if not _items(session, version.engagement_id):
            return Err(ErrorKind.CONFLICT, NOTHING_CONFIRMED)
        if not _documented(session, version.engagement_id):
            return Err(ErrorKind.CONFLICT, NO_DOCUMENTS)
        job = jobs_repo.create(session, engagement_id=version.engagement_id,
                               job_type=COMPARE_JOB, target_id=version_id)  # fmt: skip
    enqueue(job.id)
    return Ok(IntentJobStarted(job_id=job.id, version_id=version_id))


def run_compare(config: AppConfig, sessions: Sessions, job_id: str) -> Result[str]:
    """The IX_compare job: design-gap proposals, checked and verified, stored on the version."""
    with session_scope(sessions) as session:
        job = jobs_repo.get(session, job_id)
        version = versions_repo.get(session, (job.target_id or "") if job else "")
        if version is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        items = _items(session, version.engagement_id)
        documents = _documented(session, version.engagement_id)
        groups = role_groups(session, version.engagement_id)
        terms = redaction.name_replacements(session, version.engagement_id)
    if not items:
        return Ok(NOTHING_CONFIRMED)
    if not documents:
        return Ok(NO_DOCUMENTS)
    match ai_context(config):
        case Err() as err:
            return err
        case Ok(value=ctx):
            pass
    match ai.compare(sessions, ctx, items, documents, job_id):
        case Err() as err:
            return err
        case Ok(value=proposals):
            pass
    by_ref = {i.ref: i for i in items}
    checked = [ai.check_conflict(p, by_ref, documents, groups, terms) for p in proposals]
    kinds = {s.segment_id: d.kind for d in documents for s in d.segments}
    match ai.verify(sessions, ctx, checked, kinds, terms, job_id):
        case Err() as err:
            return err
        case Ok():
            pass
    with session_scope(sessions) as session:
        repo.delete_proposed_conflicts(session, version.id)
        decided = {(r.intent_id, tuple(r.segment_ids)) for r in repo.conflicts(session, version.id)}
        for c in checked:
            intent_id = str(c.fields["intent_id"])
            segments = c.fields["segment_ids"]
            assert isinstance(segments, list)
            if not intent_id or (intent_id, tuple(segments)) in decided:
                continue  # names a statement that wasn't sent, or Eric already decided it
            repo.add_conflict(session, {
                **c.fields, "version_id": version.id,
                "verifier_verdict": c.fields.get("verifier_verdict", "not_run"),
                "verification_status": (VerificationStatus.VERIFIED.value if c.kept
                                        else VerificationStatus.REJECTED.value),
                "rejection_guardrail": c.guardrail, "status": "proposed", "note": "",
            })  # fmt: skip
    rejected = sum(1 for c in checked if not c.kept)
    return Ok(_summary(len(checked), rejected, "design gap", "design gaps"))


# --- Design gaps: list and decide ---------------------------------------------------------------


def _conflict_views(
    session: Session, engagement_id: str, rows: list[IntentConflictRecord]
) -> list[IntentConflictView]:
    terms = redaction.name_replacements(session, engagement_id)
    statements = repo.for_engagement(session, engagement_id)
    intents = {v.id: v for v in intent_actions.views(session, engagement_id, statements)}
    anchors, _ = lenses.places(session, [r.segment_ids[0] for r in rows if r.segment_ids])
    owners = sources_repo.segment_owners(session, [r.segment_ids[0] for r in rows if r.segment_ids])
    found = sources_repo.get_many(session, [o[0] for o in owners.values()])
    files = {s.id: s.filename for s in found}
    out = []
    for r in rows:
        first = r.segment_ids[0] if r.segment_ids else ""
        intent = intents.get(r.intent_id)
        owner = owners.get(first)
        out.append(IntentConflictView(
            id=r.id, version_id=r.version_id, intent_id=r.intent_id,
            intent_text=intent.text if intent else "", intent_label=intent.label if intent else "",
            intent_quote=redaction.hide(r.intent_quote, terms), segment_ids=r.segment_ids,
            source_name=redaction.hide(files.get(owner[0], ""), terms) if owner else "",
            anchor=anchors.get(first, ""), quote=redaction.hide(r.quote, terms),
            conflict_text=redaction.hide(r.conflict_text, terms),
            verifier_verdict=r.verifier_verdict, verification_status=r.verification_status,
            rejection_guardrail=r.rejection_guardrail, status=r.status, note=r.note,
            created_at=r.created_at,
        ))  # fmt: skip
    return out


def list_conflicts(sessions: Sessions, version_id: str) -> Result[list[IntentConflictView]]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        rows = repo.conflicts(session, version_id)
        return Ok(_conflict_views(session, version.engagement_id, rows))


def update_conflict(
    config: AppConfig, sessions: Sessions, conflict_id: str, patch: ConflictPatch
) -> Result[IntentConflictView]:
    """Confirm, dismiss or reopen a design gap, or note why."""
    with session_scope(sessions) as session:
        row = repo.get_conflict(session, conflict_id)
        version = versions_repo.get(session, row.version_id) if row else None
        if row is None or version is None:
            return Err(ErrorKind.NOT_FOUND, CONFLICT_MISSING)
        changes: dict[str, object] = {}
        if patch.note is not None:
            note = patch.note.strip()
            if len(note) > intent_actions.MAX_NOTE or "\n" in note:
                return Err(ErrorKind.VALIDATION, intent_actions.BAD_NOTE, {"field": "note"})
            if note != row.note:
                changes["note"] = note
        if patch.status is not None:
            if patch.status not in intent_actions.STATUSES:
                return Err(ErrorKind.VALIDATION, intent_actions.BAD_STATUS, {"field": "status"})
            rejected = row.verification_status == VerificationStatus.REJECTED.value
            if patch.status == "confirmed" and rejected:
                return Err(ErrorKind.CONFLICT, CONFLICT_REJECTED)
            if patch.status != row.status:
                changes["status"] = patch.status
        if changes:
            before = {k: getattr(row, k) for k in changes}
            row = repo.update_conflict(session, conflict_id, changes)
            status = changes.get("status")
            action = CONFLICT_ACTIONS[str(status)] if status else "Noted design gap"
            audit.record(session, actor=actor_name(config), action=action,
                         target_type="intent_conflict", target_id=conflict_id,
                         engagement_id=version.engagement_id, before=before,
                         after=changes)  # fmt: skip
        return Ok(_conflict_views(session, version.engagement_id, [row])[0])
