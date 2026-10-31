"""One read-only request's repeated reads, read once (2026-10-31, Eric: "make the quality card
faster"; DECISIONS 91). Inside `read_only`, a remembered read returns a copy of its first result
and any write is refused, so a remembered row is never out of date; outside it, nothing changes."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import event, update
from sqlalchemy.orm import Session

from app.db import session_scope
from app.repositories import engagements, read_memo, redaction
from app.repositories.tables import RedactionTerm


def selects(session: Session) -> list[str]:
    seen: list[str] = []

    def count(*args: Any) -> None:
        seen.append(str(args[2]))

    event.listen(session.get_bind(), "before_cursor_execute", count)
    return seen


def setup(session: Session) -> str:
    eid = engagements.create(session, {"name": "Load control"}).id
    redaction.add(session, engagement_id=eid, term="Priya Nair", replacement="Load controller",
                  origin="manual")  # fmt: skip
    return eid


def test_inside_a_read_only_request_a_read_runs_once_and_each_caller_gets_its_own_copy(
    sessions: Any,
) -> None:
    with session_scope(sessions) as s:
        eid = setup(s)
        seen = selects(s)
        with read_memo.read_only(s):
            first = redaction.list_terms(s, eid, ["manual"])
            first[0].term = "changed by one caller"
            first.append(first[0])
            second = redaction.list_terms(s, eid, ["manual"])
        reads = [q for q in seen if "FROM redaction_terms" in q]
        assert len(reads) == 1
        assert [t.term for t in second] == ["Priya Nair"]  # the first caller's change isn't seen


def test_outside_a_read_only_request_every_read_goes_to_the_database(sessions: Any) -> None:
    with session_scope(sessions) as s:
        eid = setup(s)
        seen = selects(s)
        redaction.list_terms(s, eid, ["manual"])
        redaction.list_terms(s, eid, ["manual"])
        assert len([q for q in seen if "FROM redaction_terms" in q]) == 2
        assert read_memo.MEMO not in s.info


def test_different_arguments_are_read_separately(sessions: Any) -> None:
    with session_scope(sessions) as s:
        eid = setup(s)
        with read_memo.read_only(s):
            assert len(redaction.list_terms(s, eid, ["manual"])) == 1
            assert redaction.list_terms(s, eid, ["speaker_map"]) == []


def test_a_write_inside_a_read_only_request_is_refused(sessions: Any) -> None:
    with session_scope(sessions) as s:
        eid = setup(s)
        with read_memo.read_only(s), pytest.raises(read_memo.WriteInReadOnly):
            redaction.add(s, engagement_id=eid, term="Sam", replacement="Ramp", origin="manual")
        s.rollback()
    with session_scope(sessions) as s:
        with read_memo.read_only(s), pytest.raises(read_memo.WriteInReadOnly):
            s.execute(update(RedactionTerm).values(replacement="Ramp"))
        s.rollback()


def test_the_memory_ends_with_the_request_and_writes_work_again(sessions: Any) -> None:
    with session_scope(sessions) as s:
        eid = setup(s)
        with read_memo.read_only(s):
            redaction.list_terms(s, eid, ["manual"])
            with read_memo.read_only(s):  # an inner request shares the outer one's memory
                redaction.list_terms(s, eid, ["manual"])
            assert read_memo.MEMO in s.info
        assert read_memo.MEMO not in s.info
        redaction.add(s, engagement_id=eid, term="Sam", replacement="Ramp", origin="manual")
        assert len(redaction.list_terms(s, eid, ["manual"])) == 2
