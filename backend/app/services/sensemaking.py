"""Deterministic Work-Sense helpers (PRD §3.12.3, §3.12.10 Step B): marker pre-tagging and the
account-type cues. Pure functions on text and the versioned lexicon; no database access. Pre-tags
are hints for the model to confirm or reject with a quote; they are never evidence on their own.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path

from pydantic import ValidationError

from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import AccountType, Lexicon, MarkerTag, SentenceAccount
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
