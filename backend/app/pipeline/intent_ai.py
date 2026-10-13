"""The intent AI steps (PRD §3.16, G16; P13a-2). Advisory: nothing here counts until Eric confirms.

1. `extract` (`S1_extract_intent`): one call per policy or charter (or an SOP's purpose clauses).
   Claude sees only those passages, names hidden, and the current map's step keys and phases.
2. `check_statement` (no AI): G3 the cited passages were sent; G4 the quote is found in them; G5
   every number in the text, and the target value, is in the quote, and every role named is in the
   passages; a target is complete and its unit fits the metric; one line of up to 200 characters.
3. `compare` (`IX_compare`): confirmed statements against the documented passages (SOPs, manuals).
4. `check_conflict` (no AI): IX1 both quotes and at most 25 words; G3 the statement and passages
   were sent; G4 each quote is found on its own side; G5 numbers and roles found on the two sides.
5. `verify` (`IX_verify`, follows the verifier switch): `not_supported` → rejected `IXV`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.domain import ai_schemas
from app.domain.enums import Guardrail, IntentMetric, VerifierVerdict
from app.domain.models import NameReplacement, PromptSegment
from app.domain.result import Err, Ok, Result
from app.pipeline.context import AiContext, call_stage
from app.pipeline.ga_internal import roles_named
from app.services import grounding, prompts

Sessions = sessionmaker[Session]

EXTRACT_STAGE = "S1_extract_intent"
EXTRACT_NAME = "Finding intent statements"
COMPARE_STAGE = "IX_compare"
COMPARE_NAME = "Comparing intent with the documents"
VERIFY_STAGE = "IX_verify"
VERIFY_NAME = "Checking intent independently"
PURPOSE = re.compile(r"\b(?:to ensure|so that|in order to)\b", re.IGNORECASE)
MAX_TEXT = 200
MAX_CONFLICT_WORDS = 25
UNITS_BY_SUFFIX = {"_min": "min", "_pct": "pct"}
NO_VERDICT = "the verifier gave no verdict"
NOT_ONE_LINE = "the statement isn't one line of 1 to 200 characters"


@dataclass(frozen=True, slots=True)
class SourcePassages:
    """One source's passages as sent (call-local refs, names hidden)."""

    source_id: str
    source_name: str
    kind: str
    segments: list[PromptSegment]

    def by_ref(self) -> dict[str, PromptSegment]:
        return {s.ref: s for s in self.segments}


@dataclass(frozen=True, slots=True)
class MapPlaces:
    """The current map's steps (stable key → label, in map order) and phase names."""

    steps: dict[str, str] = field(default_factory=dict)
    phases: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Checked:
    """A proposal after the checks: the fields to store, and why it was turned down (if it was)."""

    fields: dict[str, object]
    cited: list[PromptSegment]
    words: str  # what the verifier checks: the statement's text, or the conflict
    guardrail: str | None = None
    reason: str = ""

    @property
    def kept(self) -> bool:
        return self.guardrail is None

    def reject(self, guardrail: str, reason: str) -> Checked:
        self.guardrail, self.reason = guardrail, reason
        return self


def purpose_clauses(segments: list[PromptSegment]) -> list[PromptSegment]:
    """An SOP's or manual's passages that state a purpose ("to ensure…", "so that…")."""
    return [s for s in segments if PURPOSE.search(s.text)]


def _tagged(tag: str, value: object) -> str:
    return f"<{tag}>\n{prompts.escape(json.dumps(value, ensure_ascii=False, indent=1))}\n</{tag}>"


def extract_blocks(src: SourcePassages, places: MapPlaces) -> list[dict[str, object]]:
    text = "\n".join([
        prompts.render_source("s1", src.kind, src.segments),
        _tagged("steps", [{"key": k, "label": v} for k, v in places.steps.items()]),
        _tagged("phases", places.phases),
    ])  # fmt: skip
    return [{"type": "text", "text": text}]


def extract(
    sessions: Sessions, ctx: AiContext, src: SourcePassages, places: MapPlaces, job_id: str
) -> Result[list[ai_schemas.IntentProposal]]:
    blocks = extract_blocks(src, places)
    match call_stage(sessions, ctx, EXTRACT_STAGE, EXTRACT_NAME, blocks,
                     ai_schemas.S1IntentOutput, job_id):  # fmt: skip
        case Err() as err:
            return err
        case Ok(value=output):
            assert isinstance(output, ai_schemas.S1IntentOutput)
            return Ok(list(output.statements))


def _value_in(value: float, text: str) -> bool:
    """The target value (or the offset T-n) is stated in the text."""
    number = str(int(value)) if float(value).is_integer() else str(value)
    found = grounding.numbers_in(text)
    return number in found or f"T-{number}" in found


def _unit_fits(metric: str, unit: str) -> bool:
    expected = next((u for suffix, u in UNITS_BY_SUFFIX.items() if metric.endswith(suffix)), None)
    return expected is None or unit == expected


def check_statement(
    p: ai_schemas.IntentProposal,
    src: SourcePassages,
    places: MapPlaces,
    groups: list[list[str]],
    terms: list[NameReplacement],
) -> Checked:
    """One proposal after the G16 checks. Names are hidden in everything kept (G10)."""
    passages = src.by_ref()
    text = redaction.hide(" ".join(p.text.split()), terms)
    quote = redaction.hide(p.quote.strip(), terms)
    scope, key, phase = p.scope, p.step_key or None, p.phase_name or None
    if scope == "step" and key not in places.steps:
        scope, key = "process", None  # a step not on the map: the statement covers the process
    if scope == "phase" and phase not in places.phases:
        scope, phase = "process", None
    target = (p.metric or None, p.comparator or None, p.target_value, p.unit or None)
    cited = [passages[r] for r in p.segment_ids if r in passages]
    checked = Checked(
        fields={
            "kind": p.kind, "text": text[:MAX_TEXT], "scope": scope,
            "element_stable_key": key if scope == "step" else None,
            "phase_name": phase if scope == "phase" else None,
            "metric": target[0], "comparator": target[1], "target_value": target[2],
            "unit": target[3], "source_id": src.source_id,
            "segment_ids": [s.segment_id for s in cited], "quote": quote,
        },
        cited=cited,
        words=text,
    )  # fmt: skip
    outcome = grounding.verify_segments(p.segment_ids, passages.keys())
    if not p.segment_ids or not outcome.passed:
        return checked.reject(Guardrail.G3.value, outcome.reason or "no passage cited")
    cited_text = prompts.cited_text(cited)
    found = grounding.verify_quote(p.quote, cited_text)
    if not found.passed:
        return checked.reject(found.guardrail or Guardrail.G4.value, found.reason)
    if not text or len(text) > MAX_TEXT or "\n" in p.text.strip():
        return checked.reject(Guardrail.G3.value, NOT_ONE_LINE)
    numbers = grounding.verify_numbers(text, quote)
    if not numbers.passed:
        return checked.reject(numbers.guardrail or Guardrail.G5.value, numbers.reason)
    if any(v is not None for v in target):
        metric, _, value, unit = target
        if None in target or metric not in {m.value for m in IntentMetric}:
            return checked.reject(Guardrail.G5.value, "the target is incomplete")
        if not _unit_fits(str(metric), str(unit)):
            return checked.reject(Guardrail.G5.value, "the unit doesn't fit the metric")
        if not _value_in(float(value or 0), quote):
            return checked.reject(Guardrail.G5.value, f"number not found in the quote: {value:g}")
    roles = grounding.verify_roles(roles_named(text, groups), cited_text, groups)
    if not roles.passed:
        return checked.reject(roles.guardrail or Guardrail.G5.value, roles.reason)
    return checked


# --- IX_compare -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IntentItem:
    """A confirmed statement as sent: its ref, and the words a conflict may quote from it."""

    ref: str
    intent_id: str
    kind: str
    label: str
    words: str


def documented_refs(sources: list[SourcePassages]) -> list[SourcePassages]:
    """The documents with refs unique across all of them (d1, d2, …), in the order given."""
    out, n = [], 0
    for src in sources:
        segments = []
        for s in src.segments:
            n += 1
            segments.append(s.model_copy(update={"ref": f"d{n}"}))
        out.append(SourcePassages(src.source_id, src.source_name, src.kind, segments))
    return out


def compare_blocks(
    items: list[IntentItem], documents: list[SourcePassages]
) -> list[dict[str, object]]:
    esc = prompts.escape
    lines = ["<intent>"]
    lines += [f'<statement id="{esc(i.ref)}" kind="{esc(i.kind)}" label="{esc(i.label)}">'
              f"{esc(i.words)}</statement>" for i in items]  # fmt: skip
    lines.append("</intent>")
    lines += [prompts.render_source(f"s{n}", d.kind, d.segments)
              for n, d in enumerate(documents, start=1)]  # fmt: skip
    return [{"type": "text", "text": "\n".join(lines)}]


def compare(
    sessions: Sessions,
    ctx: AiContext,
    items: list[IntentItem],
    documents: list[SourcePassages],
    job_id: str,
) -> Result[list[ai_schemas.IXConflict]]:
    blocks = compare_blocks(items, documents)
    match call_stage(sessions, ctx, COMPARE_STAGE, COMPARE_NAME, blocks,
                     ai_schemas.IXCompareOutput, job_id):  # fmt: skip
        case Err() as err:
            return err
        case Ok(value=output):
            assert isinstance(output, ai_schemas.IXCompareOutput)
            return Ok(list(output.conflicts))


def check_conflict(
    c: ai_schemas.IXConflict,
    items: dict[str, IntentItem],
    documents: list[SourcePassages],
    groups: list[list[str]],
    terms: list[NameReplacement],
) -> Checked:
    passages = {s.ref: s for d in documents for s in d.segments}
    item = items.get(c.intent_ref)
    cited = [passages[r] for r in c.segment_ids if r in passages]
    conflict = redaction.hide(" ".join(c.conflict.split()), terms)
    checked = Checked(
        fields={
            "intent_id": item.intent_id if item else "",
            "segment_ids": [s.segment_id for s in cited],
            "quote": redaction.hide(c.documented_quote.strip(), terms),
            "intent_quote": redaction.hide(c.intent_quote.strip(), terms),
            "conflict_text": conflict,
        },
        cited=cited,
        words=conflict,
    )
    if not c.intent_quote.strip() or not c.documented_quote.strip() or not c.segment_ids:
        return checked.reject(Guardrail.IX1.value, "a design gap must quote both sides")
    if not 0 < len(conflict.split()) <= MAX_CONFLICT_WORDS:
        return checked.reject(Guardrail.IX1.value, "the conflict isn't described in 1 to 25 words")
    if item is None:
        return checked.reject(Guardrail.G3.value, "names a statement that wasn't sent")
    outcome = grounding.verify_segments(c.segment_ids, passages.keys())
    if not outcome.passed:
        return checked.reject(outcome.guardrail or Guardrail.G3.value, outcome.reason)
    intent_side = grounding.verify_quote(c.intent_quote, prompts.escape(item.words))
    if not intent_side.passed:
        return checked.reject(intent_side.guardrail or Guardrail.G4.value, intent_side.reason)
    cited_text = prompts.cited_text(cited)
    documented = grounding.verify_quote(c.documented_quote, cited_text)
    if not documented.passed:
        return checked.reject(documented.guardrail or Guardrail.G4.value, documented.reason)
    both = f"{item.words}\n{cited_text}"
    numbers = grounding.verify_numbers(conflict, both)
    if not numbers.passed:
        return checked.reject(numbers.guardrail or Guardrail.G5.value, numbers.reason)
    roles = grounding.verify_roles(roles_named(conflict, groups), both, groups)
    if not roles.passed:
        return checked.reject(roles.guardrail or Guardrail.G5.value, roles.reason)
    return checked


# --- IX_verify ---------------------------------------------------------------------------------


def verify_blocks(kept: list[Checked], kinds: dict[str, str]) -> list[dict[str, object]]:
    """Each item, then the passages it relies on. `kinds`: segment ID → its source kind."""
    esc = prompts.escape
    lines: list[str] = []
    for n, c in enumerate(kept, start=1):
        kind = "conflict" if "conflict_text" in c.fields else "statement"
        lines.append(f'<item id="v{n}" type="{kind}">{esc(c.words)}</item>')
        if kind == "conflict":
            lines.append(f"<intent>{esc(str(c.fields['intent_quote']))}</intent>")
        by_kind: dict[str, list[PromptSegment]] = {}
        for s in c.cited:
            by_kind.setdefault(kinds.get(s.segment_id, "other"), []).append(s)
        lines += [prompts.render_source(f"v{n}", k, segs) for k, segs in by_kind.items()]
    return [{"type": "text", "text": "\n".join(lines)}]


def verify(
    sessions: Sessions,
    ctx: AiContext,
    checked: list[Checked],
    kinds: dict[str, str],
    terms: list[NameReplacement],
    job_id: str,
) -> Result[None]:
    """The independent verifier over the proposals the checks kept (when it is switched on)."""
    kept = [c for c in checked if c.kept]
    if not ctx.verifier_enabled or not kept:
        return Ok(None)
    blocks = verify_blocks(kept, kinds)
    match call_stage(sessions, ctx, VERIFY_STAGE, VERIFY_NAME, blocks,
                     ai_schemas.IXVerifyOutput, job_id):  # fmt: skip
        case Err() as err:
            return err
        case Ok(value=output):
            assert isinstance(output, ai_schemas.IXVerifyOutput)
    verdicts = {v.item_ref: v for v in output.verdicts}
    for n, c in enumerate(kept, start=1):
        found = verdicts.get(f"v{n}")
        verdict = found.verdict if found else VerifierVerdict.PARTIAL.value
        c.fields["verifier_verdict"] = verdict
        if verdict == VerifierVerdict.NOT_SUPPORTED.value:
            reason = redaction.hide(found.reason, terms) if found else NO_VERDICT
            c.reject(Guardrail.IXV.value, reason)
    return Ok(None)
