"""Reading a Capability Compass hand-off file (`compass-handoff` 1.x; DECISIONS 95).

Pure: a parsed JSON value in, a preview or a plain-language refusal out. Unknown fields are
ignored; every ID is passed on exactly as written."""

from __future__ import annotations

from typing import Any

from app.domain.compass import HANDOFF_FORMAT, HandoffPilot, HandoffPreview, HandoffPrinciple
from app.domain.result import Err, ErrorKind, Ok, Result

NOT_A_HANDOFF = (
    "This isn't a Capability Compass hand-off file (its format is “{found}”, not "
    "“compass-handoff”)."
)
WRONG_VERSION = "This hand-off is version {found}. This app reads version 1 files."
NO_KEY = (
    "This hand-off has no engagement key, so its IDs can't be kept. Export it again from "
    "Capability Compass."
)
NO_PILOT = "This hand-off names no pilot for Process Map Studio."
CLUSTER_NOWHERE = (
    "Pilot {pilot} points to cluster {cluster}, which isn't in this file. Export it again from "
    "Capability Compass."
)
PILOT_MISSING = "Pilot {pilot} isn't in this hand-off."


def _refuse(message: str, field: str = "handoff") -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _texts(value: Any) -> list[str]:
    return [t for t in (_text(v) for v in value) if t] if isinstance(value, list) else []


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def read_handoff(raw: Any) -> Result[HandoffPreview]:
    file = _dict(raw)
    found = _text(file.get("format")) if file else ""
    if found != HANDOFF_FORMAT:
        return _refuse(NOT_A_HANDOFF.format(found=found or "missing"))
    version = _text(file.get("format_version")) or str(file.get("format_version") or "")
    if version.split(".")[0] != "1":
        return _refuse(WRONG_VERSION.format(found=version or "missing"))
    engagement = _dict(file.get("engagement"))
    key = _text(engagement.get("key"))
    if not key:
        return _refuse(NO_KEY)
    clusters = {_text(c.get("ref")): c for c in _dicts(file.get("clusters"))}
    entries = _dicts(
        _dict(_dict(file.get("for_apps")).get("process_map_studio")).get("engagements")
    )
    pilots: list[HandoffPilot] = []
    for pilot in _dicts(file.get("pilots")):
        ref, cluster_ref = _text(pilot.get("ref")), _text(pilot.get("cluster_ref"))
        if not ref:
            continue
        cluster = clusters.get(cluster_ref)
        if cluster is None:
            return _refuse(CLUSTER_NOWHERE.format(pilot=ref, cluster=cluster_ref or "(none)"))
        name = _text(pilot.get("name"))
        entry = next(
            (e for e in entries if name and _text(e.get("process_name")) == name),
            next((e for e in entries if ref in _text(e.get("name")).split()), {}),
        )
        pilots.append(
            HandoffPilot(
                ref=ref,
                cluster_ref=cluster_ref,
                cluster_name=_text(cluster.get("name")),
                name=_text(entry.get("name")) or f"{key} {ref} {name}".strip(),
                process_name=_text(entry.get("process_name")) or name,
                process_kpi=_text(entry.get("process_kpi")) or _text(pilot.get("process_kpi")),
                industry=_text(entry.get("industry")) or _text(engagement.get("industry")),
                in_scope_roles=_texts(entry.get("in_scope_roles")),
                interview_prompts=_texts(entry.get("interview_prompts")),
                cell_refs=[
                    r for r in (_text(c.get("ref")) for c in _dicts(cluster.get("cells"))) if r
                ],
            )
        )
    if not pilots:
        return _refuse(NO_PILOT)
    readiness = _dict(file.get("readiness"))
    principles = [
        HandoffPrinciple(ref=_text(p.get("ref")), text=_text(p.get("principle")),
                         refuted_by=_text(p.get("refuted_by")))
        for p in _dicts(_dict(file.get("charter")).get("principles"))
        if _text(p.get("ref")) and _text(p.get("principle"))
    ]  # fmt: skip
    return Ok(
        HandoffPreview(
            key=key,
            organisation=_text(engagement.get("organisation")) or _text(engagement.get("name")),
            generated_at=_text(file.get("generated_at")),
            ready=readiness.get("ready") is not False,
            verdict=_text(readiness.get("verdict")),
            open=_texts(readiness.get("open")),
            pilots=pilots,
            principles=principles,
        )
    )


def choose_pilot(preview: HandoffPreview, pilot_ref: str) -> Result[HandoffPilot]:
    for pilot in preview.pilots:
        if pilot.ref == pilot_ref:
            return Ok(pilot)
    return _refuse(PILOT_MISSING.format(pilot=pilot_ref or "(none)"), "compass")
