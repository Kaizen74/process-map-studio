"""AI service (PRD §3.2, §3.7): the only module that imports the anthropic SDK.

Phase P0b provides the Models API calls used by Settings (list_models, get_model). The
Messages API call (call_claude) and web search arrive in phases P3 and P10.

Verified against anthropic 1.8.0 (see DECISIONS.md): `Anthropic(api_key=, max_retries=,
timeout=, http_client=)`, `client.models.retrieve(model_id)` and `client.models.list()` return
`ModelInfo`, whose `capabilities` is a typed `ModelCapabilities` (pdf_input, structured_outputs,
effort.low/medium/high/xhigh/max, each with `.supported`). The SDK retries 408/409/429/5xx and
connection errors (max_retries), never 401/403/404.

Mock mode (MOCK_CLAUDE=1) returns fixtures from `<fixtures_dir>/<stage_id>/<key>.json`, falling
back to `default.json`; fixtures are validated with the SDK's own `ModelInfo` type.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import anthropic
import httpx2
from anthropic.types import ModelInfo

from app.domain.models import ModelSummary
from app.domain.result import Err, ErrorKind, Ok, Result

EFFORT_ORDER = ("low", "medium", "high", "xhigh", "max")
MODELS_TIMEOUT_S = 20.0
# PRD §3.7: retry once on rate-limit or overload; the SDK never retries auth errors.
MAX_RETRIES = 1


@dataclass(frozen=True, slots=True)
class AiConnection:
    """Everything a call needs, passed explicitly (the service reads no global state)."""

    api_key: str
    mock: bool
    fixtures_dir: Path
    # Tests pass an httpx2 client with a mock transport; None uses the SDK default.
    http_client: httpx2.Client | None = None

    def __repr__(self) -> str:  # never show the key, even in debug output
        return f"AiConnection(mock={self.mock}, fixtures_dir={self.fixtures_dir!s})"


def _client(conn: AiConnection) -> anthropic.Anthropic:
    return anthropic.Anthropic(
        api_key=conn.api_key,
        max_retries=MAX_RETRIES,
        timeout=MODELS_TIMEOUT_S,
        http_client=conn.http_client,
    )


def _summary(info: ModelInfo) -> ModelSummary:
    caps = info.capabilities
    if caps is None:
        return ModelSummary(
            id=info.id,
            display_name=info.display_name,
            pdf_input=False,
            structured_outputs=False,
            effort_levels=[],
        )
    levels = []
    if caps.effort.supported:
        for level in EFFORT_ORDER:
            support = getattr(caps.effort, level, None)
            if support is not None and support.supported:
                levels.append(level)
    return ModelSummary(
        id=info.id,
        display_name=info.display_name,
        pdf_input=caps.pdf_input.supported,
        structured_outputs=caps.structured_outputs.supported,
        effort_levels=levels,
    )


def _classify(exc: anthropic.AnthropicError) -> Err:
    """Turn an SDK error into the app's error kinds. Never includes the key or request body."""
    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return Err(ErrorKind.AI_AUTH, "The API key was rejected.", _status_details(exc))
    if isinstance(exc, anthropic.NotFoundError):
        return Err(ErrorKind.NOT_FOUND, "Not found.", _status_details(exc))
    if isinstance(
        exc,
        anthropic.RateLimitError | anthropic.OverloadedError | anthropic.ServiceUnavailableError,
    ):
        return Err(ErrorKind.AI_RATE_LIMIT, "Anthropic is busy.", _status_details(exc))
    if isinstance(exc, anthropic.APIStatusError):
        return Err(ErrorKind.IO, "Anthropic returned an error.", _status_details(exc))
    if isinstance(exc, anthropic.APIConnectionError):
        return Err(ErrorKind.IO, "Anthropic could not be reached.", {"reason": type(exc).__name__})
    return Err(ErrorKind.IO, "The AI service failed.", {"reason": type(exc).__name__})


def _status_details(exc: anthropic.APIStatusError) -> dict[str, object]:
    return {
        "status": exc.status_code,
        "anthropic_request_id": exc.request_id or "",
        "error_type": exc.type or "",
    }


def _fixture(conn: AiConnection, stage_id: str, key: str) -> Result[object]:
    folder = conn.fixtures_dir / stage_id
    for candidate in (folder / f"{key}.json", folder / "default.json"):
        if candidate.is_file():
            try:
                return Ok(json.loads(candidate.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as exc:
                return Err(
                    ErrorKind.IO,
                    "A mock fixture could not be read.",
                    {"file": candidate.name, "reason": type(exc).__name__},
                )
    return Err(ErrorKind.IO, "No mock fixture for this call.", {"stage": stage_id})


def get_model(conn: AiConnection, model_id: str) -> Result[ModelSummary]:
    """Look up one model; Err(not_found) if the key can't use it, Err(ai_auth) if the key is bad."""
    if conn.mock:
        match _fixture(conn, "models_get", model_id):
            case Err() as err:
                return err
            case Ok(value=data):
                return Ok(_summary(ModelInfo.model_validate(data)))
    try:
        return Ok(_summary(_client(conn).models.retrieve(model_id)))
    except anthropic.AnthropicError as exc:
        return _classify(exc)


def list_models(conn: AiConnection) -> Result[list[ModelSummary]]:
    """Every model available to the key, newest first (the SDK follows the pages)."""
    if conn.mock:
        match _fixture(conn, "models_list", "default"):
            case Err() as err:
                return err
            case Ok(value=data):
                items = data.get("data", []) if isinstance(data, dict) else []
                return Ok([_summary(ModelInfo.model_validate(item)) for item in items])
    try:
        return Ok([_summary(info) for info in _client(conn).models.list()])
    except anthropic.AnthropicError as exc:
        return _classify(exc)
