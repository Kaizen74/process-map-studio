"""The interview question bank (`app/prompts/question_bank.json`; PRD v1.10 Appendix F) and the
wording checks it must pass (§3.12.9, F.1 principle 8, F.8 rules 6 and 8).

The bank is compared with the PRD's own Appendix F tables, so no question, probe or target can
change without the PRD changing too (or a logged decision)."""

from __future__ import annotations

import re
from functools import cache

import pytest

from app.domain.enums import InterviewType
from app.domain.interview import QuestionBank
from app.services import wording
from tests import sample_interview
from tests.paths import BACKEND_ROOT, REPO_ROOT

BANK_FILE = BACKEND_ROOT / "app" / "prompts" / "question_bank.json"
# F.8 rule 6: never dropped when a guide is shortened.
NEVER_DROPPED = {"M2.2", "M2.3", "M6.1", "L3", "L4", "L6"}
BEFORE_CONTRAST = {"L", "M0", "M1", "M2", "M3", "M4", "M5", "F"}


@cache
def bank() -> QuestionBank:
    return QuestionBank.model_validate_json(BANK_FILE.read_text(encoding="utf-8"))


def appendix_f_rows() -> dict[str, list[str]]:
    """Question ID → the other cells of its row in the PRD's Appendix F tables (F.4 to F.6)."""
    prd = (REPO_ROOT / "PRD_ProcessMapStudio.md").read_text(encoding="utf-8")
    appendix = prd.split("## Appendix F", 1)[1].split("### F.7", 1)[0]
    rows: dict[str, list[str]] = {}
    for line in appendix.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and re.fullmatch(r"(?:L\d|M\d\.(?:\d|s\d)|F\d)", cells[0]):
            rows[cells[0]] = cells[1:]
    return rows


def plain(text: str) -> str:
    """PRD cell text without Markdown emphasis and quote marks."""
    return re.sub(r"\s+", " ", text.replace('"', "").replace("**", "").replace("`", "")).strip()


def test_every_appendix_f_question_is_in_the_bank_word_for_word() -> None:
    rows = appendix_f_rows()
    b = bank()
    assert [q.id for q in b.questions] == list(rows)  # same questions, same order
    assert len(rows) == 58
    for q in b.questions:
        cells = rows[q.id]
        spoken = " ".join(x for x in (q.lead_in, q.wording) if x)
        told = f"{spoken} ({q.note})" if q.note else spoken
        assert plain(told) == plain(cells[0]), q.id
        if q.movement == "F":  # ID · Template · Built from · Translation
            assert (plain(q.built_from), plain(q.translation)) == (plain(cells[1]), plain(cells[2]))
            continue
        with_probes = len(cells) == 4  # ID · Question · Probes · Targets · Translation
        if with_probes:
            probes = [] if cells[1] == "—" else [plain(p) for p in cells[1].split(" · ")]
            assert [plain(p) for p in q.probes] == probes, q.id
        else:
            assert q.probes == [], q.id
        targets, translation = cells[-2], cells[-1]
        assert plain(", ".join(q.targets)) == plain("" if targets == "—" else targets), q.id
        assert plain(q.translation) == plain(translation), q.id


def test_each_question_has_an_id_movement_wording_and_priority() -> None:
    b = bank()
    movements = {m.id for m in b.movements}
    ids = [q.id for q in b.questions]
    assert len(ids) == len(set(ids))
    for q in b.questions:
        assert q.movement in movements and q.wording.strip() and q.priority in {"core", "standard"}
        assert q.movement == q.id.split(".")[0] if "." in q.id else q.movement in {"L", "F"}
    core = {q.id for q in b.questions if q.priority == "core"}
    assert core == NEVER_DROPPED | {q.id for q in b.questions if q.movement == "M5"}


def test_the_minute_plans_sum_to_60_60_and_30() -> None:
    b = bank()
    assert set(b.templates) == set(InterviewType)
    totals = {kind: sum(s.minutes for s in t.sections) for kind, t in b.templates.items()}
    assert totals == {"landscape": 60, "practice": 60, "follow_up": 30}
    assert {kind: t.minutes for kind, t in b.templates.items()} == totals
    # Practice follows the eight movements with the F.9 minutes.
    practice = [s.minutes for s in b.templates[InterviewType.PRACTICE].sections]
    assert practice == [3, 6, 14, 6, 12, 9, 6, 4]
    assert practice == [m.minutes for m in b.movements if m.id.startswith("M")]


def test_every_template_row_is_a_bank_question() -> None:
    b = bank()
    ids = {q.id for q in b.questions}
    for kind in InterviewType:
        asked = b.template_ids(kind)
        assert asked and set(asked) <= ids, kind
    assert b.template_ids(InterviewType.PRACTICE) == [
        q.id for q in b.questions if q.id.startswith("M")
    ][:24] + ["M5.1", "M5.s1", "M5.s2", "M5.s3", "M5.s4", "M5.s5", "M5.2", "M5.3", "M5.4"] + [
        q.id for q in b.questions if q.movement in {"M6", "M7"}
    ]
    assert b.template_ids(InterviewType.LANDSCAPE) == [
        "M0.1", "L1", "L2", "L3", "L4", "L5", "L6", "L7",
        "M5.1", "M5.s1", "M5.s2", "M5.s3", "M5.2", "M7.1", "M7.5", "M7.6",
    ]  # fmt: skip
    assert b.template_ids(InterviewType.FOLLOW_UP) == [
        "M0.1", "F1", "F2", "F3", "F4", "F5", "F6", "M7.1", "M7.2", "M7.3", "M7.4", "M7.5", "M7.6"
    ]  # fmt: skip


def all_text(b: QuestionBank) -> str:
    return b.model_dump_json()


def test_no_banned_words_in_the_bank() -> None:
    assert wording.banned_words(all_text(bank())) == []


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("A violation of the rule", ["violation"]),
        ("Non-compliance noted", ["non-compliance"]),
        ("It was an error by the lead", ["error by"]),
        ("A workaround under pressure", []),
        ("An error in the form", []),
    ],
)
def test_banned_words_are_found_as_whole_phrases(text: str, found: list[str]) -> None:
    assert wording.banned_words(text) == found


def test_no_sop_claims_before_the_contrast_movement() -> None:
    b = bank()
    for q in b.questions:
        spoken = " ".join([q.lead_in, q.wording, *q.probes])
        if q.movement in BEFORE_CONTRAST:
            assert wording.sop_claims(spoken) == [], q.id
    # The detector does find the claims M6 is allowed to make.
    assert wording.sop_claims(b.question("M6.5").wording) == ["The procedure"]
    assert wording.sop_claims(b.question("M6.5").lead_in) == ["SOP"]
    assert wording.sop_claims(b.question("M6.2").wording) == ["the procedure"]
    # Offering "following a procedure" as a way to describe a story is not a claim (M5.s1).
    assert wording.sop_claims(b.question("M5.s1").wording) == []


# Capitalised words the questions may use; anything else capitalised mid-sentence could be a name.
ALLOWED_CAPITALS = {"SME's", "SOP", "SOP-derived", "ASHEN", "M6", "A", "B", "S", "H", "E", "N"}


def test_no_personal_names_in_the_questions() -> None:
    b = bank()
    names = [*sample_interview.NAMES, "Priya", "Nair"]
    text = all_text(b)
    assert [n for n in names if re.search(rf"\b{re.escape(n)}\b", text)] == []
    for q in b.questions:
        for part in [q.lead_in, q.wording, *q.probes]:
            for sentence in re.split(r"(?<=[.?!:—])\s+|\s·\s|\(|\[", part):
                words = re.findall(r"[A-Za-z][\w'-]*", sentence)
                odd = [w for w in words[1:] if w[0].isupper() and w not in ALLOWED_CAPITALS]
                assert odd in ([], ["I"], ["I", "I"]), (q.id, odd)
