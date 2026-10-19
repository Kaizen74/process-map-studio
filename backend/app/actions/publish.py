"""Versions, publishing, reopening and exports (PRD §3.5 versions and locking, §5.9, §7.2, §7.3;
phase P7).

Publishing is refused with every blocker until the quality card's hard checks all pass; the
published version then never changes. Reopen deep-copies the latest published map into a new
draft whose reviewed steps stay locked. Exports are only of a published version with a green
card, rendered from the stored map with the stored card printed on top.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.actions import quality as quality_action
from app.actions import reality, redaction, system_trace
from app.actions import versions as versions_action
from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.enums import ElementKind, ReviewStatus, VersionState
from app.domain.models import (
    ChangeEntry,
    DraftAcceptance,
    ExportFile,
    PublishBlocker,
    ReviewProgress,
    SignalStrength,
    VersionDetail,
    VersionSummary,
)
from app.domain.quality import QualityCard
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import versions as versions_repo
from app.services import exports, signal

Sessions = sessionmaker[Session]

NOT_CURRENT_DRAFT = "Only the current draft can be published."
NOT_LATEST = "Only the latest published version can be reopened."
DRAFT_EXISTS = "There is already a draft. Review or refresh it instead."
NOT_EXPORTABLE = "Publish a version with a green quality card first."
UNKNOWN_FORMAT = "Choose md, json, csv or html."
STEP_KINDS = {ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value}
CHANGES = {
    "Confirmed step": "confirmed",
    "Edited step": "edited",
    "Rejected step": "rejected",
    "Added step": "added",
    "Restored step": "",
}
FILES = {
    "md": ("master-map.md", "text/markdown; charset=utf-8"),
    "json": ("graph.json", "application/json"),
    "csv": ("raci.csv", "text/csv; charset=utf-8"),
    "html": ("map.html", "text/html; charset=utf-8"),
}
CARD_CHECKS = {"Q1", "Q2", "Q7", "Q8", "Q9"}  # blockers not already listed one by one


def now() -> str:
    """Publishing time (UTC); tests fix it for the golden baselines."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _detail(session: Session, version_id: str) -> VersionDetail | None:
    found = versions_repo.row(session, version_id)
    if found is None:
        return None
    steps = [e for e in map_repo.elements(session, version_id) if e.kind in STEP_KINDS]
    total = len(steps)
    reviewed = sum(1 for e in steps if e.review_status != ReviewStatus.DRAFT.value)
    terms = redaction.name_replacements(session, found["engagement_id"])
    log = [
        ChangeEntry.model_validate({**entry, "step": redaction.hide(entry["step"], terms)})
        for entry in versions_repo.change_log(session, version_id)
    ]
    return VersionDetail(
        **found,
        signal=version_signal(session, version_id),
        review=ReviewProgress(reviewed=reviewed, total=total),
        acceptance=_acceptance(session, version_id, steps),
        change_log=log,
        quality_card=versions_repo.quality_card(session, version_id),
    )


def _acceptance(session: Session, version_id: str, steps: list[Any]) -> DraftAcceptance:
    """How much of Claude's draft Eric kept (deep review item 4). Eric's own steps are those marked
    added, or added in this version according to its audit log (so one he added and then
    rejected stays his); every other step is Claude's, counted by its review status."""
    added_here = {row["target_id"] for row in audit.list_for_version(session, version_id)
                  if row["action"] == "Added step" and row["target_type"] == "element"}  # fmt: skip
    mine = [e for e in steps if e.review_status == ReviewStatus.ADDED.value or e.id in added_here]
    claude = [e for e in steps if e not in mine]

    def count(status: ReviewStatus) -> int:
        return sum(1 for e in claude if e.review_status == status.value)

    return DraftAcceptance(
        drafted=len(claude),
        confirmed=count(ReviewStatus.CONFIRMED),
        edited=count(ReviewStatus.EDITED),
        rejected=count(ReviewStatus.REJECTED),
        unreviewed=count(ReviewStatus.DRAFT),
        added=len(mine),
    )


def list_versions(sessions: Sessions, engagement_id: str) -> Result[list[VersionSummary]]:
    with session_scope(sessions) as session:
        if engagements_repo.get(session, engagement_id) is None:
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(
            [
                VersionSummary(**r, signal=version_signal(session, r["id"]))
                for r in versions_repo.rows(session, engagement_id)
            ]
        )


def version_signal(session: Session, version_id: str) -> SignalStrength | None:
    """The version's signal strength, from the sources it was drafted from (P12)."""
    return signal.signal_strength(versions_repo.source_kinds(session, version_id))


def get_version(sessions: Sessions, version_id: str) -> Result[VersionDetail]:
    with session_scope(sessions) as session:
        detail = _detail(session, version_id)
    if detail is None:
        return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
    return Ok(detail)


def next_published_label(labels: list[str]) -> str:
    """v1.0 first, then v1.1, v1.2 … (PRD §3.5)."""
    minors = [int(m.group(1)) for label in labels if (m := re.fullmatch(r"v1\.(\d+)", label))]
    return f"v1.{max(minors) + 1}" if minors else "v1.0"


def _change_log(session: Session, version_id: str) -> list[dict[str, Any]]:
    """The last review action on each step while this was the draft, in process order."""
    last: dict[str, str] = {}
    for row in reversed(audit.list_for_version(session, version_id)):  # oldest first
        change = CHANGES.get(row["action"])
        if change is not None and row["target_type"] == "element":
            last[row["target_id"]] = change
    entries = []
    for element in map_repo.elements(session, version_id):
        change = last.get(element.id, "")
        if change and element.kind in STEP_KINDS:
            entries.append(
                {"change": change, "step": element.label, "stable_key": element.stable_key}
            )
    return entries


def blockers(
    config: AppConfig, session: Session, version_id: str, card: QualityCard
) -> list[PublishBlocker]:
    graph = versions_action.build_graph(session, version_id)
    assert graph is not None
    on_map = exports.on_the_map(graph)
    steps = [e for e in on_map.elements if e.kind in STEP_KINDS]
    found = [
        PublishBlocker(type="unreviewed_element", id=e.id, element_id=e.id,
                       message=f"“{e.label}” hasn't been reviewed yet.")
        for e in steps
        if e.review_status == ReviewStatus.DRAFT.value
    ]  # fmt: skip
    found += [
        PublishBlocker(type="needs_check", id=e.id, element_id=e.id,
                       message=f"“{e.label}” was only partly supported: check its evidence, "
                       "then confirm or edit it.")
        for e in steps
        if e.needs_check and e.review_status == ReviewStatus.DRAFT.value
    ]  # fmt: skip
    found += [
        PublishBlocker(type="pending_merge", id=p.id, element_id=None,
                       message=f"Merge decision waiting: “{p.proposed_label}”.")
        for p in map_repo.merge_proposals(session, version_id)
        if p.decision == "pending"
    ]  # fmt: skip
    suggested = map_repo.suggested_image_count(session, version_id)
    if suggested:
        found.append(PublishBlocker(type="suggested_image", id="images", element_id=None,
                                    message=f"{exports.plural(suggested, 'suggested image')} to "
                                    "keep or discard."))  # fmt: skip
    report = versions_action.lint_for(session, version_id)
    assert report is not None
    found += [
        PublishBlocker(type="lint_failure", id=f.rule, element_id=f.element_id, message=f.message)
        for f in report.failures
    ]
    found += [
        PublishBlocker(
            type="quality_check", id=c.id, element_id=None, message=f"{c.name}: {c.detail}"
        )
        for c in card.checks
        if c.id in CARD_CHECKS and c.status == "fail"
    ]
    return found


def publish(config: AppConfig, sessions: Sessions, version_id: str) -> Result[VersionDetail]:
    actor = actor_name(config)
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        if version.state != VersionState.DRAFT.value:
            return Err(ErrorKind.CONFLICT, NOT_CURRENT_DRAFT)
        card = quality_action.card_for(config, session, version_id)
        assert card is not None
        if not card.all_green:
            found = blockers(config, session, version_id, card)
            noun = exports.plural(len(found), "thing")
            return Err(
                ErrorKind.PUBLISH_BLOCKED,
                f"This draft can't be published yet: {noun} to fix.",
                {"blockers": [b.model_dump() for b in found]},
            )
        label = next_published_label(versions_repo.published_labels(session, version.engagement_id))
        system_trace.freeze(session, version_id)  # a published version never changes after this
        versions_repo.publish(
            session,
            version_id,
            label=label,
            published_at=now(),
            published_by=actor,
            quality_card=card.model_dump(mode="json"),
            change_log=_change_log(session, version_id),
        )
        if reality.enabled(config):  # the Reality snapshot is frozen with the version (§3.18.1)
            published = versions_repo.get(session, version_id)
            assert published is not None
            reality.freeze(session, published)
        audit.record(
            session,
            actor=actor,
            action="Published version",
            target_type="version",
            target_id=version_id,
            engagement_id=version.engagement_id,
            version_id=version_id,
            before={"label": version.label, "state": version.state},
            after={"label": label, "state": VersionState.PUBLISHED.value},
        )
        detail = _detail(session, version_id)
    assert detail is not None
    return Ok(detail)


def reopen(config: AppConfig, sessions: Sessions, version_id: str) -> Result[VersionDetail]:
    actor = actor_name(config)
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        latest = versions_repo.latest_published(session, version.engagement_id)
        if latest is None or latest["id"] != version_id:
            return Err(ErrorKind.CONFLICT, NOT_LATEST)
        if versions_repo.current_draft(session, version.engagement_id) is not None:
            return Err(ErrorKind.CONFLICT, DRAFT_EXISTS)
        labels = versions_repo.published_labels(session, version.engagement_id)
        label = f"{next_published_label(labels)} draft"
        draft = versions_repo.create_reopened(
            session, engagement_id=version.engagement_id, label=label, parent_id=version_id
        )
        versions_repo.copy_content(session, version_id, draft.id)
        audit.record(
            session,
            actor=actor,
            action="Reopened as new draft",
            target_type="version",
            target_id=draft.id,
            engagement_id=version.engagement_id,
            version_id=draft.id,
            before={"label": version.label},
            after={"label": label},
        )
        new_id = draft.id
    versions_action.lint_version(sessions, new_id)
    with session_scope(sessions) as session:
        detail = _detail(session, new_id)
    assert detail is not None
    return Ok(detail)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "process"


def export(config: AppConfig, sessions: Sessions, version_id: str, fmt: str) -> Result[ExportFile]:
    if fmt not in FILES:
        return Err(ErrorKind.NOT_FOUND, UNKNOWN_FORMAT)
    actor = actor_name(config)
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, versions_action.VERSION_MISSING)
        stored = versions_repo.quality_card(session, version_id)
        published = version.state in (VersionState.PUBLISHED.value, VersionState.SUPERSEDED.value)
        card = QualityCard.model_validate(stored) if stored else None
        if not published or card is None or not card.all_green:
            return Err(ErrorKind.CONFLICT, NOT_EXPORTABLE)
        graph = versions_action.build_graph(session, version_id)
        assert graph is not None
        data = quality_action.export_input(config, session, version_id, graph)
        assert data is not None
        data = data.model_copy(update={"quality_card": card})
        content = quality_action.render_exports(data)[fmt]
        name, media = FILES[fmt]
        filename = f"{slug(graph.process.name)}-{slug(version.label)}-{name}"
        audit.record(
            session,
            actor=actor,
            action=f"Exported {fmt}",
            target_type="version",
            target_id=version_id,
            engagement_id=version.engagement_id,
            version_id=version_id,
        )
    return Ok(ExportFile(filename=filename, media_type=media, content=content))
