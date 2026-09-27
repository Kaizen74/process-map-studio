"""S4 Assemble (PRD §3.7): the full map from the checked steps.

One call sees the process trigger and end point, the roles, and every step with the verified claims
it was built from (claims not tied to a step are listed too). Claude returns phases, edges and, per
step, RACI, decision rights, times, KPI, hand-offs, constraints, knowledge risk and AI flags.

Only verified claims count: every field is checked against the claims of its step before it is
kept (numbers must appear in them, roles must be named by them, names are scrubbed). A field that
fails is left empty and listed in the rejected-claims register with stage S4; the step itself
stays. Then, deterministically: start and end elements, the JD accountability test on decisions and
approvals (competing Accountable roles all marked contested, each with its evidence), decision
mechanisms for every decision and approval, and the G7 confidence of every step with its
breakdown.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.config import AppConfig
from app.db import session_scope
from app.domain import ai_schemas
from app.domain.enums import (
    AiBasis,
    DecisionMechanism,
    ElementKind,
    Provenance,
    SourceState,
    Stance,
    VerifierVerdict,
)
from app.domain.graph import (
    AiFlagRecord,
    ConstraintRecord,
    EdgeRecord,
    ElementRecord,
    EvidencePassage,
    EvidenceRecord,
    PhaseRecord,
    RaciRecord,
)
from app.domain.models import AiCallRecord, ClaimRecord, NameReplacement, RoleView, StanceFact
from app.domain.result import Err, ErrorKind, Ok, Result
from app.pipeline.context import AiContext, ai_failure, calls_in, record_calls, role_groups
from app.pipeline.s2_canonicalise import ClaimRef, claim_refs, claims_text
from app.pipeline.s3_calibrate import StepRef, accountable_facts, step_refs
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import versions as versions_repo
from app.services import ai_service, calibration, grounding, prompts

Sessions = sessionmaker[Session]

STAGE = "S4"
STAGE_ID = "S4_assemble"
START, END = "start", "end"
DECIDING = {ElementKind.DECISION.value, ElementKind.APPROVAL.value}
# Which register claim type a dropped field is listed under (PRD §3.5 claim types).
FIELD_TYPES = {
    "rule_or_threshold": "threshold",
    "escalation": "decision",
    "duration_text": "duration",
    "kpi": "kpi",
    "handoff_in": "handoff",
    "handoff_out": "handoff",
    "k_risk": "constraint",
}
FORMAT_FAILED = (
    "Claude's answer for 'Building the map' didn't match the expected format twice. Nothing was "
    "saved. Try again, or use Copy details to report it."
)


@dataclass(slots=True)
class S4Tally:
    phases: int = 0
    edges: int = 0
    dropped_edges: int = 0
    dropped_fields: int = 0
    dropped_flags: int = 0
    scrubbed: int = 0
    contested_steps: list[str] = field(default_factory=list)


def render(
    trigger: str,
    end_point: str,
    roles: list[RoleView],
    steps: list[StepRef],
    refs: list[ClaimRef],
    linked: dict[str, list[str]],
) -> str:
    esc = prompts.escape
    by_claim = {c.claim_id: c for c in refs}
    lines = [
        f'<process trigger="{esc(trigger)}" end_point="{esc(end_point)}"/>',
        "<roles>",
        *[f'<role name="{esc(r.name)}" aliases="{esc(", ".join(r.aliases))}"/>' for r in roles],
        "</roles>",
        "<steps>",
    ]
    for s in steps:
        lines.append(
            f'<step id="{s.ref}" kind="{esc(s.element.kind)}" lane="{esc(s.lane)}" '
            f'label="{esc(s.element.label)}" source_state="{esc(s.element.source_state)}" '
            f'divergence="{esc(", ".join(s.element.divergence_types))}">'
        )
        lines += [
            f'<claim_ref id="{by_claim[c].ref}"/>'
            for c in linked.get(s.element.id, [])
            if c in by_claim
        ]
        lines.append("</step>")
    lines += ["</steps>", "<claims>"]
    placed = {c for ids in linked.values() for c in ids}
    for c in refs:
        step = "" if c.claim_id in placed else ' unassigned="true"'
        speaker = f' speaker="{esc(", ".join(c.speakers))}"' if c.speakers else ""
        lines.append(
            f'<claim id="{c.ref}" kind="{esc(c.source_kind)}"{speaker}{step} '
            f'duration="{esc(str(c.record.payload.get("duration_text", "")))}" '
            f'threshold="{esc(str(c.record.payload.get("threshold", "")))}">'
            f"{esc(str(c.record.payload.get('text', '')))}</claim>"
        )
    lines.append("</claims>")
    return "\n".join(lines)


def blocks_for(
    trigger: str,
    end_point: str,
    roles: list[RoleView],
    steps: list[StepRef],
    refs: list[ClaimRef],
    linked: dict[str, list[str]],
) -> list[dict[str, object]]:
    return [{"type": "text", "text": render(trigger, end_point, roles, steps, refs, linked)}]


def _role_id(name: str, roles: list[RoleView]) -> str | None:
    key = grounding.normalise_text(name)
    for role in roles:
        if key and key in {grounding.normalise_text(n) for n in (role.name, *role.aliases)}:
            return role.id
    return None


def _minutes_found(value: float | None, text: str) -> bool:
    if value is None:
        return True
    written = str(int(value)) if float(value).is_integer() else str(value)
    return written in grounding.numbers_in(text)


class _Gate:
    """Checks one step's fields against its claims; what fails is dropped and listed."""

    def __init__(
        self,
        step: StepRef,
        claims: list[ClaimRef],
        roles: list[RoleView],
        groups: list[list[str]],
        terms: list[NameReplacement],
        tally: S4Tally,
    ) -> None:
        self.step, self.claims, self.roles, self.groups = step, claims, roles, groups
        self.terms, self.tally = terms, tally
        self.text = claims_text(claims)
        self.rejected: list[ClaimRecord] = []

    def reject(self, claim_type: str, text: str, reason: str, guardrail: str) -> None:
        self.tally.dropped_fields += 1
        first = self.claims[0].record if self.claims else None
        self.rejected.append(
            ClaimRecord(
                source_id=first.source_id if first else "",
                stage=STAGE,
                claim_type=claim_type,
                payload={"text": f"{self.step.element.label}: {text}"},
                segment_ids=[s for c in self.claims for s in c.record.segment_ids],
                quote="",
                provenance=Provenance.OBSERVED.value,
                basis="",
                verification_status="rejected",
                rejection_reason=reason,
                rejection_guardrail=guardrail,
            )
        )

    def scrub(self, text: str) -> str:
        result = grounding.redact_text(text, self.terms)
        self.tally.scrubbed += result.hits
        return result.text

    def text_field(self, name: str, value: str) -> str:
        value = self.scrub(value.strip())
        outcome = grounding.verify_numbers(value, self.text)
        if outcome.passed:
            return value
        self.reject(FIELD_TYPES.get(name, "activity"), value, outcome.reason, outcome.guardrail)
        return ""

    def minutes(self, what: str, value: float | None) -> float | None:
        if _minutes_found(value, self.text):
            return value
        self.reject(
            "duration", f"{what} {value:g} min", f"number not found in claims: {value:g}", "G5"
        )
        return None

    def role(self, name: str, claim_type: str) -> str | None:
        """A role named by the answer: names become their mapped role first (G10)."""
        name = self.scrub(name.strip())
        if not name:
            return None
        role_id = _role_id(name, self.roles)
        outcome = grounding.verify_roles([name], self.text, self.groups)
        if role_id is not None and outcome.passed:
            return role_id
        reason = outcome.reason if not outcome.passed else f"not a known role: {name}"
        self.reject(claim_type, name, reason, "G5")
        return None


def assemble(
    config: AppConfig,
    sessions: Sessions,
    ctx: AiContext,
    *,
    version_id: str,
    job_id: str | None = None,
) -> Result[S4Tally]:
    tally = S4Tally()
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, "That version doesn't exist.")
        engagement = engagements_repo.get(session, version.engagement_id)
        assert engagement is not None
        steps = step_refs(session, version_id)
        refs = claim_refs(session, version_id)
        linked = map_repo.element_claims(session, version_id)
        roles = engagements_repo.list_roles(session, version.engagement_id)
        groups = role_groups(session, version.engagement_id)
        terms = redaction.name_replacements(session, version.engagement_id)
    if not steps:
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
    trigger = redaction.hide(engagement.trigger, terms)
    end_point = redaction.hide(engagement.end_point, terms)
    call = ai_service.StageCall(
        stage_id=STAGE_ID,
        prompt_version=prompt.version,
        system=prompt.text,
        blocks=blocks_for(trigger, end_point, roles, steps, refs, linked),
        output_model=ai_schemas.S4Output,
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
    output = ai_schemas.S4Output.model_validate(answer.data)

    by_step = {s.ref: s for s in steps}
    by_ref = {c.ref: c for c in refs}
    by_claim = {c.claim_id: c for c in refs}
    rejected: list[ClaimRecord] = []
    with session_scope(sessions) as session:
        # Start and end come from the scope card (Setup).
        [start, end] = map_repo.add_elements(
            session,
            version_id,
            [
                ElementRecord(
                    stable_key=START, kind=ElementKind.START.value, label=trigger or "Start",
                    provenance=Provenance.OBSERVED.value, source_state=SourceState.NOT_ASSESSED,
                ),
                ElementRecord(
                    stable_key=END, kind=ElementKind.END.value, label=end_point or "End",
                    provenance=Provenance.OBSERVED.value, source_state=SourceState.NOT_ASSESSED,
                ),
            ],
        )  # fmt: skip
        ids = {START: start.id, END: end.id} | {s.ref: s.element.id for s in steps}
        stances = map_repo.evidence(session, version_id)

        # Phases: each step in at most one, in the order given.
        phase_of: dict[str, str] = {}
        for order, phase in enumerate(output.phases, start=1):
            members = [
                r for r in dict.fromkeys(phase.step_refs) if r in by_step and r not in phase_of
            ]
            if not members:
                continue
            text = claims_text(
                [
                    by_claim[c]
                    for r in members
                    for c in linked.get(by_step[r].element.id, [])
                    if c in by_claim
                ]
            )
            window = grounding.redact_text(phase.time_window, terms).text
            if not grounding.verify_numbers(window, text).passed:
                window = ""
            [record] = map_repo.add_phases(
                session,
                version_id,
                [PhaseRecord(name=grounding.redact_text(phase.name, terms).text, time_window=window,
                             sort_order=order)],
            )  # fmt: skip
            tally.phases += 1
            for r in members:
                phase_of[r] = record.id

        # Per step: fields checked against the step's claims.
        answered = {s.step_ref: s for s in output.steps if s.step_ref in by_step}
        for ref, step in by_step.items():
            element = step.element
            detail = answered.get(ref)
            own = [by_claim[c] for c in linked.get(element.id, []) if c in by_claim]
            extra = [by_ref[c] for c in (detail.claim_refs if detail else []) if c in by_ref]
            extra = [c for c in extra if c not in own]
            gate = _Gate(step, own + extra, roles, groups, terms, tally)
            if extra:
                map_repo.link_claims(session, element.id, [c.claim_id for c in extra])
            fields: dict[str, object] = {"phase_id": phase_of.get(ref)}
            mechanism = DecisionMechanism.NONE.value
            if detail is not None:
                for name in ("rule_or_threshold", "escalation", "duration_text", "kpi",
                             "handoff_in", "handoff_out", "k_risk"):  # fmt: skip
                    fields[name] = gate.text_field(name, getattr(detail, name))
                fields["work_min"] = gate.minutes("work", detail.work_min)
                fields["wait_min"] = gate.minutes("wait", detail.wait_min)
                fields["complexity"] = detail.complexity or None
                if element.kind == ElementKind.DECISION.value:
                    fields["decider_role_id"] = gate.role(detail.decider_role, "decision")
                mechanism = detail.decision_mechanism
            if element.kind in DECIDING and mechanism == DecisionMechanism.NONE.value:
                # Constraint 7: every decision and approval is classified; unsure → judgment.
                stated = {str(c.record.payload.get("mechanism", "")) for c in own}
                mechanism = (
                    DecisionMechanism.RULE_BASED.value
                    if stated == {DecisionMechanism.RULE_BASED.value}
                    or stated == {DecisionMechanism.RULE_BASED.value, DecisionMechanism.NONE.value}
                    else DecisionMechanism.JUDGMENT.value
                )
            if element.kind not in DECIDING:
                mechanism = DecisionMechanism.NONE.value
            fields["decision_mechanism"] = mechanism

            # RACI, then the JD accountability test on decisions and approvals.
            entries: dict[tuple[str, str], RaciRecord] = {}
            for entry in detail.raci if detail else []:
                role_id = gate.role(entry.role, "raci")
                if role_id is not None:
                    entries.setdefault(
                        (role_id, entry.letter),
                        RaciRecord(element_id=element.id, role_id=role_id, letter=entry.letter),
                    )
            competing: dict[str, list[str]] = {}
            if element.kind in DECIDING:
                test = calibration.jd_accountability_test(accountable_facts(step))
                if test.contested:
                    tally.contested_steps.append(element.label)
                    for name, sources in test.sources_by_role.items():
                        role_id = _role_id(name, roles)
                        if role_id is not None:
                            competing[role_id] = sources
                    entries = {k: v for k, v in entries.items() if k[1] != "A" or k[0] in competing}
                    for role_id in competing:
                        entries[(role_id, "A")] = RaciRecord(
                            element_id=element.id, role_id=role_id, letter="A", contested=True
                        )
            saved = map_repo.add_raci(session, list(entries.values()))
            # Each competing A carries the passages of the claims that name it.
            raci_links = []
            for entry_saved in saved:
                if entry_saved.role_id not in competing:
                    continue
                for c in own:
                    if c.record.source_id in competing[entry_saved.role_id]:
                        raci_links += [
                            EvidenceRecord(raci_id=entry_saved.id, segment_id=s,
                                           source_kind=c.source_kind,
                                           stance=Stance.SUPPORTS.value, verified=True,
                                           quote=c.record.quote)
                            for s in c.record.segment_ids
                        ]  # fmt: skip
            map_repo.add_evidence(session, raci_links)

            # Constraints and the AI flag.
            constraints = []
            for constraint in detail.constraints if detail else []:
                cited = [by_ref[c] for c in constraint.claim_refs if c in by_ref]
                text = gate.scrub(constraint.text)
                outcome = grounding.verify_numbers(text, claims_text(cited))
                if not cited or not outcome.passed:
                    gate.reject(
                        "constraint",
                        text,
                        outcome.reason or "cites no claim",
                        "G5" if cited else "G3",
                    )
                    continue
                constraints.append(
                    ConstraintRecord(
                        element_id=element.id, text=text,
                        provenance=Provenance.OBSERVED.value
                        if any(c.record.provenance == Provenance.OBSERVED.value for c in cited)
                        else Provenance.INFERRED.value,
                        cause_type=(
                            None if constraint.cause_type == "none" else constraint.cause_type
                        ),
                        is_key=constraint.is_key,
                    )
                )  # fmt: skip
            map_repo.add_constraints(session, constraints)
            flags = detail.ai_flags[:1] if detail else []
            for flag in flags:
                automate = flag.basis == AiBasis.RULE_BASED_AUTOMATE_CANDIDATE.value
                if automate and mechanism == DecisionMechanism.JUDGMENT.value:
                    tally.dropped_flags += 1  # constraint 7: never on a judgment step
                    continue
                texts = [gate.scrub(t) for t in (flag.input, flag.output, flag.handoff)]
                if not all(grounding.verify_numbers(t, gate.text).passed for t in texts):
                    tally.dropped_flags += 1
                    continue
                map_repo.add_ai_flags(
                    session,
                    [AiFlagRecord(element_id=element.id, component=flag.component, input=texts[0],
                                  output=texts[1], handoff=texts[2], basis=flag.basis)],
                )  # fmt: skip

            fields["confidence"], fields["confidence_breakdown"] = _confidence(
                session, element, own, stances
            )
            map_repo.update_element(session, element.id, fields)
            rejected += gate.rejected

        # Edges between known ends, labelled, no duplicates.
        seen: set[tuple[str, str, str]] = set()
        edges = []
        for edge in output.edges:
            if edge.from_ref not in ids or edge.to_ref not in ids or edge.from_ref == END:
                tally.dropped_edges += 1
                continue
            key = (edge.from_ref, edge.to_ref, edge.kind)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                EdgeRecord(
                    from_element_id=ids[edge.from_ref], to_element_id=ids[edge.to_ref],
                    kind=edge.kind, label=grounding.redact_text(edge.label, terms).text,
                )
            )  # fmt: skip
        map_repo.add_edges(session, version_id, edges)
        tally.edges = len(edges)
        claims_repo.add_claims(session, version_id, [r for r in rejected if r.source_id])
    return Ok(tally)


def _confidence(
    session: Session,
    element: ElementRecord,
    own: list[ClaimRef],
    all_passages: list[EvidencePassage],
) -> tuple[float | None, list[dict[str, object]]]:
    """G7 from the stored evidence (stances) and the verifier's verdicts on the step's claims."""
    if element.provenance not in {Provenance.OBSERVED.value, Provenance.INFERRED.value}:
        return None, []
    passages = [p for p in all_passages if p.evidence.element_id == element.id]
    facts = [
        StanceFact(
            source_id=p.source_id, source_kind=p.evidence.source_kind, stance=p.evidence.stance
        )
        for p in passages
    ]
    found = set(claims_repo.verdicts(session, [c.claim_id for c in own]).values())
    if VerifierVerdict.PARTIAL.value in found:
        verdict = VerifierVerdict.PARTIAL.value
    elif found == {VerifierVerdict.SUPPORTED.value}:
        verdict = VerifierVerdict.SUPPORTED.value
    else:
        verdict = VerifierVerdict.NOT_RUN.value
    contested = element.source_state in {
        SourceState.CONTESTED.value,
        SourceState.TRACE_CONTRADICTED.value,
    }
    result = calibration.derive_confidence(
        element.provenance, calibration.supporting_sources(facts), verdict, contested
    )
    return result.value, [t.model_dump() for t in result.breakdown]
