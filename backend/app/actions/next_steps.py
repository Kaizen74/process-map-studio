"""What is left before a draft can be published, and accepting the rest in one go (2026-10-28,
Eric: "not sure what I need to do when"; reviewing step by step "felt like a wall").

The to-do list is the publish blockers (`publish.blockers`) grouped by what Eric does about them,
in the order he does it, so the list and a refused Publish never disagree. "Accept remaining"
confirms the unreviewed steps that need nothing fixed; a step the verifier found only partly
supported, or that a map check fails on, is left for him to look at.
"""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.actions import publish as publish_action
from app.actions import quality as quality_action
from app.actions import versions as versions_action
from app.actions.engagements import actor_name
from app.actions.review import DRAFT_STATE, NOT_A_DRAFT
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import ReviewStatus
from app.domain.models import (
    AcceptedSteps,
    NextStep,
    NextStepItem,
    NextSteps,
    PublishBlocker,
    SkippedStep,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import versions as versions_repo
from app.services.exports import plural

Sessions = sessionmaker[Session]

ONLY_DRAFTS = "Only a draft has steps left before publishing."
NO_PHASE = "That phase isn't in this version."
PARTLY = "Only partly supported: check its evidence first."
FIX_FIRST = "Fix the map problem first: {message}"
FIX_MAP = {"lint_failure", "quality_check"}


def _blockers(config: AppConfig, session: Session, version_id: str) -> list[PublishBlocker]:
    card = quality_action.card_for(config, session, version_id)
    assert card is not None
    return publish_action.blockers(config, session, version_id, card)


def _must_fix(found: list[PublishBlocker]) -> dict[str, str]:
    """Step id → why it can't be accepted as drafted (first reason wins)."""
    reasons: dict[str, str] = {}
    for b in found:
        if b.element_id and b.type == "lint_failure":
            reasons.setdefault(b.element_id, FIX_FIRST.format(message=b.message))
        elif b.element_id and b.type == "needs_check":
            reasons.setdefault(b.element_id, PARTLY)
    return reasons


def _draft(session: Session, version_id: str) -> Result[str]:
    """The version's engagement, if it is a draft."""
    version = versions_repo.get(session, version_id)
    if version is None:
        return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
    if version.state != DRAFT_STATE:
        return Err(ErrorKind.CONFLICT, NOT_A_DRAFT)
    return Ok(version.engagement_id)


def next_steps(config: AppConfig, sessions: Sessions, version_id: str) -> Result[NextSteps]:
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        if version.state != DRAFT_STATE:
            return Err(ErrorKind.CONFLICT, ONLY_DRAFTS)
        found = _blockers(config, session, version_id)
        pictures = map_repo.suggested_image_count(session, version_id)

    def items(types: set[str]) -> list[NextStepItem]:
        return [NextStepItem(message=b.message, element_id=b.element_id)
                for b in found if b.type in types]  # fmt: skip

    fix = items(FIX_MAP)
    check = items({"needs_check"})
    merges = items({"pending_merge"})
    unreviewed = [b.element_id for b in found if b.type == "unreviewed_element"]
    acceptable = len(set(unreviewed) - set(_must_fix(found)))
    steps: list[NextStep] = []
    if fix:
        steps.append(NextStep(
            key="fix_map", title=f"Fix {plural(len(fix), 'problem')} on the map",
            detail="These must be fixed before publishing. Each opens its step.",
            count=len(fix), bulk=0, items=fix))  # fmt: skip
    if check:
        steps.append(NextStep(
            key="check_steps", title=f"Check {plural(len(check), 'partly supported step')}",
            detail="The independent check found only part of each one in your sources: look at "
            "the evidence, then confirm or edit it.",
            count=len(check), bulk=0, items=check))  # fmt: skip
    if merges:
        steps.append(NextStep(
            key="merges", title=f"Decide {plural(len(merges), 'merge proposal')}",
            detail="Claude thought these might be one step described differently: merge them or "
            "keep them apart.",
            count=len(merges), bulk=0, items=merges))  # fmt: skip
    if unreviewed:
        detail = (
            f"Confirm, edit or reject each one, or accept the {acceptable} that need nothing "
            "fixed as drafted."
            if acceptable
            else "Fix the problems above first; then confirm, edit or reject these."
        )
        steps.append(NextStep(
            key="review_steps", title=f"Review {plural(len(unreviewed), 'step')}", detail=detail,
            count=len(unreviewed), bulk=acceptable, items=[]))  # fmt: skip
    if pictures:
        steps.append(NextStep(
            key="pictures",
            title=f"Keep or discard {plural(pictures, 'suggested picture')}",
            detail="Pictures found in your PDFs. Discard them all if none helps.",
            count=pictures, bulk=pictures, items=[]))  # fmt: skip
    if not found:
        steps = [NextStep(key="publish", title="Publish the map", detail="Every check is green.",
                          count=0, bulk=0, items=[])]  # fmt: skip
    return Ok(NextSteps(ready_to_publish=not found, steps=steps))


def accept_remaining(
    config: AppConfig, sessions: Sessions, version_id: str, phase_id: str | None
) -> Result[AcceptedSteps]:
    """Confirm the unreviewed steps (of one phase, or all) that need nothing fixed."""
    actor = actor_name(config)
    with session_scope(sessions) as session:
        match _draft(session, version_id):
            case Err() as err:
                return err
            case Ok(value=engagement_id):
                pass
        if phase_id and phase_id not in {p.id for p in map_repo.phases(session, version_id)}:
            return Err(ErrorKind.VALIDATION, NO_PHASE, {"field": "phase_id"})
        found = _blockers(config, session, version_id)
        waiting = {b.element_id for b in found if b.type == "unreviewed_element"}
        reasons = _must_fix(found)
        accepted: list[str] = []
        skipped: list[SkippedStep] = []
        for e in map_repo.elements(session, version_id):
            if e.id not in waiting or (phase_id and e.phase_id != phase_id):
                continue
            if e.id in reasons:
                skipped.append(SkippedStep(element_id=e.id, label=e.label, reason=reasons[e.id]))
                continue
            map_repo.update_element(session, e.id, {"review_status": ReviewStatus.CONFIRMED.value})
            accepted.append(e.id)
        if accepted:
            audit.record(session, actor=actor, action="Accepted remaining steps as drafted",
                         target_type="version", target_id=version_id,
                         engagement_id=engagement_id, version_id=version_id,
                         before={"review_status": ReviewStatus.DRAFT.value},
                         after={"count": len(accepted), "element_ids": accepted,
                                "phase_id": phase_id})  # fmt: skip
    if accepted:
        versions_action.lint_version(sessions, version_id)
    return Ok(AcceptedSteps(accepted=len(accepted), skipped=skipped))
