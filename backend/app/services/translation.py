"""Deterministic verbatim-to-workflow translation rules (PRD §3.12.3, §3.12.10 step C,
§3.12.11). Pure functions on explicit inputs; no database access."""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.graph import AccountSummary


def account_summary(account_types: Iterable[str | None]) -> AccountSummary:
    """How many of a step's interview claims give the official, lived or unclear account
    (claims from other kinds of source carry no account and are not counted)."""
    types = [t for t in account_types if t is not None]
    return AccountSummary(
        official=types.count("official"), lived=types.count("lived"), unclear=types.count("unclear")
    )


def practice_described(summary: AccountSummary) -> bool | None:
    """§3.12.3: the lived account is the practice voice. True when a lived claim describes the
    step; False when only the official account does ("Practice not described"); None when the
    interview gives no account of it either way."""
    if summary.lived:
        return True
    if summary.official:
        return False
    return None
