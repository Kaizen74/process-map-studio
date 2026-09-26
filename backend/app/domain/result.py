"""Shared result type (PRD §3.2): every service returns Ok(value) or Err(kind, message, details).

Actions translate Err into the standard API error shape and plain-language messages.

Example:
    match parse_docx(path):
        case Ok(value=segments): ...
        case Err(kind=ErrorKind.IO, message=message): ...
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class ErrorKind(StrEnum):
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    IO = "io"
    AI_AUTH = "ai_auth"
    AI_RATE_LIMIT = "ai_rate_limit"
    AI_FORMAT = "ai_format"
    GROUNDING_FAILED = "grounding_failed"
    PUBLISH_BLOCKED = "publish_blocked"


@dataclass(frozen=True, slots=True)
class Ok[T]:
    """A successful result carrying its value."""

    value: T


def _empty_details() -> Mapping[str, object]:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class Err:
    """A failed result: what kind of failure, a plain-language message and structured details."""

    kind: ErrorKind
    message: str
    details: Mapping[str, object] = field(default_factory=_empty_details)

    @property
    def code(self) -> str:
        """The error code used in the standard API error shape, e.g. PUBLISH_BLOCKED."""
        return self.kind.value.upper()


type Result[T] = Ok[T] | Err
