"""Gap analysis A, documents vs practice (PRD §3.11.1; phase P10). Advisory: nothing here changes
the map; the findings are stored as a report for Eric to disposition.

1. `divergence_set` (no AI): every step whose source state is contested, documented-only,
   practiced-only or trace-contradicted, or that has a contested RACI entry, with how each source
   stands on it, the passages behind those stances (names hidden) and the divergence notes.
2. `synthesise` (`GA_internal`): Claude sees only that set and its passages.
3. `check` (no AI): the §3.8 checks on every finding and evidence item — G3 passage given and step
   in the set, G4 quote found in its passage, G5 numbers and roles found in the cited passages —
   plus evidence from both sides (documents and practice; a side that is silent on every step
   the finding names counts as that side's evidence), and a basis citing interview passages for
   every pattern or likely cause. Names are replaced by roles (G10).
4. `verify` (`GA_verify`, follows the verifier switch): `not_supported` → rejected `GAV`;
   `partial` or no verdict → kept with "needs check".
5. `report` (no AI): severity by `gap.severity_internal`; provenance `O` for facts, `I` otherwise.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import PurePath

from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions import versions as versions_action
from app.domain import ai_schemas
from app.domain.enums import Guardrail, VerifierVerdict
from app.domain.gap import GapEvidence, NewGapFinding
from app.domain.graph import GraphElement
from app.domain.models import NameReplacement, PromptSegment
from app.domain.result import Err, Ok, Result
from app.pipeline import s1_extract
from app.pipeline.context import AiContext, call_stage, role_groups
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import gap, grounding, prompts, sensemaking

Sessions = sessionmaker[Session]

STAGE_ID = "GA_internal"
VERIFY_STAGE = "GA_verify"
DIVERGENT_STATES = ("contested", "documented_only", "practiced_only", "trace_contradicted")
PRACTICE_KINDS = ("interview_transcript", "executed_artefact")
SIDES = ("documents", "practice")
INTERVIEW = "interview_transcript"
NO_VERDICT = "the verifier gave no verdict for this finding"
QUESTION_TITLE = "Cause not explained by the sources"
# Reality gaps (§3.12.7; B.22): classed only from a reason an SME stated (B.32).
REALITY_GAPS = frozenset(
    {"known_adaptation", "unknown_rule", "disclosure_gap", "control_gap", "constraint_mismatch"}
)
UNEXPLAINED = "unexplained"
NO_ACCOUNTS = "a known adaptation needs an official and a lived account of the step"
NOT_BOTH_ACCOUNTS = "a known adaptation must quote both the official and the lived account"
NOT_COMPLEX = "a constraint mismatch needs work the evidence shows is complex"
NO_PRESCRIPTION = "a constraint mismatch must quote what the documents prescribe"
WHY_QUESTION = "Why do people do it this way?"  # the bank's M6.4, asked about the step
REASON_NOT_FOUND = (
    "The stated reason wasn't found in the interview passages cited, so the class is unexplained."
)
STAGE_NAMES = {STAGE_ID: "Explaining the differences", VERIFY_STAGE: "Independent verification"}


def side_of(source_kind: str) -> str:
    """Interviews and executed artefacts show practice; SOPs, manuals, JDs and others document."""
    return "practice" if source_kind in PRACTICE_KINDS else "documents"


@dataclass(frozen=True, slots=True)
class Passage:
    ref: str  # call-local, e1 …
    source_ref: str  # call-local, s1 …
    source_id: str
    source_kind: str
    source_name: str
    stance: str
    segment: PromptSegment


@dataclass(slots=True)
class SideStance:
    source_ref: str
    source_id: str
    source_kind: str
    source_name: str
    stance: str
    passage_refs: list[str] = field(default_factory=list)
    note: str = ""


@dataclass(frozen=True, slots=True)
class Account:
    """An interview's official or lived account of the step (§3.12.3), with the SME's stated
    reason (found in the passage by S1) for a lived one."""

    account_type: str  # official · lived
    passage_refs: list[str]
    stated_reason: str = ""
    quote: str = ""  # the account claim's own words (checked by S1)

    def holds(self, ref: str, quote: str) -> bool:
        """A finding's quote from this account: in its passage and within (or around) its
        claim's words, so two sentences of one passage stay apart."""
        a, b = grounding.normalise_text(quote), grounding.normalise_text(self.quote)
        return ref in self.passage_refs and bool(a) and bool(b) and (a in b or b in a)


@dataclass(slots=True)
class Divergence:
    ref: str  # call-local, d1 …
    element: GraphElement
    lane: str
    sides: list[SideStance]
    contested_raci: list[tuple[str, str]]  # (role name, letter)
    # Reality gaps (§3.12.7; C4b): the step's accounts and its work type with the cue passages.
    accounts: list[Account] = field(default_factory=list)
    work_type_refs: list[str] = field(default_factory=list)

    @property
    def work_type(self) -> str | None:
        wt = self.element.work_type
        return wt if wt and wt != sensemaking.NOT_CLASSIFIED else None

    def account_refs(self, account_type: str) -> set[str]:
        return {r for a in self.accounts if a.account_type == account_type for r in a.passage_refs}

    def quotes_account(self, account_type: str, ref: str, quote: str) -> bool:
        return any(a.account_type == account_type and a.holds(ref, quote) for a in self.accounts)


@dataclass(slots=True)
class DivergenceSet:
    version_id: str
    engagement_id: str
    items: list[Divergence]
    passages: dict[str, Passage]
    sources: dict[str, tuple[str, str]]  # source ref → (kind, name)
    terms: list[NameReplacement]
    roles: list[list[str]]

    def item(self, ref: str) -> Divergence | None:
        return next((d for d in self.items if d.ref == ref), None)


# --- 1. The divergence set -----------------------------------------------------------------------


def _source_name(filename: str, terms: list[NameReplacement]) -> str:
    """The file name without extension, underscores as spaces ("sop LC-07"), names hidden."""
    return redaction.hide(PurePath(filename).stem.replace("_", " "), terms)


def divergence_set(session: Session, version_id: str) -> DivergenceSet | None:
    version = versions_repo.get(session, version_id)
    graph = versions_action.build_graph(session, version_id)
    if version is None or graph is None:
        return None
    terms = redaction.name_replacements(session, version.engagement_id)
    roles = {r.id: r.name for r in graph.roles}
    raci_owner = {r.id: r.element_id for r in map_repo.raci(session, version_id)}
    raci_rows = {r.id: r for r in map_repo.raci(session, version_id)}
    linked = [p for p in map_repo.evidence(session, version_id) if p.evidence.verified]

    divergent = [
        e
        for e in graph.elements
        if e.review_status != "rejected"
        and (e.source_state in DIVERGENT_STATES or any(r.contested for r in e.raci))
    ]
    # Sources in a fixed order (by file name), so the same map always sends the same data.
    source_ids = {ev.source_id for e in divergent for ev in e.evidence}
    infos = {sid: sources_repo.get(session, sid) for sid in source_ids}
    ordered = sorted(
        (sid for sid, info in infos.items() if info is not None),
        key=lambda sid: (infos[sid].filename, sid),  # type: ignore[union-attr]
    )
    source_ref = {sid: f"s{n}" for n, sid in enumerate(ordered, start=1)}
    sources = {
        source_ref[sid]: (infos[sid].kind, _source_name(infos[sid].filename, terms))  # type: ignore[union-attr]
        for sid in ordered
    }
    segments: dict[str, tuple[str, PromptSegment]] = {}  # segment id → (source id, as sent)
    for sid in ordered:
        info = sources_repo.reading_info(session, sid)
        if info is None:
            continue
        stored = sources_repo.stored_segments(session, sid)
        for seg in s1_extract.prompt_segments(stored, info.format, terms):
            segments[seg.segment_id] = (sid, seg)

    passages: dict[str, Passage] = {}
    by_segment: dict[str, str] = {}
    items: list[Divergence] = []

    def passage_for(segment_id: str, stance: str) -> str:
        """The call-local ref of a passage, added on first use (it must be in `segments`)."""
        ref = by_segment.get(segment_id)
        if ref is None:
            sid, seg = segments[segment_id]
            ref = f"e{len(passages) + 1}"
            by_segment[segment_id] = ref
            passages[ref] = Passage(
                ref=ref,
                source_ref=source_ref[sid],
                source_id=sid,
                source_kind=infos[sid].kind,  # type: ignore[union-attr]
                source_name=sources[source_ref[sid]][1],
                stance=stance,
                segment=seg,
            )
        return ref

    behind = map_repo.element_claims(session, version_id)
    claims = claims_repo.by_ids(session, [c for e in divergent for c in behind.get(e.id, [])])
    for n, element in enumerate(divergent, start=1):
        own = [
            p
            for p in linked
            if p.evidence.element_id == element.id
            or raci_owner.get(p.evidence.raci_id or "") == element.id
        ]
        sides: dict[str, SideStance] = {}
        for p in sorted(own, key=lambda p: (source_ref.get(p.source_id, ""), p.seq)):
            if p.source_id not in source_ref or p.evidence.segment_id not in segments:
                continue
            key = f"{p.source_id}:{p.evidence.stance}"
            side = sides.setdefault(
                key,
                SideStance(
                    source_ref=source_ref[p.source_id],
                    source_id=p.source_id,
                    source_kind=p.evidence.source_kind,
                    source_name=sources[source_ref[p.source_id]][1],
                    stance=p.evidence.stance,
                ),
            )
            ref = passage_for(p.evidence.segment_id, p.evidence.stance)
            if ref not in side.passage_refs:
                side.passage_refs.append(ref)
            note = redaction.hide(p.evidence.note, terms)
            if p.evidence.raci_id and p.evidence.raci_id in raci_rows:
                row = raci_rows[p.evidence.raci_id]
                note = f"RACI {row.letter} {roles.get(row.role_id, '')}: {note}".rstrip(": ")
            if note and note not in side.note:
                side.note = f"{side.note} {note}".strip()
        speaking = {s.source_ref for s in sides.values()}
        silent = [
            SideStance(
                source_ref=source_ref[ev.source_id],
                source_id=ev.source_id,
                source_kind=ev.source_kind,
                source_name=sources[source_ref[ev.source_id]][1],
                stance="silent",
            )
            for ev in element.evidence
            if ev.stance == "silent"
            and ev.source_id in source_ref
            and source_ref[ev.source_id] not in speaking
        ]
        unique_silent = {s.source_ref: s for s in silent}
        all_sides = sorted(
            [*sides.values(), *unique_silent.values()], key=lambda s: (s.source_ref, s.stance)
        )
        accounts = []
        for claim_id in behind.get(element.id, []):
            c = claims.get(claim_id)
            if c is None or c.account_type not in {"official", "lived"}:
                continue
            refs = [passage_for(seg, "supports") for seg in c.segment_ids if seg in segments]
            if not refs:
                continue
            reason = str(c.payload.get("stated_reason", "")) if c.account_type == "lived" else ""
            account = Account(c.account_type, refs, redaction.hide(reason, terms), c.quote)
            if account not in accounts:
                accounts.append(account)
        cue_refs = [
            passage_for(str(seg), "supports")
            for cue in element.work_type_basis
            for seg in (cue.get("segment_ids") or [])
            if str(seg) in segments
        ]
        items.append(
            Divergence(
                ref=f"d{n}",
                element=element,
                lane=roles.get(element.lane_role_id or "", ""),
                sides=all_sides,
                contested_raci=[
                    (roles.get(r.role_id, ""), r.letter) for r in element.raci if r.contested
                ],
                accounts=accounts,
                work_type_refs=list(dict.fromkeys(cue_refs)),
            )
        )
    return DivergenceSet(
        version_id=version_id,
        engagement_id=version.engagement_id,
        items=items,
        passages=passages,
        sources=sources,
        terms=terms,
        roles=role_groups(session, version.engagement_id),
    )


def _render_passages(dset: DivergenceSet, refs: list[str]) -> list[str]:
    """The given passages grouped by source, in the set's order."""
    esc = prompts.escape
    lines: list[str] = []
    wanted = [dset.passages[r] for r in dset.passages if r in set(refs)]
    for source_ref, (kind, name) in dset.sources.items():
        mine = [p for p in wanted if p.source_ref == source_ref]
        if not mine:
            continue
        lines.append(f'<source id="{esc(source_ref)}" kind="{esc(kind)}" name="{esc(name)}">')
        for p in mine:
            s = p.segment
            speaker = f' speaker="{esc(s.speaker_role)}"' if s.speaker_role else ""
            lines.append(
                f'<segment id="{esc(p.ref)}" anchor="{esc(s.anchor)}"{speaker}>'
                f"{esc(s.text)}</segment>"
            )
        lines.append("</source>")
    return lines


def blocks_for(dset: DivergenceSet) -> list[dict[str, object]]:
    esc = prompts.escape
    lines: list[str] = []
    for item in dset.items:
        e = item.element
        work_type = f' work_type="{esc(item.work_type)}"' if item.work_type else ""
        lines.append(
            f'<divergence id="{item.ref}" kind="{esc(e.kind)}" lane="{esc(item.lane)}" '
            f'label="{esc(e.label)}" state="{esc(e.source_state)}" '
            f'types="{esc(" ".join(e.divergence_types))}"{work_type}>'
        )
        for side in item.sides:
            segs = f' segments="{" ".join(side.passage_refs)}"' if side.passage_refs else ""
            lines.append(
                f'<side source="{side.source_ref}" kind="{esc(side.source_kind)}" '
                f'name="{esc(side.source_name)}" stance="{esc(side.stance)}"{segs}/>'
            )
            if side.note:
                lines.append(f'<note source="{side.source_ref}">{esc(side.note)}</note>')
        for role, letter in item.contested_raci:
            lines.append(f'<raci role="{esc(role)}" letter="{esc(letter)}" contested="yes"/>')
        shown: set[tuple[str, str, str]] = set()
        for a in item.accounts:
            key = (a.account_type, " ".join(a.passage_refs), a.stated_reason)
            if key in shown:
                continue
            shown.add(key)
            reason = f' reason="{esc(a.stated_reason)}"' if a.stated_reason else ""
            lines.append(
                f'<account type="{esc(a.account_type)}" '
                f'segments="{" ".join(a.passage_refs)}"{reason}/>'
            )
        if item.work_type and item.work_type_refs:
            lines.append(
                f'<work_type type="{esc(item.work_type)}" cues="{" ".join(item.work_type_refs)}"/>'
            )
        lines.append("</divergence>")
    lines += _render_passages(dset, list(dset.passages))
    return [{"type": "text", "text": "\n".join(lines)}]


# --- 2. Synthesis --------------------------------------------------------------------------------


def _call(
    sessions: Sessions,
    ctx: AiContext,
    stage_id: str,
    blocks: list[dict[str, object]],
    output_model: type[BaseModel],
    job_id: str | None,
) -> Result[BaseModel]:
    return call_stage(sessions, ctx, stage_id, STAGE_NAMES[stage_id], blocks, output_model, job_id)


def synthesise(
    sessions: Sessions, ctx: AiContext, dset: DivergenceSet, job_id: str | None = None
) -> Result[ai_schemas.GAInternalOutput]:
    if not dset.items:
        return Ok(ai_schemas.GAInternalOutput(findings=[], unknowns=[]))
    match _call(sessions, ctx, STAGE_ID, blocks_for(dset), ai_schemas.GAInternalOutput, job_id):
        case Err() as err:
            return err
        case Ok(value=output):
            assert isinstance(output, ai_schemas.GAInternalOutput)
            return Ok(output)


# --- 3. The grounding gate -----------------------------------------------------------------------


@dataclass(slots=True)
class Checked:
    """A finding after the gate: kept or rejected, with the passages the verifier will see."""

    finding: NewGapFinding
    passage_refs: list[str]
    silent: list[GapEvidence]
    kinds: list[str]
    trace_contradicted: bool


def _mentions(text: str, name: str) -> bool:
    words = grounding.normalise_text(name)
    return bool(words) and re.search(rf"(?<!\w){re.escape(words)}s?(?!\w)", text) is not None


def roles_named(text: str, groups: list[list[str]]) -> list[str]:
    """The known roles a finding names (by name or alias)."""
    plain = grounding.normalise_text(text)
    return [g[0] for g in groups if any(_mentions(plain, n) for n in g)]


def _rejected(checked: Checked, guardrail: str, reason: str) -> Checked:
    checked.finding.verification_status = "rejected"
    checked.finding.rejection_guardrail = guardrail
    checked.finding.rejection_reason = reason
    return checked


def check(dset: DivergenceSet, f: ai_schemas.GAFinding) -> Checked:
    def hide(text: str) -> str:
        return redaction.hide(text, dset.terms)

    items = [dset.item(r) for r in f.step_refs]
    known = [i for i in items if i is not None]
    finding = NewGapFinding(
        section=f.section,
        finding_type=f.finding_type,
        title=hide(f.title),
        text=hide(f.text),
        element_ids=[i.element.id for i in known],
        basis=hide(f.basis),
        provenance="O" if f.section == "fact" else "I",
    )
    checked = Checked(
        finding=finding,
        passage_refs=[],
        silent=[],
        kinds=[i.element.kind for i in known],
        trace_contradicted=any(i.element.source_state == "trace_contradicted" for i in known),
    )
    if not f.step_refs or len(known) != len(items):
        return _rejected(
            checked, Guardrail.G3.value, "refers to a step that isn't in the comparison"
        )
    cited = [e.segment_id for e in f.evidence]
    outcome = grounding.verify_segments(cited, dset.passages.keys())
    if not outcome.passed:
        return _rejected(checked, outcome.guardrail, outcome.reason)
    evidence: list[GapEvidence] = []
    for cite in f.evidence:
        p = dset.passages[cite.segment_id]
        quote = grounding.verify_quote(cite.quote, prompts.cited_text([p.segment]))
        if not quote.passed:
            return _rejected(checked, quote.guardrail, quote.reason)
        evidence.append(
            GapEvidence(
                side=side_of(p.source_kind),
                source_id=p.source_id,
                source_kind=p.source_kind,
                source_name=p.source_name,
                stance=p.stance,
                segment_id=p.segment.segment_id,
                anchor=p.segment.anchor,
                quote=hide(cite.quote),
            )
        )
    basis_refs = list(f.basis_segment_ids)
    if basis_refs and not grounding.verify_segments(basis_refs, dset.passages.keys()).passed:
        return _rejected(
            checked, Guardrail.G3.value, "the basis cites a passage that wasn't provided"
        )
    if f.section == "interpretation" and (
        not f.basis.strip()
        or not basis_refs
        or any(dset.passages[r].source_kind != INTERVIEW for r in basis_refs)
    ):
        return _rejected(
            checked,
            Guardrail.G3.value,
            "a pattern or cause needs a basis citing what the SMEs said",
        )
    refs = list(dict.fromkeys([*cited, *basis_refs]))
    checked.passage_refs = refs
    text = prompts.cited_text([dset.passages[r].segment for r in refs])
    claim = f"{f.title}. {f.text}"
    # A finding may name the documents and places it compares ("SOP LC-07 §3.2"); their names
    # count for the number and role checks (so the alias "LC" inside "LC-07" isn't a new role).
    named = [
        *(f"{dset.passages[r].source_name} {dset.passages[r].segment.anchor}" for r in refs),
        *(s.source_name for i in known for s in i.sides),
    ]
    with_names = "\n".join([text, *named])
    numbers = grounding.verify_numbers(claim, with_names, f.basis)
    if not numbers.passed:
        return _rejected(checked, numbers.guardrail, numbers.reason)
    roles = grounding.verify_roles(roles_named(claim, dset.roles), with_names, dset.roles)
    if not roles.passed:
        return _rejected(checked, roles.guardrail, roles.reason)
    if f.finding_type == "known_adaptation":
        # The comparison is the SME's official account against their lived one (§3.12.7).
        official = set().union(*(i.account_refs("official") for i in known))
        lived = set().union(*(i.account_refs("lived") for i in known))
        if not official or not lived:
            return _rejected(checked, Guardrail.G3.value, NO_ACCOUNTS)
        # One quote from each account's own words (both may sit in the same passage).
        quotes = [(e.segment_id, e.quote) for e in f.evidence]
        if not all(
            any(i.quotes_account(kind, ref, q) for i in known for ref, q in quotes)
            for kind in ("official", "lived")
        ):
            return _rejected(checked, Guardrail.G3.value, NOT_BOTH_ACCOUNTS)
    if f.finding_type == "constraint_mismatch":
        if any(i.work_type not in sensemaking.NEVER_AUTOMATED for i in known):
            return _rejected(checked, Guardrail.G3.value, NOT_COMPLEX)
        if "documents" not in {e.side for e in evidence}:
            return _rejected(checked, Guardrail.G3.value, NO_PRESCRIPTION)
    if f.finding_type in REALITY_GAPS:
        _classify(checked, f, refs, dset)
    if f.finding_type == "known_adaptation":
        finding.evidence = evidence
        return checked
    # Both sides: quoted, or silent on every step the finding names.
    spoken = {e.side for e in evidence}
    for item in known:
        for side in item.sides:
            if side.stance != "silent" or side_of(side.source_kind) in spoken:
                continue
            others = [
                s
                for s in item.sides
                if s.stance != "silent" and side_of(s.source_kind) == side_of(side.source_kind)
            ]
            if others:
                continue  # that side does speak about the step; silence isn't its evidence
            ev = GapEvidence(
                side=side_of(side.source_kind),
                source_id=side.source_id,
                source_kind=side.source_kind,
                source_name=side.source_name,
                stance="silent",
            )
            if ev not in checked.silent:
                checked.silent.append(ev)
    present = spoken | {e.side for e in checked.silent}
    missing = [s for s in SIDES if s not in present]
    if missing:
        return _rejected(checked, Guardrail.G3.value, f"no evidence from the {missing[0]} side")
    finding.evidence = evidence + checked.silent
    return checked


def _classify(
    checked: Checked, f: ai_schemas.GAFinding, refs: list[str], dset: DivergenceSet
) -> None:
    """A reality gap's class (§3.12.7): proposed only when the SME's stated reason is quoted
    exactly from an interview passage the finding cites; otherwise `unexplained`, with the
    question "Why do people do it this way?" for the SMEs (added to the report)."""
    finding = checked.finding
    interview = [
        dset.passages[r].segment for r in refs if dset.passages[r].source_kind == INTERVIEW
    ]
    reason = f.stated_reason.strip()
    found = bool(reason) and grounding.verify_quote(reason, prompts.cited_text(interview)).passed
    if found and f.gap_class != UNEXPLAINED:
        finding.gap_class = f.gap_class
        finding.stated_reason = redaction.hide(reason, dset.terms)
        finding.cause_type = None if f.cause_type == "none" else f.cause_type
        return
    finding.gap_class = UNEXPLAINED
    finding.stated_reason = redaction.hide(reason, dset.terms) if found else ""
    if reason and not found:
        finding.notes.append(REASON_NOT_FOUND)


def why_question(dset: DivergenceSet, c: Checked) -> NewGapFinding:
    """The follow-up question an unexplained reality gap raises (§3.12.7), about its steps."""
    labels = [i.element.label for e in c.finding.element_ids for i in dset.items
              if i.element.id == e]  # fmt: skip
    question = redaction.hide(f'On "{labels[0]}": {WHY_QUESTION}' if labels else WHY_QUESTION,
                              dset.terms)  # fmt: skip
    return NewGapFinding(
        section="recommendation",
        finding_type=c.finding.finding_type,
        title=QUESTION_TITLE,
        text=question,
        element_ids=list(c.finding.element_ids),
        question=question,
    )


def unknown_finding(dset: DivergenceSet, u: ai_schemas.GAUnknown) -> NewGapFinding:
    """A cause the sources don't explain, kept as a suggested question for the SMEs."""
    question = redaction.hide(u.question, dset.terms)
    return NewGapFinding(
        section="recommendation",
        finding_type=u.finding_type,
        title=QUESTION_TITLE,
        text=question,
        element_ids=[i.element.id for r in u.step_refs if (i := dset.item(r)) is not None],
        question=question,
    )


# --- 4. The verifier -----------------------------------------------------------------------------


def verify_blocks(dset: DivergenceSet, kept: list[Checked]) -> list[dict[str, object]]:
    esc = prompts.escape
    lines: list[str] = []
    for n, c in enumerate(kept, start=1):
        f = c.finding
        lines.append(
            f'<finding id="f{n}" type="{esc(f.finding_type)}" section="{esc(f.section)}">'
            f"{esc(f.title)}. {esc(f.text)}</finding>"
        )
        if f.basis:
            lines.append(f"<basis>{esc(f.basis)}</basis>")
        if f.stated_reason:
            lines.append(f"<stated_reason>{esc(f.stated_reason)}</stated_reason>")
        for s in c.silent:
            lines.append(
                f'<silent kind="{esc(s.source_kind)}" name="{esc(s.source_name)}">'
                "says nothing about this step</silent>"
            )
        lines += _render_passages(dset, c.passage_refs)
    return [{"type": "text", "text": "\n".join(lines)}]


def verify(
    sessions: Sessions,
    ctx: AiContext,
    dset: DivergenceSet,
    checked: list[Checked],
    job_id: str | None = None,
) -> Result[None]:
    kept = [c for c in checked if c.finding.verification_status != "rejected"]
    if not ctx.verifier_enabled or not kept:
        return Ok(None)
    blocks = verify_blocks(dset, kept)
    match _call(sessions, ctx, VERIFY_STAGE, blocks, ai_schemas.GAVerifyOutput, job_id):
        case Err() as err:
            return err
        case Ok(value=output):
            assert isinstance(output, ai_schemas.GAVerifyOutput)
    verdicts = {v.finding_ref: v for v in output.verdicts}
    for n, c in enumerate(kept, start=1):
        found = verdicts.get(f"f{n}")
        verdict = found.verdict if found else VerifierVerdict.PARTIAL.value
        c.finding.verifier_verdict = verdict
        if verdict == VerifierVerdict.NOT_SUPPORTED.value:
            reason = redaction.hide(found.reason, dset.terms) if found else NO_VERDICT
            _rejected(c, Guardrail.GAV.value, reason)
    return Ok(None)


# --- 5. The report -------------------------------------------------------------------------------


def report(
    dset: DivergenceSet, checked: list[Checked], unknowns: list[ai_schemas.GAUnknown]
) -> list[NewGapFinding]:
    out: list[NewGapFinding] = []
    asked: list[NewGapFinding] = []
    for c in checked:
        if c.finding.verification_status != "rejected":
            c.finding.severity = gap.severity_internal(
                c.finding.finding_type, c.kinds, trace_contradicted=c.trace_contradicted
            )
            if c.finding.gap_class == UNEXPLAINED:
                asked.append(why_question(dset, c))
        out.append(c.finding)
    out += [unknown_finding(dset, u) for u in unknowns]
    have = {(q.text, tuple(q.element_ids)) for q in out if q.question}
    return out + [q for q in asked if (q.text, tuple(q.element_ids)) not in have]
