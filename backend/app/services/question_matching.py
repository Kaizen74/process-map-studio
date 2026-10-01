"""Question-anchored segmentation, step A (PRD v1.10 §3.12.10): which guide or template question
an interviewer turn is asking. First an explicit tag at the start of the turn ("[M2.2] Walk me
through …"), otherwise wording similarity of at least 0.60 (difflib) against the questions.

Pure functions; the questions are passed in (a template's or, from phase P4c, a tailored guide's).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher

from app.domain.interview import BankQuestion, QuestionMatch

THRESHOLD = 0.60
_TAG = re.compile(r"^\s*\[(?P<id>L\d|M\d\.(?:\d|s\d)|F\d)\]\s*")
_ASHEN_LETTER = re.compile(r"\((?:[ASHEN])(?:, [^)]*)?\)")


def normalise(text: str) -> str:
    """Lower case, words only: punctuation, quote marks and dashes don't count."""
    return " ".join(re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower().replace("\u2019", "'")))


def _phrasings(question: BankQuestion) -> list[str]:
    """The ways a question can be asked: its whole wording and each part of a combined one
    (M4.5 asks five ASHEN questions, one at a time)."""
    whole = _ASHEN_LETTER.sub("", question.wording)
    parts = [p for p in whole.split(" · ") if p.strip()]
    return [normalise(p) for p in [whole, *parts] if normalise(p)]


def match_turn(text: str, questions: Sequence[BankQuestion]) -> QuestionMatch | None:
    """The question an interviewer turn asks, or None for free conversation."""
    known = {q.id for q in questions}
    tag = _TAG.match(text)
    if tag and tag.group("id") in known:
        return QuestionMatch(question_id=tag.group("id"), method="tag", score=1.0)
    spoken = normalise(text[tag.end() :] if tag else text)
    if not spoken:
        return None
    best: tuple[float, str] | None = None
    for question in questions:
        for phrasing in _phrasings(question):
            score = SequenceMatcher(None, spoken, phrasing, autojunk=False).ratio()
            if best is None or score > best[0]:
                best = (score, question.id)
    if best is None or best[0] < THRESHOLD:
        return None
    return QuestionMatch(question_id=best[1], method="wording", score=round(best[0], 2))
