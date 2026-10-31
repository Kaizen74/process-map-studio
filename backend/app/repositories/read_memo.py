"""One read-only request's repeated reads, read once (2026-10-31, DECISIONS 91).

The quality card read the same rows up to ten times while it worked out the map, the exports and
the checks. Inside `read_only(session)`, a read wrapped with `@remembered` runs once for the same
arguments and every caller gets its own copy of the result; any write in that time is refused, so
a remembered row can never be out of date. Outside `read_only`, every read goes to the database as
before.
"""

from __future__ import annotations

import copy
import functools
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any, Concatenate

from sqlalchemy import event
from sqlalchemy.orm import ORMExecuteState, Session

MEMO = "read_memo"  # session.info key: the remembered reads of the current read-only request


class WriteInReadOnly(RuntimeError):
    """A read-only request tried to write; its remembered reads could go out of date."""


def _key(value: Any) -> Any:
    if isinstance(value, list | tuple):
        return tuple(_key(v) for v in value)
    if isinstance(value, set | frozenset):
        return frozenset(value)
    if isinstance(value, dict):
        return tuple(sorted((k, _key(v)) for k, v in value.items()))
    return value


def remembered[**P, T](
    read: Callable[Concatenate[Session, P], T],
) -> Callable[Concatenate[Session, P], T]:
    """Run `read` once per read-only request for the same arguments; hand out copies."""

    @functools.wraps(read)
    def wrapper(session: Session, /, *args: P.args, **kwargs: P.kwargs) -> T:
        memo: dict[Any, Any] | None = session.info.get(MEMO)
        if memo is None:
            return read(session, *args, **kwargs)
        key = (read.__module__, read.__qualname__, _key(args), _key(kwargs))
        if key not in memo:
            memo[key] = read(session, *args, **kwargs)
        return copy.deepcopy(memo[key])  # type: ignore[no-any-return]

    return wrapper


def _refuse(*_: Any) -> None:
    raise WriteInReadOnly("A read-only request tried to write.")


def _refuse_statement(state: ORMExecuteState) -> None:
    if not state.is_select:
        _refuse()


@contextmanager
def read_only(session: Session) -> Iterator[None]:
    """Remember reads and refuse writes until the block ends; an inner block shares the outer."""
    if MEMO in session.info:
        yield
        return
    session.info[MEMO] = {}
    event.listen(session, "before_flush", _refuse)
    event.listen(session, "do_orm_execute", _refuse_statement)
    try:
        yield
    finally:
        event.remove(session, "do_orm_execute", _refuse_statement)
        event.remove(session, "before_flush", _refuse)
        session.info.pop(MEMO, None)
