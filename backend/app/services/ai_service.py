"""AI service (PRD §3.2, §3.7): the only module that imports the anthropic SDK.

Phase P0b provides the Models API calls used by Settings (list_models, get_model); phase P3 adds
`call_claude`, the one Messages API call every pipeline stage uses; phase P10 adds
`call_claude_with_web_search` for the research call of gap analysis B (only the brief is sent).

Verified against anthropic 1.8.0 (see DECISIONS.md): `Anthropic(api_key=, max_retries=,
timeout=, http_client=)`, `client.models.retrieve(model_id)` and `client.models.list()` return
`ModelInfo`, whose `capabilities` is a typed `ModelCapabilities` (pdf_input, structured_outputs,
effort.low/medium/high/xhigh/max, each with `.supported`). The SDK retries 408/409/429/5xx and
connection errors (max_retries), never 401/403/404.

Messages API (verified in anthropic 1.8.0 and the current docs, DECISIONS.md): `client.messages
.stream(model=, max_tokens=, system=, messages=, output_config=)` with `get_final_message()`;
`output_config` = `{"effort": low|medium|high|xhigh|max, "format": {"type": "json_schema",
"schema": {...}}}`; the answer's first text block is the JSON; `usage.input_tokens/output_tokens`;
`stop_reason` "refusal" and "max_tokens" are handled; `thinking` is omitted (current Opus models
then think adaptively; Claude Opus 5.5 refuses to disable it); no temperature or top_p.

Mock mode (MOCK_CLAUDE=1) returns fixtures from `<fixtures_dir>/<stage_id>/<key>.json`, falling
back to `default.json`; model fixtures are validated with the SDK's own `ModelInfo` type, stage
answers with the stage's own schema. For `call_claude` the key is the input hash (below).
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

import anthropic
import httpx2
from anthropic import Omit, omit
from anthropic.types import ContentBlockParam, MessageParam, ModelInfo, OutputConfigParam
from pydantic import BaseModel, ValidationError

from app.domain.models import (
    AiAnswer,
    AiCallRecord,
    ModelSummary,
    ResearchAnswer,
    ResearchCitation,
    ResearchPassage,
    SearchResult,
)
from app.domain.result import Err, ErrorKind, Ok, Result

EFFORT_ORDER = ("low", "medium", "high", "xhigh", "max")
MODELS_TIMEOUT_S = 20.0
# PRD §3.7: retry once on rate-limit or overload; the SDK never retries auth errors.
MAX_RETRIES = 1
# Stage calls stream (long outputs); ten minutes is the SDK default for a whole call.
MESSAGES_TIMEOUT_S = 600.0
DEFAULT_MAX_TOKENS = 32000
REPAIR_STAGE = "R_repair"


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


@contextmanager
def _client(conn: AiConnection, timeout: float = MODELS_TIMEOUT_S) -> Iterator[anthropic.Anthropic]:
    """A client for one call. Its connection is closed afterwards, unless the caller passed its
    own HTTP client (tests), which stays open for its owner."""
    client = anthropic.Anthropic(
        api_key=conn.api_key,
        max_retries=MAX_RETRIES,
        timeout=timeout,
        http_client=conn.http_client,
    )
    try:
        yield client
    finally:
        if conn.http_client is None:
            client.close()


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
        with _client(conn) as client:
            return Ok(_summary(client.models.retrieve(model_id)))
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
        with _client(conn) as client:
            return Ok([_summary(info) for info in client.models.list()])
    except anthropic.AnthropicError as exc:
        return _classify(exc)


# --- Messages API: call_claude (PRD §3.7) -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class StageCall:
    """One stage request. `blocks` are the user content blocks (source data); `system` is the
    stage prompt; `output_model` is the Pydantic model the answer must match."""

    stage_id: str
    prompt_version: str
    system: str
    blocks: Sequence[Mapping[str, object]]
    output_model: type[BaseModel]
    model: str
    repair_prompt: str
    effort: str | None = None
    structured_outputs: bool = True
    max_tokens: int = DEFAULT_MAX_TOKENS
    labels: Mapping[str, str] = field(default_factory=dict)


def input_hash(stage_id: str, blocks: Sequence[Mapping[str, object]]) -> str:
    """SHA-256 of the stage and its data blocks (not the prompt wording): the ai_calls input hash
    and the mock-fixture key, so fixtures survive prompt edits but not source changes."""
    payload = json.dumps({"stage": stage_id, "blocks": list(blocks)}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def strict_schema(model: type[BaseModel]) -> dict[str, object]:
    """The model's JSON schema in the form structured outputs accept: references inlined, every
    object closed (`additionalProperties: false`) with all its properties required."""
    raw = model.model_json_schema()
    definitions = raw.get("$defs", {})

    def walk(node: object) -> object:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                return walk(definitions[ref.removeprefix("#/$defs/")])
            # Drop Pydantic's metadata keys from each schema, but never from "properties", whose
            # keys are field names (a field may be called "title" or "default").
            out = {
                k: ({name: walk(sub) for name, sub in v.items()} if k == "properties" else walk(v))
                for k, v in node.items()
                if k not in ("$defs", "title", "default")
            }
            properties = out.get("properties")
            if out.get("type") == "object" and isinstance(properties, dict):
                out["additionalProperties"] = False
                out["required"] = list(properties)
            return out
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    result = walk(raw)
    assert isinstance(result, dict)
    return result


def _output_config(call: StageCall, schema: dict[str, object]) -> OutputConfigParam | Omit:
    config: OutputConfigParam = {}
    if call.effort in EFFORT_ORDER:
        config["effort"] = cast(Literal["low", "medium", "high", "xhigh", "max"], call.effort)
    if call.structured_outputs:
        config["format"] = {"type": "json_schema", "schema": schema}
    return config if config else omit


def _system(call: StageCall, prompt: str, schema: dict[str, object]) -> str:
    if call.structured_outputs:
        return prompt
    # Without structured outputs the schema goes into the instructions (PRD §3.7).
    return (
        f"{prompt}\n\nReturn only JSON that matches this JSON schema, with no other text:\n"
        f"{json.dumps(schema)}"
    )


@dataclass(slots=True)
class _Raw:
    text: str
    record: AiCallRecord
    stop_reason: str


def _send(
    conn: AiConnection,
    call: StageCall,
    *,
    stage_id: str,
    system: str,
    blocks: Sequence[Mapping[str, object]],
    fixture_key: str,
    schema: dict[str, object],
) -> Result[_Raw]:
    """One Messages API call (or its mock). Returns the answer text and the usage record."""
    record = AiCallRecord(
        stage_id=stage_id,
        prompt_version=call.prompt_version,
        model=call.model,
        status="ok",
        input_hash=fixture_key,
    )
    started = time.monotonic()
    if conn.mock:
        match _fixture(conn, stage_id, fixture_key):
            case Err() as err:
                return err
            case Ok(value=data):
                text = data if isinstance(data, str) else json.dumps(data)
                record.status = "mock"
                return Ok(_Raw(text=text, record=record, stop_reason="end_turn"))
    # The blocks are plain dicts in the Messages API shape (text and PDF document blocks).
    content = cast(list[ContentBlockParam], [dict(b) for b in blocks])
    messages: list[MessageParam] = [{"role": "user", "content": content}]
    try:
        with (
            _client(conn, MESSAGES_TIMEOUT_S) as client,
            client.messages.stream(
                model=call.model,
                max_tokens=call.max_tokens,
                system=_system(call, system, schema),
                messages=messages,
                output_config=_output_config(call, schema),
            ) as stream,
        ):
            message = stream.get_final_message()
    except anthropic.AnthropicError as exc:
        err = _classify(exc)
        record.status = "error"
        record.duration_ms = int((time.monotonic() - started) * 1000)
        return Err(err.kind, err.message, {**err.details, "calls": [record.model_dump()]})
    record.duration_ms = int((time.monotonic() - started) * 1000)
    record.input_tokens = message.usage.input_tokens
    record.output_tokens = message.usage.output_tokens
    text = next((b.text for b in message.content if b.type == "text"), "")
    return Ok(_Raw(text=text, record=record, stop_reason=message.stop_reason or ""))


def _validate(model: type[BaseModel], text: str) -> Result[dict[str, object]]:
    try:
        return Ok(model.model_validate(json.loads(text)).model_dump())
    except json.JSONDecodeError as exc:
        return Err(ErrorKind.AI_FORMAT, f"Not valid JSON: {exc.msg} (position {exc.pos}).")
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in e['loc']) or 'answer'}: {e['msg']}"
            for e in exc.errors()[:20]
        )
        return Err(ErrorKind.AI_FORMAT, f"Does not match the schema: {problems}")


def _stop_problem(raw: _Raw) -> str | None:
    if raw.stop_reason == "refusal":
        raw.record.status = "refused"
        return "refused"
    if raw.stop_reason == "max_tokens":
        raw.record.status = "truncated"
        return "truncated"
    return None


def _calls_of(err: Err) -> list[object]:
    calls = err.details.get("calls", [])
    return list(calls) if isinstance(calls, list) else []


def call_claude(conn: AiConnection, call: StageCall) -> Result[AiAnswer]:
    """Send one stage request and return its answer validated against `call.output_model`.

    A malformed answer gets exactly one `R_repair` call (the bad answer and the validation error,
    same schema); a second failure is `Err(ai_format)`. A refusal or a cut-off answer is
    `Err(ai_format)` straight away (a repair can't fix either). Every call made, successful or
    not, is listed in `AiAnswer.calls` or `Err.details["calls"]` for the ai_calls table.
    """
    schema = strict_schema(call.output_model)
    key = input_hash(call.stage_id, call.blocks)
    match _send(
        conn,
        call,
        stage_id=call.stage_id,
        system=call.system,
        blocks=call.blocks,
        fixture_key=key,
        schema=schema,
    ):
        case Err() as err:
            return err
        case Ok(value=first):
            pass
    calls = [first.record]
    problem = _stop_problem(first)
    if problem is not None:
        return Err(
            ErrorKind.AI_FORMAT,
            "Claude declined this part of the sources."
            if problem == "refused"
            else "Claude's answer was cut off before it was complete.",
            {"stop_reason": first.stop_reason, "calls": [c.model_dump() for c in calls]},
        )
    match _validate(call.output_model, first.text):
        case Ok(value=data):
            return Ok(AiAnswer(data=data, calls=calls))
        case Err(message=reason):
            first.record.status = "invalid"

    repair_blocks: list[Mapping[str, object]] = [
        {
            "type": "text",
            "text": (
                "<schema>\n" + json.dumps(schema) + "\n</schema>\n"
                "<validation_error>\n" + reason + "\n</validation_error>\n"
                "<previous_answer>\n" + first.text + "\n</previous_answer>"
            ),
        }
    ]
    match _send(
        conn,
        call,
        stage_id=REPAIR_STAGE,
        system=call.repair_prompt,
        blocks=repair_blocks,
        fixture_key=key,  # mock repair answers are filed under the original call's hash
        schema=schema,
    ):
        case Err() as err:
            return Err(
                err.kind,
                err.message,
                {**err.details, "calls": [*(c.model_dump() for c in calls), *_calls_of(err)]},
            )
        case Ok(value=second):
            pass
    calls.append(second.record)
    if _stop_problem(second) is None:
        match _validate(call.output_model, second.text):
            case Ok(value=data):
                second.record.status = "repaired"
                return Ok(AiAnswer(data=data, calls=calls))
            case Err():
                second.record.status = "invalid"
    return Err(
        ErrorKind.AI_FORMAT,
        "Claude's answer didn't match the expected format twice.",
        {"calls": [c.model_dump() for c in calls]},
    )


# --- Web research: call_claude_with_web_search (PRD §3.11.2 step 2; phase P10) ---------------

# Verified against the current web search tool documentation and anthropic 1.8.0 (DECISIONS.md):
# `web_search_20260318` is the newest version (dynamic filtering, plus `response_inclusion`, left
# at its default "full" so every result block comes back); `max_uses`; `allowed_domains` or
# `blocked_domains`, never both (the API answers 400); results are `web_search_tool_result`
# blocks whose `content` is a list of `web_search_result` (url, title, page_age,
# encrypted_content) or one `web_search_tool_result_error` object (`error_code`), inside a normal
# 200 answer; text blocks carry `web_search_result_location` citations (url, title, cited_text);
# `usage.server_tool_use.web_search_requests` counts the searches; a paused turn
# (`stop_reason: "pause_turn"`) is continued by sending the assistant content back unchanged; an
# organisation with web search switched off gets a 400 saying web search is not enabled.
WEB_SEARCH_TOOL = "web_search_20260318"
MAX_CONTINUATIONS = 5
RESEARCH_MAX_TOKENS = 16000
SEARCH_OFF = (
    "Web search isn't enabled for your Anthropic organisation. "
    "See the README, 'If something goes wrong'."
)
BOTH_DOMAIN_LISTS = "Use either allowed domains or blocked domains, not both."
SEARCH_OFF_CODE = "WEB_SEARCH_UNAVAILABLE"  # a `conflict` (409) with its own API code


@dataclass(frozen=True, slots=True)
class ResearchCall:
    """One web research request. `brief` is the only content sent (PRD §3.11.2)."""

    stage_id: str
    prompt_version: str
    system: str
    brief: str
    model: str
    max_uses: int
    allowed_domains: tuple[str, ...] = ()
    blocked_domains: tuple[str, ...] = ()
    effort: str | None = None
    max_tokens: int = RESEARCH_MAX_TOKENS


def _search_tool(call: ResearchCall) -> dict[str, object]:
    tool: dict[str, object] = {
        "type": WEB_SEARCH_TOOL,
        "name": "web_search",
        "max_uses": call.max_uses,
    }
    if call.allowed_domains:
        tool["allowed_domains"] = list(call.allowed_domains)
    if call.blocked_domains:
        tool["blocked_domains"] = list(call.blocked_domains)
    return tool


def research_key(call: ResearchCall) -> str:
    """The mock-fixture key: the stage and exactly what is sent (the brief and the tool limits)."""
    return input_hash(call.stage_id, [{"type": "text", "text": call.brief}, _search_tool(call)])


def _search_disabled(exc: anthropic.AnthropicError) -> bool:
    if not isinstance(exc, anthropic.BadRequestError):
        return False
    text = str(exc).lower()
    return "web search" in text and "not enabled" in text


def _read_answer(messages: Sequence[anthropic.types.Message]) -> tuple[
    list[ResearchPassage], list[SearchResult], list[str], int
]:  # fmt: skip
    """Everything the research turn produced, across its continuations."""
    passages: list[ResearchPassage] = []
    results: list[SearchResult] = []
    errors: list[str] = []
    searches = 0
    seen: set[str] = set()
    for message in messages:
        usage = message.usage.server_tool_use
        searches += usage.web_search_requests if usage else 0
        for block in message.content:
            if block.type == "text":
                cites = [
                    ResearchCitation(url=c.url, title=c.title or "", cited_text=c.cited_text)
                    for c in block.citations or []
                    if c.type == "web_search_result_location"
                ]
                passages.append(ResearchPassage(text=block.text, citations=cites))
            elif block.type == "web_search_tool_result":
                if isinstance(block.content, list):
                    for result in block.content:
                        if result.url not in seen:
                            seen.add(result.url)
                            results.append(
                                SearchResult(
                                    url=result.url,
                                    title=result.title,
                                    page_age=result.page_age or "",
                                )
                            )
                else:
                    errors.append(block.content.error_code)
    return passages, results, errors, searches


def _mock_research(
    conn: AiConnection, call: ResearchCall, key: str
) -> Result[list[anthropic.types.Message]]:
    """Mock answers: `{"responses": [<Messages API response>, …]}` (several for a paused turn),
    validated with the SDK's own Message type; `{"error": "web_search_disabled"}` stands for an
    organisation with web search switched off."""
    match _fixture(conn, call.stage_id, key):
        case Err() as err:
            return err
        case Ok(value=data):
            pass
    if isinstance(data, dict) and data.get("error") == "web_search_disabled":
        return Err(ErrorKind.CONFLICT, SEARCH_OFF, api_code=SEARCH_OFF_CODE)
    try:
        responses = data["responses"] if isinstance(data, dict) else None
        if not isinstance(responses, list):
            raise ValueError("responses")
        return Ok([anthropic.types.Message.model_validate(r) for r in responses])
    except (KeyError, ValueError, ValidationError) as exc:
        return Err(
            ErrorKind.IO, "A mock fixture could not be read.", {"reason": type(exc).__name__}
        )


def call_claude_with_web_search(conn: AiConnection, call: ResearchCall) -> Result[ResearchAnswer]:
    """Send the research brief with the web search tool and capture every search result and
    citation (PRD §3.11.2 step 2). A paused turn is continued (at most MAX_CONTINUATIONS times);
    tool errors such as `max_uses_exceeded` are kept as partial results, never raised; web search
    switched off for the organisation is `Err(web_search_unavailable)` with the README pointer.
    Only the brief is sent: no sources, map or names ever reach this call."""
    if call.allowed_domains and call.blocked_domains:
        return Err(ErrorKind.VALIDATION, BOTH_DOMAIN_LISTS, {"field": "domains"})
    key = research_key(call)
    calls: list[AiCallRecord] = []
    messages: list[anthropic.types.Message] = []
    if conn.mock:
        match _mock_research(conn, call, key):
            case Err() as err:
                return err
            case Ok(value=mocked):
                messages = mocked
        calls = [
            AiCallRecord(stage_id=call.stage_id, prompt_version=call.prompt_version,
                         model=call.model, status="mock", input_hash=key)
            for _ in messages
        ]  # fmt: skip
    else:
        effort = cast(Literal["low", "medium", "high", "xhigh", "max"], call.effort)
        config: OutputConfigParam | Omit = (
            {"effort": effort} if call.effort in EFFORT_ORDER else omit
        )
        tools = cast(list[anthropic.types.ToolUnionParam], [_search_tool(call)])
        sent: list[object] = []  # the assistant content so far, sent back unchanged when paused
        for _ in range(MAX_CONTINUATIONS + 1):
            history: list[MessageParam] = [{"role": "user", "content": call.brief}]
            if sent:
                history.append(
                    {"role": "assistant", "content": cast(list[ContentBlockParam], sent)}
                )
            record = AiCallRecord(stage_id=call.stage_id, prompt_version=call.prompt_version,
                                  model=call.model, status="ok", input_hash=key)  # fmt: skip
            started = time.monotonic()
            try:
                with (
                    _client(conn, MESSAGES_TIMEOUT_S) as client,
                    client.messages.stream(
                        model=call.model,
                        max_tokens=call.max_tokens,
                        system=call.system,
                        messages=history,
                        tools=tools,
                        output_config=config,
                    ) as stream,
                ):
                    message = stream.get_final_message()
            except anthropic.AnthropicError as exc:
                record.status = "error"
                record.duration_ms = int((time.monotonic() - started) * 1000)
                calls.append(record)
                if _search_disabled(exc):
                    logged = {"calls": [c.model_dump() for c in calls]}
                    return Err(ErrorKind.CONFLICT, SEARCH_OFF, logged, api_code=SEARCH_OFF_CODE)
                err = _classify(exc)
                return Err(err.kind, err.message,
                           {**err.details, "calls": [c.model_dump() for c in calls]})  # fmt: skip
            record.duration_ms = int((time.monotonic() - started) * 1000)
            record.input_tokens = message.usage.input_tokens
            record.output_tokens = message.usage.output_tokens
            calls.append(record)
            messages.append(message)
            if message.stop_reason != "pause_turn":
                break
            sent += [block.to_dict() for block in message.content]
    last = messages[-1].stop_reason if messages else ""
    if last == "refusal":
        calls[-1].status = "refused"
    passages, results, errors, searches = _read_answer(messages)
    return Ok(
        ResearchAnswer(
            passages=passages,
            results=results,
            tool_errors=errors,
            search_count=searches,
            stop_reason=last or "",
            calls=calls,
        )
    )
