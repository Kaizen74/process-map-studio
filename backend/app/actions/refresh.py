"""Refresh draft from sources (PRD §3.5 versions and locking; phase P6).

The draft job runs every stage again into a temporary version (state `building`); `fold` then
moves the fresh map into the draft being refreshed. Steps Eric confirmed, edited, added or
rejected stay exactly as they are (constraint 8); everything else is replaced by the fresh run,
and a replaced step's pictures follow it to its fresh successor.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.enums import ReviewStatus
from app.domain.graph import ElementRecord
from app.domain.models import RefreshChanges, StepRename
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import images as images_repo
from app.repositories import versions as versions_repo

KEPT = {
    ReviewStatus.CONFIRMED.value,
    ReviewStatus.EDITED.value,
    ReviewStatus.ADDED.value,
    ReviewStatus.REJECTED.value,
}
STEP_KINDS = {"activity", "decision", "approval"}


def changes(old: list[ElementRecord], fresh: list[ElementRecord], kept: int) -> RefreshChanges:
    """Among the steps Eric hadn't reviewed, what the fresh run drafted differently (by step key,
    labels in process order): drift between runs made at different times made visible."""
    before = {e.stable_key: e.label for e in old if e.kind in STEP_KINDS}
    unreviewed = {
        e.stable_key: e.label for e in old if e.kind in STEP_KINDS and e.review_status not in KEPT
    }
    after = {e.stable_key: e.label for e in fresh if e.kind in STEP_KINDS}
    return RefreshChanges(
        kept=kept,
        new_steps=[label for key, label in after.items() if key not in before],
        no_longer_drafted=[label for key, label in unreviewed.items() if key not in after],
        renamed=[
            StepRename(before=label, after=after[key])
            for key, label in unreviewed.items()
            if key in after and after[key] != label
        ],
    )


def fold(session: Session, draft_id: str, fresh_id: str) -> RefreshChanges:
    """Fold the fresh version into the draft; returns how many steps were kept as reviewed and
    what changed among the others."""
    old = map_repo.elements(session, draft_id)
    keep = {e.id: e for e in old if e.review_status in KEPT}
    replaced = [e for e in old if e.id not in keep]
    fresh = map_repo.elements(session, fresh_id)
    keep_by_key = {e.stable_key: e.id for e in keep.values()}
    changed = changes(old, [f for f in fresh if f.stable_key not in keep_by_key], len(keep))
    dropped = {f.id: keep_by_key[f.stable_key] for f in fresh if f.stable_key in keep_by_key}
    fresh_by_key = {f.stable_key: f.id for f in fresh if f.id not in dropped}
    successor = {e.id: fresh_by_key[e.stable_key] for e in replaced if e.stable_key in fresh_by_key}
    answered = {q.question for q in map_repo.questions(session, draft_id) if q.status == "answered"}
    old_phases = {p.id: p.name for p in map_repo.phases(session, draft_id)}
    fresh_phases = {p.name: p.id for p in map_repo.phases(session, fresh_id)}

    # The draft's lines around its kept steps stay; their other end follows its fresh successor.
    own_exits: set[str] = set()
    for edge in map_repo.edges(session, draft_id):
        start, end = edge.from_element_id, edge.to_element_id
        new_start = start if start in keep else successor.get(start)
        new_end = end if end in keep else successor.get(end)
        if (start not in keep and end not in keep) or new_start is None or new_end is None:
            map_repo.delete_edge(session, edge.id)
            continue
        if (new_start, new_end) != (start, end):
            map_repo.update_edge(
                session, edge.id, {"from_element_id": new_start, "to_element_id": new_end}
            )
        if start in keep:
            own_exits.add(start)

    # The fresh lines: into a dropped step → its kept twin; out of it only if the kept step has no
    # lines of its own out (Eric's structure around his reviewed steps wins).
    for edge in map_repo.edges(session, fresh_id):
        start, end = edge.from_element_id, edge.to_element_id
        new_start, new_end = dropped.get(start, start), dropped.get(end, end)
        if start in dropped and new_start in own_exits:
            map_repo.delete_edge(session, edge.id)
        elif (new_start, new_end) != (start, end):
            map_repo.update_edge(
                session, edge.id, {"from_element_id": new_start, "to_element_id": new_end}
            )
    for fresh_step, kept_step in dropped.items():
        map_repo.move_questions(session, [fresh_step], kept_step)
    # The fresh claims behind a dropped twin go with it: the kept step has its own claims.
    fresh_claims = map_repo.element_claims(session, fresh_id)
    twin_claims = [c for step in dropped for c in fresh_claims.get(step, [])]
    map_repo.delete_elements(session, list(dropped))
    claims_repo.delete_claims(session, twin_claims)

    # A replaced step's pictures (and Eric's keep or discard of them) go to its fresh successor.
    images_repo.move(session, successor)

    # Out with the draft's replaced content, in with the fresh.
    versions_repo.clear_for_refresh(session, draft_id, set(keep))
    map_repo.delete_elements(session, [e.id for e in replaced])
    versions_repo.move_content(session, fresh_id, draft_id)
    for step in keep.values():
        name = old_phases.get(step.phase_id or "")
        if name is not None and name in fresh_phases:
            map_repo.update_element(session, step.id, {"phase_id": fresh_phases[name]})
    versions_repo.delete_unused_phases(session, draft_id)

    # Tidy: no line from a step to itself, no second line with the same ends and kind.
    seen: set[tuple[str, str, str]] = set()
    for edge in map_repo.edges(session, draft_id):
        key = (edge.from_element_id, edge.to_element_id, edge.kind)
        if edge.from_element_id == edge.to_element_id or key in seen:
            map_repo.delete_edge(session, edge.id)
        seen.add(key)
    for q in map_repo.questions(session, draft_id):
        if q.question in answered and q.status == "open":
            map_repo.set_question_status(session, q.id, "answered")
    return changed
