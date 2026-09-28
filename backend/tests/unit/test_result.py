"""Shared result type (PRD §3.2)."""

from __future__ import annotations

import dataclasses

import pytest

from app.domain.result import Err, ErrorKind, Ok, Result


def divide(a: int, b: int) -> Result[float]:
    if b == 0:
        return Err(ErrorKind.VALIDATION, "Cannot divide by zero.", {"b": b})
    return Ok(a / b)


def test_ok_carries_value() -> None:
    assert divide(6, 3) == Ok(2.0)


def test_err_carries_kind_message_details_and_code() -> None:
    result = divide(1, 0)
    assert isinstance(result, Err)
    assert result.kind is ErrorKind.VALIDATION
    assert result.message == "Cannot divide by zero."
    assert dict(result.details) == {"b": 0}
    assert result.code == "VALIDATION"


def test_pattern_matching_works() -> None:
    match divide(1, 0):
        case Ok():
            pytest.fail("expected Err")
        case Err(kind=kind, message=message):
            assert kind == "validation"
            assert "zero" in message


def test_err_details_default_is_empty_and_read_only() -> None:
    err = Err(ErrorKind.NOT_FOUND, "Not found.")
    assert dict(err.details) == {}
    with pytest.raises(TypeError):
        err.details["x"] = 1  # type: ignore[index]


def test_results_are_immutable() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Ok(1).value = 2  # type: ignore[misc]


def test_error_kinds_match_prd() -> None:
    assert {k.value for k in ErrorKind} == {
        "validation",
        "not_found",
        "conflict",
        "io",
        "ai_auth",
        "ai_rate_limit",
        "ai_format",
        "grounding_failed",
        "publish_blocked",
    }


def test_an_error_can_carry_the_api_code_the_prd_names() -> None:
    # PRD §4 names codes such as 409 BRIEF_NOT_APPROVED for cases of an existing kind.
    plain = Err(ErrorKind.CONFLICT, "Refused.")
    specific = Err(ErrorKind.CONFLICT, "Approve the brief first.", api_code="BRIEF_NOT_APPROVED")
    assert (plain.code, specific.code) == ("CONFLICT", "BRIEF_NOT_APPROVED")
    assert specific.kind is ErrorKind.CONFLICT
