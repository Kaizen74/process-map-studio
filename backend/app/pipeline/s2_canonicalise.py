"""S2 Canonicalise (PRD §3.7): verified claims from every source → the steps of the draft map.

One call sees every verified claim (short sentences, never whole sources) with call-local IDs
(`c1`, `c2` …) and source IDs (`s1` …), plus the known roles. Claude groups the claims into steps,
names each step's lane role and may propose merges. Each step is checked before it is kept:
it must cite claims that were supplied (G3), numbers in its label must appear in its claims and
its lane role must be named by them (G5), and names are scrubbed (G10). A failing step is stored
as a rejected claim of stage S2 and never becomes an element.

Merge proposals at 0.80 similarity or above are merged now and listed as accepted; below that the
steps stay separate and the proposal waits for Eric (PRD §9 assumption 8).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.config import AppConfig
from app.db import session_scope
from app.domain import ai_schemas
from app.domain.enums import MergeDecision, Provenance
from app.domain.graph import ElementRecord, MergeGroup, MergeProposalRecord
from app.domain.models import AiCallRecord, CheckOutcome, ClaimRecord, NameReplacement, RoleView
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls, role_groups
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import ai_service, grounding, prompts

Sessions = sessionmaker[Session]

STAGE = "S2"
STAGE_ID = "S2_canonicalise"
PRE_MERGE = 0.80
FORMAT_FAILED = (
    "Claude's answer for 'Comparing sources' didn't match the expected format twice. Nothing was "
    "saved. Try again, or use Copy details to report it."
)


@dataclass(slots=True)
class S2Tally:
    steps: int = 0
    rejected: int = 0
    merged: int = 0
    pending_merges: int = 0
    roles_created: int = 0
    scrubbed: int = 0


@dataclass(frozen=True, slots=True)
class ClaimRef:
    ref: str
    claim_id: str
    record: ClaimRecord
    source_ref: str
    source_kind: str
    speakers: tuple[str, ...] = ()  # roles of the speakers of the cited passages


def _field(record: ClaimRecord, name: str) -> str:
    value = record.payload.get(name, "")
    return value if isinstance(value, str) else ""


def claim_refs(session: Session, version_id: str) -> list[ClaimRef]:
    """The verified claims as the call names them: `c1…` in stored order, sources `s1…` in the
    order they first appear."""
    rows = claims_repo.verified_rows(session, version_id)
    speaking = sources_repo.speaker_roles(session, [s for _, r in rows for s in r.segment_ids])
    source_refs: dict[str, str] = {}
    kinds: dict[str, str] = {}
    out = []
    for n, (claim_id, record) in enumerate(rows, start=1):
        if record.source_id not in source_refs:
            source_refs[record.source_id] = f"s{len(source_refs) + 1}"
            source = sources_repo.get(session, record.source_id)
            kinds[record.source_id] = source.kind if source else ""
        out.append(
            ClaimRef(
                ref=f"c{n}",
                claim_id=claim_id,
                record=record,
                source_ref=source_refs[record.source_id],
                source_kind=kinds[record.source_id],
                speakers=tuple(
                    dict.fromkeys(speaking[s] for s in record.segment_ids if s in speaking)
                ),
            )
        )
    return out


def render(refs: list[ClaimRef], roles: list[RoleView]) -> str:
    esc = prompts.escape
    lines = ["<roles>"]
    lines += [f'<role name="{esc(r.name)}" aliases="{esc(", ".join(r.aliases))}"/>' for r in roles]
    lines += ["</roles>", "<claims>"]
    for c in refs:
        attrs = {
            "id": c.ref,
            "source": c.source_ref,
            "kind": c.source_kind,
            "speaker": ", ".join(c.speakers),
            "type": c.record.claim_type,
            "responsible": _field(c.record, "responsible_role"),
            "accountable": _field(c.record, "accountable_role"),
            "decider": _field(c.record, "decider_role"),
            "mechanism": _field(c.record, "mechanism"),
            "duration": _field(c.record, "duration_text"),
            "threshold": _field(c.record, "threshold"),
        }
        rendered = " ".join(f'{k}="{esc(v)}"' for k, v in attrs.items())
        lines.append(f"<claim {rendered}>{esc(_field(c.record, 'text'))}</claim>")
    lines.append("</claims>")
    return "\n".join(lines)


def blocks_for(refs: list[ClaimRef], roles: list[RoleView]) -> list[dict[str, object]]:
    return [{"type": "text", "text": render(refs, roles)}]


def claims_text(claims: list[ClaimRef]) -> str:
    """What a step may be checked against: its claims' sentences, times, thresholds and roles,
    and the roles of the people speaking in the passages they cite (as for S1 claims)."""
    parts = []
    for c in claims:
        parts += list(c.speakers)
        parts += [
            _field(c.record, name)
            for name in (
                "text",
                "duration_text",
                "threshold",
                "responsible_role",
                "accountable_role",
                "decider_role",
            )
        ]
    return "\n".join(p for p in parts if p)


def check_step(
    step: ai_schemas.S2Step, by_ref: dict[str, ClaimRef], groups: list[list[str]]
) -> CheckOutcome:
    """G3 (claims supplied) → G5 numbers in the label → G5 lane role named by the claims."""
    if not step.claim_refs or any(r not in by_ref for r in step.claim_refs):
        return CheckOutcome(
            passed=False, guardrail="G3", reason="cites a claim that wasn't provided"
        )
    cited = claims_text([by_ref[r] for r in step.claim_refs])
    outcome = grounding.verify_numbers(step.label, cited)
    if not outcome.passed:
        return outcome
    return grounding.verify_roles([step.lane_role], cited, groups)


def stable_key(label: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-") or "step"
    key, n = base, 2
    while key in taken:
        key, n = f"{base}-{n}", n + 1
    taken.add(key)
    return key


def _role_for(
    name: str, roles: list[RoleView], new_roles: list[ai_schemas.S2Role]
) -> tuple[RoleView | None, ai_schemas.S2Role | None]:
    """The known role a lane name refers to, or the new role Claude listed for it."""
    key = grounding.normalise_text(name)
    for role in roles:
        if key in {grounding.normalise_text(n) for n in (role.name, *role.aliases)}:
            return role, None
    for new in new_roles:
        if key in {grounding.normalise_text(n) for n in (new.name, *new.aliases)}:
            return None, new
    return None, ai_schemas.S2Role(name=" ".join(name.split()), aliases=[])


def _scrub(text: str, terms: list[NameReplacement]) -> tuple[str, int]:
    result = grounding.redact_text(text, terms)
    return result.text, result.hits


class _Groups:
    """Union-find over step refs, for merges at or above the threshold."""

    def __init__(self, refs: list[str]) -> None:
        self.parent = {r: r for r in refs}

    def find(self, ref: str) -> str:
        while self.parent[ref] != ref:
            ref = self.parent[ref]
        return ref

    def union(self, refs: list[str]) -> None:
        root = self.find(refs[0])
        for other in refs[1:]:
            self.parent[self.find(other)] = root


def canonicalise(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[S2Tally]:
    tally = S2Tally()
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, "That version doesn't exist.")
        refs = claim_refs(session, version_id)
        roles = engagements_repo.list_roles(session, version.engagement_id)
        terms = redaction.name_replacements(session, version.engagement_id)
        groups = role_groups(session, version.engagement_id)
    if not refs:
        return Ok(tally)  # nothing verified, nothing to map
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
    call = ai_service.StageCall(
        stage_id=STAGE_ID,
        prompt_version=prompt.version,
        system=prompt.text,
        blocks=blocks_for(refs, roles),
        output_model=ai_schemas.S2Output,
        model=ctx.model,
        repair_prompt=repair.text,
        effort=ctx.effort,
        structured_outputs=ctx.structured_outputs,
    )
    result = ai_service.call_claude(ctx.conn, call)
    used: list[AiCallRecord] = result.value.calls if isinstance(result, Ok) else calls_in(result)
    with session_scope(sessions) as session:
        record_calls(session, job_id, used)
    match result:
        case Err(kind=ErrorKind.AI_FORMAT) as err:
            return Err(ErrorKind.AI_FORMAT, FORMAT_FAILED, err.details)
        case Err() as err:
            return ai_failure(err)
        case Ok(value=answer):
            pass
    output = ai_schemas.S2Output.model_validate(answer.data)
    by_ref = {c.ref: c for c in refs}
    # G10 first: a name anywhere in the answer becomes its mapped role before anything else.
    new_roles = []
    for listed in output.new_roles:
        name, hits = _scrub(listed.name, terms)
        aliases = [_scrub(a, terms) for a in listed.aliases]
        tally.scrubbed += hits + sum(h for _, h in aliases)
        new_roles.append(ai_schemas.S2Role(name=name, aliases=[a for a, _ in aliases]))
    output = output.model_copy(update={"new_roles": new_roles})
    new_groups = groups + [[r.name, *r.aliases] for r in output.new_roles]

    # Check every step; scrub names from what is kept.
    kept: dict[str, ai_schemas.S2Step] = {}
    rejected: list[ClaimRecord] = []
    for step in output.steps:
        label, hits = _scrub(step.label, terms)
        lane, lane_hits = _scrub(step.lane_role, terms)
        tally.scrubbed += hits + lane_hits
        step = step.model_copy(update={"label": label, "lane_role": lane})
        outcome = check_step(step, by_ref, new_groups)
        if outcome.passed and step.ref not in kept:
            kept[step.ref] = step
            continue
        cited = [by_ref[r] for r in step.claim_refs if r in by_ref]
        rejected.append(
            ClaimRecord(
                source_id=(cited[0] if cited else refs[0]).record.source_id,
                stage=STAGE,
                claim_type=step.kind,
                payload={"text": label, "claim_refs": list(step.claim_refs), "scrubbed": hits},
                segment_ids=[s for c in cited for s in c.record.segment_ids],
                quote="",
                provenance=Provenance.OBSERVED.value,
                basis="",
                verification_status="rejected",
                rejection_reason=outcome.reason or "the same step was listed twice",
                rejection_guardrail=outcome.guardrail or "G3",
            )
        )

    # Merge proposals: only between kept steps; at or above the threshold, merged now.
    union = _Groups(list(kept))
    proposals: list[tuple[list[str], str, float]] = []
    for merge in output.merge_proposals:
        steps = list(dict.fromkeys(r for r in merge.step_refs if r in kept))
        label, hits = _scrub(merge.proposed_label, terms)
        tally.scrubbed += hits
        merged_text = claims_text([by_ref[c] for r in steps for c in kept[r].claim_refs])
        if len(steps) < 2 or not grounding.verify_numbers(label, merged_text).passed:
            continue
        similarity = min(max(merge.similarity, 0.0), 1.0)
        if similarity >= PRE_MERGE:
            union.union(steps)
        proposals.append((steps, label, similarity))

    merged_label = {
        union.find(steps[0]): label for steps, label, sim in proposals if sim >= PRE_MERGE
    }
    groups_in_order: dict[str, list[str]] = {}
    for ref in kept:
        groups_in_order.setdefault(union.find(ref), []).append(ref)

    now = datetime.now(UTC).isoformat(timespec="seconds")
    with session_scope(sessions) as session:
        known = engagements_repo.list_roles(session, version.engagement_id)
        taken: set[str] = set()
        for root, members in groups_in_order.items():
            first = kept[members[0]]
            role, new = _role_for(first.lane_role, known, output.new_roles)
            if role is None and new is not None:
                role = engagements_repo.create_role(
                    session,
                    version.engagement_id,
                    name=new.name,
                    aliases=new.aliases,
                    is_system=False,
                )
                known.append(role)
                tally.roles_created += 1
            claim_ids = list(
                dict.fromkeys(by_ref[c].claim_id for m in members for c in kept[m].claim_refs)
            )
            observed = any(
                by_ref[c].record.provenance == Provenance.OBSERVED.value
                for m in members
                for c in kept[m].claim_refs
            )
            label = merged_label.get(root, first.label)
            [element] = map_repo.add_elements(
                session,
                version_id,
                [
                    ElementRecord(
                        stable_key=stable_key(label, taken),
                        kind=first.kind,
                        label=label,
                        lane_role_id=role.id if role else None,
                        provenance=(
                            Provenance.OBSERVED.value if observed else Provenance.INFERRED.value
                        ),
                    )
                ],
            )
            map_repo.link_claims(session, element.id, claim_ids)
            tally.steps += 1

        def group_of(ref: str) -> MergeGroup:
            """One merged step as drafted, so the Merge tab can show it and Split restore it."""
            step = kept[ref]
            role, _ = _role_for(step.lane_role, known, output.new_roles)
            return MergeGroup(
                label=step.label,
                kind=step.kind,
                lane_role_id=role.id if role else None,
                claim_ids=list(dict.fromkeys(by_ref[c].claim_id for c in step.claim_refs)),
            )

        map_repo.add_merge_proposals(
            session,
            version_id,
            [
                MergeProposalRecord(
                    claim_ids=list(
                        dict.fromkeys(by_ref[c].claim_id for r in steps for c in kept[r].claim_refs)
                    ),
                    proposed_label=label,
                    similarity=similarity,
                    decision=(
                        MergeDecision.ACCEPTED.value
                        if similarity >= PRE_MERGE
                        else MergeDecision.PENDING.value
                    ),
                    decided_at=now if similarity >= PRE_MERGE else None,
                    claim_groups=[group_of(r) for r in steps],
                )
                for steps, label, similarity in proposals
            ],
        )
        claims_repo.add_claims(session, version_id, rejected)
    tally.rejected = len(rejected)
    tally.merged = sum(1 for _, _, s in proposals if s >= PRE_MERGE)
    tally.pending_merges = len(proposals) - tally.merged
    return Ok(tally)
