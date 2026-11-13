"""Capability Compass hand-off preview and What we are testing (DECISIONS 95).

The preview applies nothing. Testing items hold the design principles from the hand-off and the
hypotheses Eric adds by hand; he sets each verdict and names the step, discrepancy or intent
codes it rests on. This app never mints a `P` or `H` ID: the reference is typed as written in
the app that owns it."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.actions import countries, redaction
from app.actions.engagements import ENGAGEMENT_MISSING, actor_name
from app.config import AppConfig
from app.db import session_scope
from app.domain.compass import (
    VERDICTS,
    HandoffPreview,
    TestingCreate,
    TestingItem,
    TestingPatch,
)
from app.domain.result import Err, ErrorKind, Ok, Result
from app.repositories import audit
from app.repositories import engagements as engagements_repo
from app.repositories import testing as repo
from app.services import compass, grounding

Sessions = sessionmaker[Session]

ITEM_MISSING = "That item doesn't exist."
BAD_REF = "Give the ID as written in the other app, for example H2 or P5."
BAD_TEXT = "Say what is being tested in one line of up to 300 characters."
BAD_LINE = "Keep it to one line of up to 300 characters."
BAD_VERDICT = "Choose open, supported or refuted."
BAD_CODES = "Use step, discrepancy or intent codes, for example S-04, X2 or I1."
NEEDS_CODES = "Add the step or discrepancy codes this verdict rests on."
FROM_HANDOFF = "This principle came from the hand-off, so its wording stays as received."
KEEP_PRINCIPLE = (
    "This principle came from the hand-off. Leave its verdict open if it wasn't tested."
)
HIDDEN_NAME = "{what} contains a name from your list of names to hide. Use the role instead."
_REF = re.compile(r"[PH]\d{1,3}", re.IGNORECASE)
_CODE = re.compile(r"(S-\d{1,4}|X\d{1,4}|I\d{1,4})", re.IGNORECASE)
MAX_CODES = 20


def _invalid(field: str, message: str) -> Err:
    return Err(ErrorKind.VALIDATION, message, {"field": field})


def preview(sessions: Sessions, body: Any) -> Result[HandoffPreview]:
    """What the file would create, and for each pilot the engagements mapping the same process
    in another country (DECISIONS 98). Applies nothing."""
    match compass.read_handoff(body):
        case Err() as err:
            return err
        case Ok(value=found):
            pass
    with session_scope(sessions) as session:
        return Ok(countries.with_same_process(session, found))


def _line(field: str, value: str, *, required: bool = False) -> Result[str]:
    text = value.strip()
    if len(text) > 300 or "\n" in text or (required and not text):
        return _invalid(field, BAD_TEXT if required else BAD_LINE)
    return Ok(text)


def _hidden(session: Session, engagement_id: str, texts: dict[str, str]) -> Err | None:
    terms = [t.term for t in redaction.name_replacements(session, engagement_id)]
    labels = {"text": "The item", "refuted_by": "What would refute it", "note": "The note"}
    for field, text in texts.items():
        if text and grounding.scan_redaction_terms(text, terms):
            return _invalid(field, HIDDEN_NAME.format(what=labels[field]))
    return None


def list_items(sessions: Sessions, engagement_id: str) -> Result[list[TestingItem]]:
    with session_scope(sessions) as session:
        if not engagements_repo.exists(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        return Ok(repo.list_for(session, engagement_id))


def add_item(
    config: AppConfig, sessions: Sessions, engagement_id: str, body: TestingCreate
) -> Result[TestingItem]:
    ref = body.ref.strip().upper()
    if not _REF.fullmatch(ref):
        return _invalid("ref", BAD_REF)
    match _line("text", body.text, required=True):
        case Err() as err:
            return err
        case Ok(value=text):
            pass
    match _line("refuted_by", body.refuted_by):
        case Err() as err:
            return err
        case Ok(value=refuted_by):
            pass
    actor = actor_name(config)
    with session_scope(sessions) as session:
        if not engagements_repo.exists(session, engagement_id):
            return Err(ErrorKind.NOT_FOUND, ENGAGEMENT_MISSING)
        if any(i.ref.upper() == ref for i in repo.list_for(session, engagement_id)):
            return Err(ErrorKind.CONFLICT, f"There is already an item {ref}.", {"field": "ref"})
        hidden = _hidden(session, engagement_id, {"text": text, "refuted_by": refuted_by})
        if hidden is not None:
            return hidden
        item = repo.add(session, engagement_id, ref=ref, text=text, refuted_by=refuted_by,
                        origin="owner")  # fmt: skip
        audit.record(session, actor=actor, action="Added testing item", target_type="testing_item",
                     target_id=item.id, engagement_id=engagement_id,
                     after=item.model_dump(exclude={"id"}))  # fmt: skip
        return Ok(item)


def _codes(values: list[str]) -> Result[list[str]]:
    cleaned: list[str] = []
    for raw in values:
        code = raw.strip().upper()
        if not code:
            continue
        if not _CODE.fullmatch(code):
            return _invalid("evidence_refs", BAD_CODES)
        if code not in cleaned:
            cleaned.append(code)
    if len(cleaned) > MAX_CODES:
        return _invalid("evidence_refs", f"At most {MAX_CODES} codes.")
    return Ok(cleaned)


def update_item(
    config: AppConfig, sessions: Sessions, item_id: str, body: TestingPatch
) -> Result[TestingItem]:
    sent = body.model_dump(exclude_unset=True)
    fields: dict[str, Any] = {}
    if "verdict" in sent:
        if sent["verdict"] not in VERDICTS:
            return _invalid("verdict", BAD_VERDICT)
        fields["verdict"] = sent["verdict"]
    if "evidence_refs" in sent:
        match _codes(sent["evidence_refs"] or []):
            case Err() as err:
                return err
            case Ok(value=codes):
                fields["evidence_refs"] = codes
    for name in ("note", "text", "refuted_by"):
        if name in sent:
            match _line(name, sent[name] or "", required=name == "text"):
                case Err() as err:
                    return err
                case Ok(value=line):
                    fields[name] = line
    actor = actor_name(config)
    with session_scope(sessions) as session:
        found = repo.get(session, item_id)
        if found is None:
            return Err(ErrorKind.NOT_FOUND, ITEM_MISSING)
        engagement_id, before = found
        if before.origin == "compass" and any(
            n in fields and fields[n] != getattr(before, n) for n in ("text", "refuted_by")
        ):
            return Err(ErrorKind.CONFLICT, FROM_HANDOFF)
        verdict = fields.get("verdict", before.verdict)
        codes = fields.get("evidence_refs", before.evidence_refs)
        if verdict != "open" and not codes:
            return _invalid("evidence_refs", NEEDS_CODES)
        texts: dict[str, str] = {
            n: str(fields[n]) for n in ("text", "refuted_by", "note") if n in fields
        }
        hidden = _hidden(session, engagement_id, texts)
        if hidden is not None:
            return hidden
        after = repo.update(session, item_id, fields)
        assert after is not None
        verdict_set = "verdict" in fields or "evidence_refs" in fields
        audit.record(session, actor=actor,
                     action="Set testing verdict" if verdict_set else "Edited testing item",
                     target_type="testing_item", target_id=item_id, engagement_id=engagement_id,
                     before=before.model_dump(exclude={"id"}),
                     after=after.model_dump(exclude={"id"}))  # fmt: skip
        return Ok(after)


def delete_item(config: AppConfig, sessions: Sessions, item_id: str) -> Result[None]:
    actor = actor_name(config)
    with session_scope(sessions) as session:
        found = repo.get(session, item_id)
        if found is None:
            return Err(ErrorKind.NOT_FOUND, ITEM_MISSING)
        engagement_id, before = found
        if before.origin == "compass":
            return Err(ErrorKind.CONFLICT, KEEP_PRINCIPLE)
        repo.delete(session, item_id)
        audit.record(session, actor=actor, action="Removed testing item",
                     target_type="testing_item", target_id=item_id, engagement_id=engagement_id,
                     before=before.model_dump(exclude={"id"}), after=None)  # fmt: skip
        return Ok(None)
