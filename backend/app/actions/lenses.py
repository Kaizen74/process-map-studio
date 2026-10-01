"""What the panel shows beyond the flow (PRD §3.12.2, §3.12.6, §5.7.7 4b-4c; C2b): each step's
know-how and stories, and the glossary, worked out from the interview's checked items (S1, C1)
and the steps S3c linked them to (by stable key, so they hold across refresh and reopen).

Quotes and anchors stay in the app; names are hidden (G10); roles, never people.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.actions import redaction
from app.db import session_scope
from app.domain.enums import ElementKind
from app.domain.graph import AshenItem, GlossaryEntry, KnowHow, StoryCard
from app.domain.models import ClaimRecord, NameReplacement
from app.domain.result import Err, ErrorKind, Ok, Result
from app.domain.sensemaking import SENSE_CLAIM_TYPES
from app.repositories import claims as claims_repo
from app.repositories import elements as map_repo
from app.repositories import sources as sources_repo
from app.repositories import versions as versions_repo
from app.services import parsing, sensemaking

Sessions = sessionmaker[Session]

DECIDING = {ElementKind.DECISION.value, ElementKind.APPROVAL.value}
VERSION_MISSING = "That version doesn't exist."


@dataclass(frozen=True, slots=True)
class Lenses:
    """The version's checked items, with where each first passage is and who said it."""

    items: list[ClaimRecord]
    anchors: dict[str, str]
    roles: dict[str, str]
    terms: list[NameReplacement]

    def hide(self, text: str) -> str:
        return redaction.hide(text, self.terms)


def load(session: Session, version_id: str, engagement_id: str) -> Lenses:
    items = [
        r
        for _, r in claims_repo.verified_rows(session, version_id)
        if r.claim_type in SENSE_CLAIM_TYPES
    ]
    first = [r.segment_ids[0] for r in items if r.segment_ids]
    rows = sources_repo.segment_rows(session, first)
    anchors = {
        sid: parsing.segment_anchor(fmt=fmt, seq=seg.seq, page=seg.page, section=seg.section,
                                    text=seg.text, start_ms=seg.start_ms)
        for sid, (seg, fmt) in rows.items()
    }  # fmt: skip
    terms = redaction.name_replacements(session, engagement_id)
    return Lenses(items, anchors, sources_repo.speaker_roles(session, first), terms)


def _where(lens: Lenses, record: ClaimRecord) -> tuple[str | None, str]:
    segment = record.segment_ids[0] if record.segment_ids else None
    return segment, lens.anchors.get(segment or "", "")


def _about(record: ClaimRecord, stable_key: str) -> bool:
    about = record.payload.get("about_steps")
    return isinstance(about, list) and stable_key in about


def know_how(lens: Lenses, stable_key: str, kind: str, work_type: str | None) -> KnowHow | None:
    """The ASHEN profile of a knowledge disclosure point (decisions, approvals and complex
    steps); None for other steps."""
    judgment = work_type in sensemaking.NEVER_AUTOMATED
    if kind not in DECIDING and not judgment:
        return None
    ashen: dict[str, list[AshenItem]] = {k: [] for k in sensemaking.ASHEN}
    received: list[str] = []
    attended: list[str] = []
    wanted: list[str] = []
    via: list[str] = []
    cadence: str | None = None
    for r in lens.items:
        if not _about(r, stable_key):
            continue
        segment, anchor = _where(lens, r)
        if r.claim_type == "know_how":
            category = str(r.payload.get("category", ""))
            if category in ashen:
                ashen[category].append(AshenItem(
                    text=lens.hide(str(r.payload.get("text", ""))), quote=lens.hide(r.quote),
                    role=lens.roles.get(segment or "", ""), source_id=r.source_id,
                    segment_id=segment, anchor=anchor,
                ))  # fmt: skip
        elif r.claim_type == "decision_info":
            for field, into in (("received", received), ("attended", attended),
                                ("wanted", wanted), ("communicated_via", via)):  # fmt: skip
                values = r.payload.get(field)
                if isinstance(values, list):
                    into += [lens.hide(str(v)) for v in values if str(v) not in into]
            stated = str(r.payload.get("cadence", "none"))
            cadence = stated if stated != "none" else cadence
    plain = {k: [i.model_dump() for i in v] for k, v in ashen.items()}
    risk = sensemaking.knowledge_risk(plain)
    return KnowHow(
        kdp_type="judgment" if judgment else "decision",
        ashen=ashen,
        knowledge_risk=risk,
        risk_reason=sensemaking.risk_reason(plain, risk),
        cadence=cadence,
        received=received,
        attended=attended,
        wanted=wanted,
        communicated_via=via,
    )


def stories(lens: Lenses, stable_key: str) -> list[StoryCard]:
    """The fragments told about the step, in the order told, kept when told once."""
    cards = []
    for r in lens.items:
        if r.claim_type != "story" or not _about(r, stable_key):
            continue
        segment, anchor = _where(lens, r)
        signifiers = r.payload.get("signifiers")
        cards.append(StoryCard(
            label=lens.hide(str(r.payload.get("text", ""))),
            fragment_type=str(r.payload.get("fragment_type", "other")),
            signifiers=[lens.hide(str(s)) for s in signifiers]
            if isinstance(signifiers, list) else [],
            frequency=lens.hide(str(r.payload.get("frequency", ""))),
            single_account=True,  # one source tells it; kept all the same (§3.12.9 rule 2)
            quote=lens.hide(r.quote), source_id=r.source_id, segment_id=segment, anchor=anchor,
        ))  # fmt: skip
    return cards


def get_glossary(sessions: Sessions, version_id: str) -> Result[list[GlossaryEntry]]:
    """The SME terms the interviews use, with the steps they belong to, in the order heard."""
    with session_scope(sessions) as session:
        version = versions_repo.get(session, version_id)
        if version is None:
            return Err(ErrorKind.NOT_FOUND, VERSION_MISSING)
        lens = load(session, version_id, version.engagement_id)
        labels = {e.stable_key: e.label for e in map_repo.elements(session, version_id)}
    entries: list[GlossaryEntry] = []
    seen: set[str] = set()
    for r in lens.items:
        term = str(r.payload.get("term", ""))
        if r.claim_type != "sme_term" or term.lower() in seen:
            continue
        seen.add(term.lower())
        segment, anchor = _where(lens, r)
        about = r.payload.get("about_steps")
        entries.append(GlossaryEntry(
            term=lens.hide(term), plain_meaning=lens.hide(str(r.payload.get("plain_meaning", ""))),
            steps=[lens.hide(labels[k]) for k in about if k in labels]
            if isinstance(about, list) else [],
            source_id=r.source_id, segment_id=segment, anchor=anchor,
        ))  # fmt: skip
    return Ok(entries)
