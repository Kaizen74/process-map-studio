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

from app.domain.models import PromptSegment
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import AccountType, Lexicon, MarkerTag, SentenceAccount
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
