"""Questions about another flow (2026-10-29, Eric; DECISIONS 83). The reading's open questions
(S1 unknowns) cover the whole document; on a one-flow map whose drafting set claims about other
flows aside, a question that points only at passages no step of the map uses is set aside too.
Deterministic: no AI judgement."""

from __future__ import annotations

from app.pipeline import s5_questions as s5


def test_a_question_whose_passages_no_step_uses_is_set_aside() -> None:
    used = {"a", "b"}
    asked = [["a"], ["x"], ["x", "b"], [], ["y", "z"]]
    assert s5.questions_aside(asked, used, claims_aside=True) == [1, 4]


def test_nothing_is_set_aside_when_the_documents_describe_only_this_flow() -> None:
    assert s5.questions_aside([["x"], ["y"]], {"a"}, claims_aside=False) == []


def test_a_question_without_a_passage_stays() -> None:
    assert s5.questions_aside([[]], set(), claims_aside=True) == []
