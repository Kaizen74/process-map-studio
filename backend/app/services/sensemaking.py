"""Deterministic Work-Sense helpers (PRD §3.12.3, §3.12.10 Step B): marker pre-tagging and the
account-type cues. Pure functions on text and the versioned lexicon; no database access. Pre-tags
are hints for the model to confirm or reject with a quote; they are never evidence on their own.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from pydantic import ValidationError

from app.domain.graph import Graph
from app.domain.models import ClaimRecord, PromptSegment
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import (
    SENSE_CLAIM_TYPES,
    AccountType,
    CoverageDimension,
    CoverageStatus,
    FollowUpQuestion,
    Lexicon,
    MarkerTag,
    SentenceAccount,
)
from app.services import grounding, prompts
from app.services.prompts import PROMPTS_DIR

LEXICON_FILE = PROMPTS_DIR / "marker_lexicon.json"
LEXICON_DAMAGED = "The app's marker list is missing or damaged."
_SENTENCE = re.compile(r"[^.!?]+(?:[.!?]+|$)")


def load_lexicon(path: Path = LEXICON_FILE) -> Result[Lexicon]:
    try:
        return Ok(Lexicon.model_validate(json.loads(path.read_text(encoding="utf-8"))))
    except (OSError, ValueError, ValidationError):
        return Err(ErrorKind.IO, LEXICON_DAMAGED, {"file": path.name})


@cache
def _pattern(phrase: str) -> re.Pattern[str]:
    """Whole words, any case; a phrase ending in a non-word character ("around T-") may run on
    into the next word ("around T-120")."""
    end = r"\b" if phrase[-1].isalnum() else ""
    return re.compile(rf"(?<![\w-]){re.escape(phrase)}{end}", re.IGNORECASE)


def pretag(text: str, lexicon: Lexicon) -> list[MarkerTag]:
    """Every marker the lexicon finds in `text`, in order of position. Within one family the
    longest phrase at a place wins ("first thing" over "first", "wait for" over "wait")."""
    tags: list[MarkerTag] = []
    for family, entry in lexicon.families.items():
        found: list[MarkerTag] = []
        for phrase in sorted(entry.phrases, key=len, reverse=True):
            for match in _pattern(phrase).finditer(text):
                if any(t.start <= match.start() < t.end for t in found):
                    continue
                found.append(
                    MarkerTag(
                        family=family,
                        pretag=entry.pretag,
                        phrase=match.group(0),
                        start=match.start(),
                        end=match.end(),
                    )
                )
        tags.extend(found)
    return sorted(tags, key=lambda t: (t.start, t.family))


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.findall(text) if s.strip()]


def pretag_account_type(text: str, lexicon: Lexicon) -> list[SentenceAccount]:
    """Each sentence's account (§3.12.3) from the official and lived cue lists: the first cue in
    the sentence decides; a sentence with no cue is `unclear` (the model may still change it,
    quoting its cue)."""
    result: list[SentenceAccount] = []
    for index, sentence in enumerate(sentences(text)):
        cues = [t for t in pretag(sentence, lexicon) if t.family in ("official", "lived")]
        first = cues[0] if cues else None
        account: AccountType = "unclear"
        if first is not None:
            account = "official" if first.family == "official" else "lived"
        result.append(
            SentenceAccount(
                index=index, text=sentence, account_type=account, cue=first.phrase if first else ""
            )
        )
    return result


# --- Work type (§3.12.4, §3.12.5) and know-how (§3.12.6): S3c and the panel (C2) ----------------

NOT_CLASSIFIED = "not_classified"
PROPOSED = "proposed"
CONFIRMED = "confirmed"  # Eric confirmed or changed it (V3b)
CONSTRAINT_FOR: dict[str, str | None] = {
    "clear": "rigid",
    "complicated": "governing",
    "complex": "enabling",
    "chaotic": "absent",
    "confused": None,
}
NEVER_AUTOMATED = frozenset({"complex", "chaotic"})


@dataclass(frozen=True, slots=True)
class CueCheck:
    """The cues that passed (each with the real passage IDs and the quote) and how many didn't."""

    cues: list[dict[str, object]]
    dropped: int


def validate_work_type_cues(
    cues: list[tuple[list[str], str]], passages: dict[str, PromptSegment]
) -> CueCheck:
    """A work-type cue counts only if it cites passages sent in the same call (G3) and its quote is
    found in them (G4), like every claim (§3.12.4: 'each must be quoted')."""
    kept: list[dict[str, object]] = []
    for refs, quote in cues:
        if not grounding.verify_segments(refs, passages).passed:
            continue
        cited = prompts.cited_text([passages[r] for r in refs])
        if grounding.verify_quote(quote, cited).passed:
            kept.append({"segment_ids": [passages[r].segment_id for r in refs], "quote": quote})
    return CueCheck(cues=kept, dropped=len(cues) - len(kept))


def work_type_fields(work_type: str | None, cues: list[dict[str, object]]) -> dict[str, object]:
    """The element fields for a proposed work type, or for one not classified (no valid cue)."""
    if work_type is None or not cues:
        return {"work_type": NOT_CLASSIFIED, "constraint_type": None, "work_type_basis": [],
                "work_type_status": NOT_CLASSIFIED}  # fmt: skip
    return {"work_type": work_type, "constraint_type": CONSTRAINT_FOR.get(work_type),
            "work_type_basis": cues, "work_type_status": PROPOSED}  # fmt: skip


ASHEN = ("artefacts", "skills", "heuristics", "experience", "natural_talent")


def knowledge_risk(ashen: dict[str, list[dict[str, object]]]) -> str:
    """§3.12.6, deterministic: high when heuristics and experience outweigh artefacts and skills
    and no more than two roles hold them, or when natural talent is cited; medium when skills
    outweigh artefacts (or heuristics and experience are spread over more roles); low when
    artefacts and skills cover it; `unknown` when nothing is known about it yet."""
    count = {k: len(ashen.get(k, [])) for k in ASHEN}
    if not any(count.values()):
        return "unknown"
    if count["natural_talent"]:
        return "high"
    tacit = ashen.get("heuristics", []) + ashen.get("experience", [])
    if len(tacit) > count["artefacts"] + count["skills"]:
        holders = {str(i.get("role", "")) for i in tacit}
        return "high" if len(holders) <= 2 else "medium"
    if count["skills"] > count["artefacts"]:
        return "medium"
    return "low"


def risk_reason(ashen: dict[str, list[dict[str, object]]], risk: str) -> str:
    """Why the knowledge risk is what it is, in one plain sentence (no blame, roles not people)."""
    count = {k: len(ashen.get(k, [])) for k in ASHEN}
    if risk == "unknown":
        return "The interviews don't yet say what this call needs; ask the know-how questions."
    if count["natural_talent"]:
        return "The SME says the role needs a natural aptitude, which is hard to pass on."
    tacit = count["heuristics"] + count["experience"]
    if risk == "high":
        return (
            "Rules of thumb and experience outweigh documents and skills, and few roles hold them."
        )
    if risk == "medium" and tacit > count["artefacts"] + count["skills"]:
        return (
            "Rules of thumb and experience outweigh documents and skills, but several roles hold "
            "them."
        )
    if risk == "medium":
        return "Learnable skills carry most of this call."
    return "Documents, tools and learnable skills cover this call."


# --- Coverage report (§3.12.8, criterion 50, A.8; C4) ------------------------------------------

# Every dimension, in report order, with the bank question that asks for it (Appendix F).
COVERAGE_QUESTIONS: dict[str, str] = {
    "trigger": "M2.1",
    "end_point": "M2.5",
    "step_spine": "M2.2",
    "handoffs": "M3.3",
    "decisions_and_criteria": "M4.3",
    "approvals": "M7.2",
    "exceptions": "M2.6",
    "raci": "M4.4",
    "work_and_wait_time": "M2.4",
    "kpis": "M7.1",
    "artefacts": "M7.4",
    "know_how": "M4.8",
    "stories": "",  # one question per kind of story not yet told
    "official_vs_lived": "M6.2",
    "sme_terms": "M0.2",
}
STORY_KINDS = {"went_well": "M5.1", "went_badly": "M5.2", "surprise": "M5.3"}
DECIDING = frozenset({"decision", "approval"})
STEPS = frozenset({"activity", "decision", "approval"})


def _by_count(count: int) -> CoverageStatus:
    """The plain rule: nothing said is missing, one mention is thin, two or more is covered."""
    return "missing" if count == 0 else "thin" if count == 1 else "covered"


def _share(done: int, of: int) -> CoverageStatus:
    return "missing" if done == 0 else "covered" if done == of else "thin"


def _text(value: object) -> bool:
    return bool(str(value or "").strip())


def coverage_dimensions(
    claims: list[ClaimRecord], done: Graph
) -> tuple[dict[str, CoverageDimension], dict[str, list[str]]]:
    """What the interviews covered (deterministic, §3.12.8): each dimension's status and evidence
    count from the checked interview claims and items, and the As done view; with, per dimension,
    what a follow-up is about (decisions without know-how, story kinds not told, lines whose
    order wasn't stated)."""
    # The interviews' claims about the flow carry an account type (B.28); their stories,
    # know-how, terms and decision information are items of their own (C1).
    items = [c for c in claims if c.claim_type in SENSE_CLAIM_TYPES]
    flow = [c for c in claims if c.account_type is not None and c not in items]

    def counted(*types: str) -> int:
        return sum(1 for c in flow if c.claim_type in types)

    def items_of(claim_type: str) -> list[ClaimRecord]:
        return [c for c in items if c.claim_type == claim_type]

    dims: dict[str, CoverageDimension] = {}
    about: dict[str, list[str]] = {}

    def put(name: str, status: CoverageStatus, count: int, note: str = "") -> None:
        dims[name] = CoverageDimension(status=status, evidence_count=count, note=note)

    put("trigger", *_counted(counted("trigger")))
    elements = {e.id: e for e in done.elements}
    ends = {e.id for e in done.elements if e.kind == "end"}
    last = [elements[x.from_] for x in done.edges if x.to in ends and x.from_ in elements]
    heard = [
        e for e in last
        if any(v.source_kind == "interview_transcript" and v.segment_id and v.verified
               and v.stance == "supports" for v in e.evidence)
    ]  # fmt: skip
    end_count = sum(
        1 for e in heard for v in e.evidence
        if v.source_kind == "interview_transcript" and v.segment_id and v.verified
        and v.stance == "supports"
    )  # fmt: skip
    put("end_point", *_counted(end_count),
        f"Heard for: {', '.join(e.label for e in heard)}" if heard else "")  # fmt: skip

    spine = counted("activity", "decision", "approval")
    unstated = [
        f"{elements[x.from_].label} → {elements[x.to].label}"
        for x in done.edges
        if (x.kind == "gap" or x.sequence_basis == "narration_order")
        and x.from_ in elements and x.to in elements
    ]  # fmt: skip
    status = _by_count(spine)
    if unstated and status == "covered":
        status = "thin"
    put("step_spine", status, spine,
        f"Order not stated: {'; '.join(unstated)}" if unstated else "")  # fmt: skip
    about["step_spine"] = ["; ".join(unstated)] if unstated else [""]

    put("handoffs", *_counted(counted("handoff")))
    put("decisions_and_criteria", *_counted(counted("decision", "threshold")))
    put("approvals", *_counted(counted("approval")))
    exceptions = sum(
        1 for c in flow
        if c.claim_type == "exception" or _text(c.payload.get("variation_condition"))
    )  # fmt: skip
    put("exceptions", *_counted(exceptions))
    raci = sum(
        1 for c in flow
        if c.claim_type == "raci"
        or _text(c.payload.get("accountable_role")) or _text(c.payload.get("decider_role"))
    )  # fmt: skip
    put("raci", *_counted(raci))
    timed = sum(
        1 for c in flow if c.claim_type == "duration" or _text(c.payload.get("duration_text"))
    )
    put("work_and_wait_time", *_counted(timed))
    put("kpis", *_counted(counted("kpi")))
    artefacts = [c for c in items_of("know_how") if c.payload.get("category") == "artefacts"]
    put("artefacts", *_counted(len(artefacts)))

    know_how = items_of("know_how")
    points = [e for e in done.elements if e.kind in DECIDING]
    linked = {k for c in know_how for k in _about_steps(c)}
    unknown = [e.label for e in points if e.stable_key not in linked]
    put("know_how", _share(len(points) - len(unknown), len(points)), len(know_how),
        f"No know-how yet: {', '.join(unknown)}" if unknown else "")  # fmt: skip
    about["know_how"] = unknown

    told = items_of("story")
    kinds = {str(c.payload.get("fragment_type", "")) for c in told}
    missing_kinds = [k for k in STORY_KINDS if k not in kinds]
    put("stories", _share(len(STORY_KINDS) - len(missing_kinds), len(STORY_KINDS)), len(told),
        f"Not yet told: {', '.join(k.replace('_', ' ') for k in missing_kinds)}"
        if missing_kinds else "")  # fmt: skip
    about["stories"] = missing_kinds

    both = [
        e.label for e in done.elements
        if e.kind in STEPS and e.account_summary.official and e.account_summary.lived
    ]  # fmt: skip
    put("official_vs_lived", "covered" if both else "missing", len(both),
        f"Both accounts on {len(both)} step{'s' if len(both) != 1 else ''}: {', '.join(both)}"
        if both else "")  # fmt: skip
    put("sme_terms", *_counted(len(items_of("sme_term"))))
    return {name: dims[name] for name in COVERAGE_QUESTIONS}, about


def _counted(count: int) -> tuple[CoverageStatus, int]:
    return _by_count(count), count


def _about_steps(record: ClaimRecord) -> list[str]:
    about = record.payload.get("about_steps")
    return [str(k) for k in about] if isinstance(about, list) else []


def follow_up_questions(
    dims: dict[str, CoverageDimension], about: dict[str, list[str]], wording: dict[str, str]
) -> list[FollowUpQuestion]:
    """A ready-to-ask question for each thin or missing dimension, word for word from the bank;
    one per decision without know-how and one per kind of story not yet told."""
    out: list[FollowUpQuestion] = []
    for name, dim in dims.items():
        if dim.status == "covered":
            continue
        if name == "stories":
            for k in about.get("stories", []):
                qid = STORY_KINDS[k]
                out.append(FollowUpQuestion(dimension=name, question_id=qid,
                                            question=wording[qid]))  # fmt: skip
            continue
        qid = COVERAGE_QUESTIONS[name]
        targets = about.get(name) or [""]
        out += [
            FollowUpQuestion(dimension=name, question_id=qid, question=wording[qid], about=t)
            for t in targets
        ]
    return out


# --- Reflective probes (Appendix F F2; A.10; C4c) ----------------------------------------------

PROBE_ID = "F2"
PROBE_SLOT = "[SME's own words, ≤ 20 words]"
PROBE_WORDS = 20


def probe_claims(claims: list[ClaimRecord]) -> list[tuple[ClaimRecord, str]]:
    """The verified interview words worth playing back (F2: "verified quotes carrying
    constraints, risks or stated reasons"), each once, at most 20 words, in reading order: the
    claim's quote, or for a longer quote the stated reason it carries (checked word for word by
    S1). Words are never cut."""
    out: list[tuple[ClaimRecord, str]] = []
    seen: set[str] = set()
    for c in claims:
        interview = c.account_type is not None or c.claim_type in SENSE_CLAIM_TYPES
        reason = str(c.payload.get("stated_reason") or "").strip()
        carries = (
            c.claim_type == "constraint"
            or (c.claim_type == "capability" and c.payload.get("kind") == "weakness")
            or bool(reason)
        )
        words = c.quote if len(c.quote.split()) <= PROBE_WORDS else reason
        key = grounding.normalise_text(words)
        if not (interview and carries) or not key or key in seen:
            continue
        if len(words.split()) > PROBE_WORDS:
            continue
        seen.add(key)
        out.append((c, words))
    return out


def probe_question(wording: str, quote: str) -> str:
    """The bank's F2 wording with the SME's words in its slot (a final full stop or semicolon
    is dropped where the quote meets the bank's own punctuation)."""
    return wording.replace(PROBE_SLOT, f"“{quote.strip().rstrip('.;')}”")
