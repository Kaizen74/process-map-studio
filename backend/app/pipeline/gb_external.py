"""Gap analysis B, external best practice (PRD §3.11.2; phase P10). Advisory: nothing here changes
the map; the findings are stored as a report for Eric to disposition.

- `brief_facts`, `scan_inputs`, `brief_state` (no AI): the brief drafted from the version and the
  confidentiality scan of exactly what would be sent.
- `research` (`GB_research`, the web search tool): only the approved brief text is sent.
- `capture` (no AI): every search result and citation, citations numbered c1 …; tool errors kept
  as partial results with a plain note.
- `structure` (`GB_structure`, no tools): findings citing only the captured citation IDs.
- `check` (no AI): GX1-GX6 (`grounding.verify_citations`).
- `verify` (`GB_verify`, follows the verifier switch): `not_supported` → rejected `GAV`.
- `report` (no AI): aligned practices left out as "not a gap", severity, compliance note, `R`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.actions import versions as versions_action
from app.db import session_scope
from app.domain import ai_schemas
from app.domain.enums import Guardrail, VerifierVerdict
from app.domain.gap import (
    Brief,
    BriefInput,
    BriefState,
    CitedSource,
    GapEvidence,
    NewExternalSource,
    NewGapFinding,
    ScanResult,
)
from app.domain.graph import GraphElement
from app.domain.models import AiCallRecord, NameReplacement, ResearchAnswer
from app.domain.result import Err, Ok, Result
from app.pipeline.context import AiContext, ai_failure, call_stage, calls_in, record_calls
from app.repositories import elements as map_repo
from app.repositories import engagements as engagements_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import ai_service, gap, grounding, prompts

Sessions = sessionmaker[Session]

RESEARCH_STAGE = "GB_research"
STRUCTURE_STAGE = "GB_structure"
VERIFY_STAGE = "GB_verify"
STAGE_NAMES = {
    RESEARCH_STAGE: "Searching the web with your brief",
    STRUCTURE_STAGE: "Organising the findings",
    VERIFY_STAGE: "Independent verification",
}
STEP_KINDS = ("activity", "decision", "approval")
NO_VERDICT = "the verifier gave no verdict for this finding"
LINK_REMOVED = "A link to a step that isn't on this map was removed."
TOOL_ERRORS = {
    "max_uses_exceeded": (
        "The search limit was reached before the research finished, so this report may be "
        "incomplete."
    ),
    "too_many_requests": (
        "Web search was busy, so some searches didn't run; this report may be incomplete."
    ),
}
TOOL_ERROR = "Some searches failed ({code}), so this report may be incomplete."
CUT_SHORT = "The research was cut short before it finished, so this report may be incomplete."
NOT_A_GAP = "Left out as not a gap (the map already does this): “{title}”."


# --- The brief and its confidentiality scan (no AI) ----------------------------------------------


def steps_of(session: Session, version_id: str) -> list[GraphElement]:
    graph = versions_action.build_graph(session, version_id)
    if graph is None:
        return []
    return [e for e in graph.elements if e.kind in STEP_KINDS and e.review_status != "rejected"]


def brief_facts(session: Session, version_id: str) -> BriefInput | None:
    version = versions_repo.get(session, version_id)
    engagement = engagements_repo.get(session, version.engagement_id) if version else None
    if version is None or engagement is None:
        return None
    terms = redaction.name_replacements(session, engagement.id)
    return BriefInput(
        process_name=engagement.process_name or engagement.name,
        industry=engagement.industry,
        adjacent_industries=list(engagement.adjacent_industries),
        step_labels=[e.label for e in steps_of(session, version_id)],
        confidential_terms=list(engagement.confidential_terms),
        hidden_names=[t.term for t in terms],
    )


@dataclass(frozen=True, slots=True)
class ScanInputs:
    hidden_names: list[str]
    confidential_terms: list[str]
    map_numbers: set[str]
    passages: list[str]


def scan_inputs(session: Session, version_id: str) -> ScanInputs | None:
    """What the brief is scanned against: names to hide, confidential terms, every number or time
    on the map, and every transcript or document passage the version was drafted from."""
    facts = brief_facts(session, version_id)
    graph = versions_action.build_graph(session, version_id)
    if facts is None or graph is None:
        return None
    texts = [graph.process.kpi, graph.process.trigger, graph.process.end_point]
    for e in graph.elements:
        texts += [e.label, e.time.text, e.kpi, e.k_risk, e.handoff.in_, e.handoff.out]
        texts += [e.decision.rule_or_threshold, e.decision.escalation]
        texts += [c.text for c in e.constraints]
        texts += [str(n) for n in (e.time.work_min, e.time.wait_min) if n is not None]
    numbers = set().union(*(grounding.numbers_in(t) for t in texts if t))
    passages = [
        s.text
        for sid in map_repo.version_source_ids(session, version_id)
        for s in sources_repo.stored_segments(session, sid)
    ]
    return ScanInputs(facts.hidden_names, facts.confidential_terms, numbers, passages)


def brief_state(brief: Brief, confirmed: bool, inputs: ScanInputs) -> BriefState:
    text = gap.brief_text(brief)
    hits = gap.scan_brief(
        text,
        hidden_names=inputs.hidden_names,
        confidential_terms=inputs.confidential_terms,
        map_numbers=inputs.map_numbers,
        passages=inputs.passages,
    )
    return BriefState(brief=brief, text=text, confirmed=confirmed, scan=ScanResult(hits=hits))


# --- Research (the only call that uses web search) -----------------------------------------------


def research(
    sessions: Sessions, ctx: AiContext, brief: Brief, cap: int, job_id: str | None = None
) -> Result[ResearchAnswer]:
    match prompts.load_prompt(RESEARCH_STAGE):
        case Err() as err:
            return err
        case Ok(value=prompt):
            pass
    call = ai_service.ResearchCall(
        stage_id=RESEARCH_STAGE,
        prompt_version=prompt.version,
        system=prompt.text,
        brief=gap.brief_text(brief),  # only the approved brief is sent
        model=ctx.model,
        max_uses=max(1, min(brief.max_searches, cap)),
        allowed_domains=tuple(brief.allowed_domains),
        blocked_domains=tuple(brief.blocked_domains),
        effort=ctx.effort,
    )
    result = ai_service.call_claude_with_web_search(ctx.conn, call)
    used: list[AiCallRecord] = result.value.calls if isinstance(result, Ok) else calls_in(result)
    with session_scope(sessions) as session:
        record_calls(session, job_id, used)
    match result:
        case Err(api_code=ai_service.SEARCH_OFF_CODE) as err:
            return err
        case Err() as err:
            return ai_failure(err)
        case Ok(value=answer):
            return Ok(answer)


@dataclass(slots=True)
class Captured:
    """What the research returned: citations by ID, the answer with its citation IDs, every page
    returned or cited, and notes about a partial result."""

    citations: dict[str, CitedSource]
    answer: list[tuple[str, list[str]]]
    search_urls: set[str]
    sources: list[NewExternalSource]
    notes: list[str] = field(default_factory=list)

    def citation_rows(self) -> list[tuple[str, str, str]]:
        return [(c.id, c.url, c.cited_text) for c in self.citations.values()]


def capture(answer: ResearchAnswer) -> Captured:
    pages = {r.url: r for r in answer.results}
    citations: dict[str, CitedSource] = {}
    by_key: dict[tuple[str, str], str] = {}
    text: list[tuple[str, list[str]]] = []
    for passage in answer.passages:
        refs: list[str] = []
        for c in passage.citations:
            ref = by_key.get((c.url, c.cited_text))
            if ref is None:
                ref = f"c{len(citations) + 1}"
                by_key[(c.url, c.cited_text)] = ref
                page = pages.get(c.url)
                citations[ref] = CitedSource(
                    id=ref,
                    url=c.url,
                    title=c.title or (page.title if page else ""),
                    cited_text=c.cited_text,
                    page_age=page.page_age if page else "",
                )
            refs.append(ref)
        text.append((passage.text, refs))
    sources = [
        NewExternalSource(
            url=r.url,
            title=r.title,
            domain=gap.domain_of(r.url),
            page_age=r.page_age,
            tier=gap.source_tier(r.url),
            returned_in_results=True,
        )
        for r in answer.results
    ]
    for cited in citations.values():
        if cited.url not in pages and all(s.url != cited.url for s in sources):
            sources.append(
                NewExternalSource(
                    url=cited.url,
                    title=cited.title,
                    domain=gap.domain_of(cited.url),
                    page_age="",
                    tier=gap.source_tier(cited.url),
                    returned_in_results=False,
                )
            )
    notes = [TOOL_ERRORS.get(code, TOOL_ERROR.format(code=code)) for code in answer.tool_errors]
    if answer.stop_reason in {"pause_turn", "max_tokens"}:
        notes.append(CUT_SHORT)
    return Captured(
        citations=citations,
        answer=text,
        search_urls={r.url for r in answer.results},
        sources=sources,
        notes=list(dict.fromkeys(notes)),
    )


# --- Structuring ---------------------------------------------------------------------------------


def step_refs(steps: list[GraphElement]) -> dict[str, GraphElement]:
    return {f"m{n}": e for n, e in enumerate(steps, start=1)}


def structure_blocks(
    captured: Captured, steps: dict[str, GraphElement], lanes: dict[str, str]
) -> list[dict[str, object]]:
    esc = prompts.escape
    lines = ["<answer>"]
    for text, refs in captured.answer:
        cites = "".join(f'<cite id="{r}"/>' for r in refs)
        lines.append(f"<passage>{esc(text)}{cites}</passage>")
    lines.append("</answer>")
    for c in captured.citations.values():
        lines.append(
            f'<citation id="{c.id}" url="{esc(c.url)}" title="{esc(c.title)}">'
            f"{esc(c.cited_text)}</citation>"
        )
    for ref, e in steps.items():
        lane = lanes.get(e.lane_role_id or "", "")
        lines.append(
            f'<step id="{ref}" kind="{esc(e.kind)}" lane="{esc(lane)}">{esc(e.label)}</step>'
        )
    return [{"type": "text", "text": "\n".join(lines)}]


def _call(
    sessions: Sessions,
    ctx: AiContext,
    stage_id: str,
    blocks: list[dict[str, object]],
    output_model: type[BaseModel],
    job_id: str | None,
) -> Result[BaseModel]:
    return call_stage(sessions, ctx, stage_id, STAGE_NAMES[stage_id], blocks, output_model, job_id)


def structure(
    sessions: Sessions,
    ctx: AiContext,
    blocks: list[dict[str, object]],
    job_id: str | None = None,
) -> Result[ai_schemas.GBStructureOutput]:
    match _call(sessions, ctx, STRUCTURE_STAGE, blocks, ai_schemas.GBStructureOutput, job_id):
        case Err() as err:
            return err
        case Ok(value=output):
            assert isinstance(output, ai_schemas.GBStructureOutput)
            return Ok(output)


# --- The external grounding gate (GX1-GX6) -------------------------------------------------------


@dataclass(slots=True)
class CheckedB:
    finding: NewGapFinding
    citation_ids: list[str]
    tiers_by_domain: dict[str, str]
    dated: bool
    aligned: bool


def check(
    captured: Captured,
    steps: dict[str, GraphElement],
    f: ai_schemas.GBFinding,
    *,
    recency_years: int,
    this_year: int,
    terms: list[NameReplacement],
) -> CheckedB:
    outcome = grounding.verify_citations(
        claim=f"{f.title}. {f.claim}",
        quote=f.quote,
        citation_ids=f.citation_ids,
        citations=captured.citations,
        search_urls=captured.search_urls,
        element_ids=f.step_refs,
        known_elements=set(steps),
        recency_years=recency_years,
        this_year=this_year,
        tier_of=gap.source_tier,
    )
    evidence = [
        GapEvidence(
            side="external",
            source_kind=gap.source_tier(c.url),
            source_name=c.title,
            stance="supports",
            quote=gap.excerpt(c.cited_text),
            url=c.url,
            tier=gap.source_tier(c.url),
            page_age=c.page_age,
            citation_id=c.id,
        )
        for ref in dict.fromkeys(f.citation_ids)
        if (c := captured.citations.get(ref)) is not None
    ]
    strength = "dated" if outcome.dated else "weak" if outcome.weak else "strong"
    finding = NewGapFinding(
        section="recommendation",
        finding_type=f.finding_type,
        title=redaction.hide(f.title, terms),
        text=redaction.hide(f.claim, terms),
        element_ids=[steps[r].id for r in outcome.element_ids],
        evidence=evidence,
        provenance="R",
        evidence_strength=strength,
        comparison=f.comparison if f.comparison != "aligned" else None,
        notes=[LINK_REMOVED] if outcome.dropped_element_ids else [],
    )
    if not outcome.outcome.passed:
        finding.verification_status = "rejected"
        finding.rejection_guardrail = outcome.outcome.guardrail
        finding.rejection_reason = outcome.outcome.reason
    return CheckedB(
        finding=finding,
        citation_ids=list(dict.fromkeys(f.citation_ids)),
        tiers_by_domain=outcome.tiers_by_domain,
        dated=outcome.dated,
        aligned=f.comparison == "aligned",
    )


# --- The verifier --------------------------------------------------------------------------------


def verify_blocks(captured: Captured, kept: list[CheckedB]) -> list[dict[str, object]]:
    esc = prompts.escape
    lines: list[str] = []
    for n, c in enumerate(kept, start=1):
        f = c.finding
        lines.append(
            f'<finding id="f{n}" type="{esc(f.finding_type)}">{esc(f.title)}. {esc(f.text)}'
            "</finding>"
        )
        for ref in c.citation_ids:
            cite = captured.citations[ref]
            lines.append(
                f'<citation id="{ref}" title="{esc(cite.title)}">{esc(cite.cited_text)}</citation>'
            )
    return [{"type": "text", "text": "\n".join(lines)}]


def to_verify(checked: list[CheckedB]) -> list[CheckedB]:
    """Findings that passed the gate and are gaps (aligned practices are left out first)."""
    return [c for c in checked if c.finding.verification_status != "rejected" and not c.aligned]


def verify(
    sessions: Sessions,
    ctx: AiContext,
    captured: Captured,
    checked: list[CheckedB],
    terms: list[NameReplacement],
    job_id: str | None = None,
) -> Result[None]:
    kept = to_verify(checked)
    if not ctx.verifier_enabled or not kept:
        return Ok(None)
    blocks = verify_blocks(captured, kept)
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
            c.finding.verification_status = "rejected"
            c.finding.rejection_guardrail = Guardrail.GAV.value
            c.finding.rejection_reason = (
                redaction.hide(found.reason, terms) if found else NO_VERDICT
            )
    return Ok(None)


# --- The report ----------------------------------------------------------------------------------


def report(checked: list[CheckedB]) -> tuple[list[NewGapFinding], list[str]]:
    """The findings to store and the notes for practices left out as not a gap."""
    out: list[NewGapFinding] = []
    notes: list[str] = []
    for c in checked:
        f = c.finding
        if c.aligned and f.verification_status != "rejected":
            notes.append(NOT_A_GAP.format(title=f.title))
            continue
        if f.verification_status != "rejected":
            f.severity = gap.severity_external(f.finding_type, c.tiers_by_domain, dated=c.dated)
            if gap.needs_compliance_note(f"{f.title} {f.text}", c.tiers_by_domain.values()):
                f.notes.append(gap.COMPLIANCE_NOTE)
        out.append(f)
    return out, notes
