"""HTTP mapping shared by routers: turn a Result into a response or the standard error shape.

Standard error shape (PRD §4):
    {"error": {"code": "PUBLISH_BLOCKED", "message": "Plain-language explanation", "details": {}}}
"""

from __future__ import annotations

from collections.abc import Mapping

from fastapi.responses import JSONResponse

from app.domain.result import Err, ErrorKind, Ok, Result

STATUS_BY_KIND: Mapping[ErrorKind, int] = {
    ErrorKind.VALIDATION: 422,
    ErrorKind.NOT_FOUND: 404,
    ErrorKind.CONFLICT: 409,
    ErrorKind.IO: 500,
    ErrorKind.AI_AUTH: 502,
    ErrorKind.AI_RATE_LIMIT: 503,
    ErrorKind.AI_FORMAT: 502,
    ErrorKind.GROUNDING_FAILED: 422,
    ErrorKind.PUBLISH_BLOCKED: 409,
}


class ApiError(Exception):
    """Raised by routers for an Err; the app's exception handler renders the standard shape."""

    def __init__(self, err: Err) -> None:
        super().__init__(err.message)
        self.err = err


def unwrap[T](result: Result[T]) -> T:
    """Return the value of Ok, or raise ApiError for Err."""
    match result:
        case Ok(value=value):
            return value
        case Err() as err:
            raise ApiError(err)


def error_response(
    status: int,
    code: str,
    message: str,
    details: Mapping[str, object] | None = None,
    request_id: str = "",
) -> JSONResponse:
    """The standard error shape; the request ID (if any) goes into details for Copy details."""
    body_details = dict(details or {})
    if request_id:
        body_details["request_id"] = request_id
    body = {"error": {"code": code, "message": message, "details": body_details}}
    return JSONResponse(status_code=status, content=body)


def err_response(err: Err, request_id: str = "") -> JSONResponse:
    return error_response(STATUS_BY_KIND[err.kind], err.code, err.message, err.details, request_id)
