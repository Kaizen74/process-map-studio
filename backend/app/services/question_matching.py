"""Question-anchored segmentation, step A (PRD v1.10 §3.12.10): which guide or template question
an interviewer turn is asking. First an explicit tag at the start of the turn ("[M2.2] Walk me
through …"), otherwise wording similarity of at least 0.60 (difflib) against the questions.

Pure functions; the questions are passed in (a template's or, from phase P4c, a tailored guide's).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from difflib import SequenceMatcher

from app.domain.interview import AnsweredTurn, BankQuestion, QuestionMatch, Turn

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


def match_turn(
    text: str, questions: Sequence[BankQuestion], tag_questions: Sequence[BankQuestion] = ()
) -> QuestionMatch | None:
    """The question an interviewer turn asks, or None for free conversation. Wording is compared
    with `questions` (the guide's); an explicit tag may also name any of `tag_questions` (the
    whole bank: the interviewer said which question it is)."""
    known = {q.id for q in questions} | {q.id for q in tag_questions}
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


def answer_blocks(
    turns: Sequence[Turn],
    questions: Sequence[BankQuestion],
    tag_questions: Sequence[BankQuestion] = (),
) -> list[AnsweredTurn]:
    """Step A over a whole transcript: each matched interviewer turn opens an answer block; the
    SME turns that follow belong to it until the next matched question. An unmatched interviewer
    turn is free conversation: it is still extracted and does not end the block."""
    current: str | None = None
    result: list[AnsweredTurn] = []
    for turn in turns:
        if not turn.is_interviewer:
            result.append(AnsweredTurn(seq=turn.seq, question_id=current, asked=False))
            continue
        found = match_turn(turn.text, questions, tag_questions)
        if found is not None:
            current = found.question_id
        result.append(
            AnsweredTurn(
                seq=turn.seq,
                question_id=found.question_id if found else None,
                asked=found is not None,
                match=found,
            )
        )
    return result
