"""The Belmar fixture for decision rights, SOP owners, the process owner and the data lens
(2026-11-25, Eric's brief §6; DECISIONS 110): a small fictional published map of `VS-01` "Bid to
contract renewal" in Belmar, started from the Compass sample `belmar_compass_handoff.json`, and
Arden's map of the same process as the reference it is compared with.

The map is written as a published version, as the other country fixtures are; Eric's records that
have screens (the SOP register, the process owner, the comparison's classing) go through the real
routes in the tests. Built to give the brief's figures exactly:

- 11 steps (2 decisions, 2 approvals), 6 handoffs between 5 roles, 1 rework loop, work 840 and
  waiting 7,200 minutes.
- The decision-rights table: S-03, S-05, S-07, S-08 and the activity S-02.
- Systems of record: 3 systems across the steps; how data moves: 2 handoffs by hand (re-keyed,
  email or spreadsheet), the other 4 by system interface.
- The SOP "Load planning and sign-off" cited by 9 steps; the manual "Overtime approval" by S-05.
- In the version's frozen Reality snapshot: X1 Different role (D12) at S-03, X2 Off-system (D6)
  at S-11 and X3 Different role (D12) at S-05, as in the Compass's own sample; no D11.
- Arden, the reference, runs S-04 in twice the time, has S-07 decided by the Regional finance
  controller in that lane, and has no S-11: 3 of Belmar's 11 steps differ once Eric classes them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi.testclient import TestClient

from app.actions import reality as reality_action
from app.db import session_scope
from app.domain.reality import CodeView
from app.repositories import reality_snapshots as snapshots_repo
from app.repositories import versions as versions_repo
from app.repositories.tables import (
    Edge,
    Element,
    EvidenceLink,
    MapVersion,
    Phase,
    Raci,
    RealitySnapshot,
    Source,
    SourceSegment,
    VersionSource,
)
from tests.countries_fixture import key_of
from tests.unit.test_countries_start import start_country

CL, SS, SM = "Commercial lead", "Shift supervisor", "Station manager"
CLC, CM = "Certified load controller", "Country manager"
RRO, RFC = "Regional roster owner", "Regional finance controller"
DCS, ROSTER, CONTRACTS = "Load control system", "Rostering system", "Contract system"
PEOPLE = [CL, SS, SM, CLC, CM, RRO, RFC]
SYSTEMS = [DCS, ROSTER, CONTRACTS]
PERSON = {"arden": "Rosa Delgado", "belmar": "Tomas Vrba"}
SOP_TITLE, MANUAL_TITLE = "Load planning and sign-off", "Overtime approval"


@dataclass(frozen=True)
class Step:
    code: str
    label: str
    kind: str
    lane: str
    work: int
    wait: int
    decider: str | None = None
    a: tuple[tuple[str, bool], ...] = ()  # (role, contested) holding A
    sop: bool = False  # cites the SOP
    manual: bool = False  # cites the manual
    system: str | None = None  # a system role, or "none"
    paper: str | None = None  # the decider named in the documents


BELMAR = [
    Step("S-01", "Receive the renewal request", "activity", CL, 30, 1440, sop=True, system="none"),
    Step("S-02", "Weigh the cargo", "activity", SS, 60, 0, sop=True, system=DCS),
    Step("S-03", "Sign off the load plan", "approval", SS, 30, 720, decider=SS,
         a=((CLC, False),), sop=True, system=DCS, paper=CLC),
    Step("S-04", "Plan the overtime", "activity", SM, 60, 0, sop=True, system=ROSTER),
    Step("S-05", "Approve overtime", "approval", SM, 15, 1440, decider=SM, a=((RRO, True),),
         sop=True, manual=True, system=ROSTER, paper=RRO),
    Step("S-06", "Check the load sheet", "activity", CLC, 45, 0, sop=True, system=DCS),
    Step("S-07", "Approve the renewal price", "decision", CM, 60, 2880, decider=CM,
         a=((CM, False), (RFC, False)), sop=True),
    Step("S-08", "Release the bid", "decision", CL, 30, 0),
    Step("S-09", "Prepare the contract", "activity", CL, 240, 0, sop=True, system=CONTRACTS),
    Step("S-10", "Sign the contract", "activity", CM, 30, 720, system=CONTRACTS),
    Step("S-11", "File the contract", "activity", CM, 240, 0, sop=True, system="none"),
]  # fmt: skip
# Arden: S-04 takes twice as long, S-07 is decided by the finance controller in that lane, and
# there is no S-11.
ARDEN = [
    s if s.code not in ("S-04", "S-07") else (
        Step(s.code, s.label, s.kind, s.lane, 120, s.wait, sop=True) if s.code == "S-04"
        else Step(s.code, s.label, s.kind, RFC, 60, 2880, decider=RFC, a=((RFC, False),), sop=True)
    )
    for s in BELMAR if s.code != "S-11"
]  # fmt: skip
# (from, to, kind, label, data_move): the six handoffs are the lines between lanes.
LINES = [
    ("start", "S-01", "sequence", "", None),
    ("S-01", "S-02", "sequence", "", "re_keyed"),
    ("S-02", "S-03", "sequence", "", None),
    ("S-03", "S-04", "approve", "Approve", "system_interface"),
    ("S-03", "S-02", "rework", "Weigh again", None),  # the one rework loop (same lane)
    ("S-04", "S-05", "sequence", "", None),
    ("S-05", "S-06", "approve", "Approve", "system_interface"),
    ("S-05", "end", "reject", "Refused", None),
    ("S-06", "S-07", "sequence", "", "system_interface"),
    ("S-07", "S-08", "yes", "Price approved", "email_spreadsheet"),
    ("S-07", "end", "no", "Not approved", None),
    ("S-08", "S-09", "yes", "Released", None),
    ("S-08", "end", "no", "Held", None),
    ("S-09", "S-10", "sequence", "", "system_interface"),
    ("S-10", "S-11", "sequence", "", None),
    ("S-11", "end", "sequence", "", None),
]
# The X codes in Belmar's frozen snapshot: (code, types, step, title).
CODES = [
    ("X1", ["D12"], "S-03", "The shift supervisor signs off the load plan"),
    ("X2", ["D6"], "S-11", "Contracts are filed outside any system"),
    ("X3", ["D12"], "S-05", "Overtime is approved without the regional roster owner"),
]


@dataclass
class Built:
    client: TestClient
    engagement_id: str
    version_id: str
    roles: dict[str, str]
    steps: dict[str, str]  # S-nn -> element ID
    sources: dict[str, str] = field(default_factory=dict)  # "sop", "manual", "interview"
    passages: dict[str, str] = field(default_factory=dict)  # S-nn -> the SOP or manual passage

    def get(self, path: str) -> Any:
        response = self.client.get(path)
        assert response.status_code == 200, response.text
        return response.json()


@dataclass
class Fixture:
    client: TestClient
    arden: Built
    belmar: Built


def _roles(client: TestClient, engagement_id: str) -> dict[str, str]:
    have = {
        r["name"]: r["id"] for r in client.get(f"/api/engagements/{engagement_id}/roles").json()
    }
    for name in PEOPLE + SYSTEMS:
        if name not in have:
            made = client.post(f"/api/engagements/{engagement_id}/roles",
                               json={"name": name, "is_system": name in SYSTEMS})  # fmt: skip
            assert made.status_code == 201, made.text
            have[name] = made.json()["id"]
    return have


def _publish(client: TestClient, engagement_id: str, country: str, steps: list[Step],
             codes: bool) -> Built:  # fmt: skip
    roles = _roles(client, engagement_id)
    built = Built(client, engagement_id, "", roles, {})
    with session_scope(client.app.state.sessions) as s:  # type: ignore[attr-defined]
        sop = Source(engagement_id=engagement_id, kind="sop", filename="sop_load_planning.docx",
                     stored_path="", format="docx", text_status="ready")  # fmt: skip
        manual = Source(engagement_id=engagement_id, kind="manual", filename="overtime.pdf",
                        stored_path="", format="pdf", text_status="ready")  # fmt: skip
        interview = Source(engagement_id=engagement_id, kind="interview_transcript",
                           filename=f"interview_{country}.txt", stored_path="", format="txt",
                           text_status="ready")  # fmt: skip
        s.add_all([sop, manual, interview])
        s.flush()
        built.sources = {"sop": sop.id, "manual": manual.id, "interview": interview.id}
        version = MapVersion(
            engagement_id=engagement_id,
            label="v1.0",
            state="published",
            published_at="2026-11-25T09:00:00+00:00",
            published_by="Eric",
        )
        s.add(version)
        s.flush()
        built.version_id = version.id
        s.add_all([VersionSource(version_id=version.id, source_id=x.id)
                   for x in (sop, manual, interview)])  # fmt: skip
        phase = Phase(version_id=version.id, name="Renew", sort_order=1)
        s.add(phase)
        s.flush()
        ids: dict[str, str] = {}
        stamp = iter(range(10, 99))

        def created() -> str:
            return f"2026-11-25T08:00:{next(stamp):02d}+00:00"

        for key, kind, label in (
            ("start", "start", "Renewal due"),
            ("end", "end", "Contract filed"),
        ):
            ends = Element(
                version_id=version.id,
                stable_key=key,
                kind=kind,
                label=label,
                provenance="O",
                review_status="confirmed",
                created_at=created(),
            )
            s.add(ends)
            s.flush()
            ids[key] = ends.id
        for seq, step in enumerate(steps, start=1):
            system = {} if step.system is None else (
                {"system_status": "none"} if step.system == "none"
                else {"system_status": "system", "system_role_id": roles[step.system]}
            )  # fmt: skip
            element = Element(
                version_id=version.id, stable_key=key_of(step.label), kind=step.kind,
                label=step.label, lane_role_id=roles[step.lane], phase_id=phase.id,
                work_min=float(step.work), wait_min=float(step.wait),
                decision_mechanism="judgment" if step.kind != "activity" else "none",
                decider_role_id=roles[step.decider] if step.decider else None,
                provenance="O", source_state="corroborated", review_status="confirmed",
                view_membership="both", created_at=created(), **system,
            )  # fmt: skip
            s.add(element)
            s.flush()
            ids[step.code] = element.id
            s.add(Raci(element_id=element.id, role_id=roles[step.lane], letter="R"))
            for role, contested in step.a:
                s.add(Raci(element_id=element.id, role_id=roles[role], letter="A",
                           contested=contested))  # fmt: skip
            said = f"{PERSON[country]} said: {step.label.casefold()} is done by the {step.lane}."
            spoken = SourceSegment(source_id=interview.id, seq=seq, speaker_label=PERSON[country],
                                   text=said)  # fmt: skip
            s.add(spoken)
            s.flush()
            links = [(spoken, "interview_transcript", said)]
            for wanted, source, kind in ((step.sop, sop, "sop"), (step.manual, manual, "manual")):
                if wanted:
                    text = f"{step.label}: {step.paper or step.lane}."
                    written = SourceSegment(source_id=source.id, seq=seq, section=str(seq),
                                            text=text)  # fmt: skip
                    s.add(written)
                    s.flush()
                    links.append((written, kind, text))
                    built.passages.setdefault(step.code, written.id)
            for segment, kind, quote in links:
                s.add(EvidenceLink(element_id=element.id, segment_id=segment.id, source_kind=kind,
                                   stance="supports", verified=True, quote=quote))  # fmt: skip
            if step.paper:
                element.paper_decider_status = "named"
                element.paper_decider_role_id = roles[step.paper]
                element.paper_decider_segment_id = built.passages.get(step.code)
        for start, end, kind, label, move in LINES:
            if start in ids and end in ids:
                s.add(
                    Edge(
                        version_id=version.id,
                        from_element_id=ids[start],
                        to_element_id=ids[end],
                        kind=kind,
                        label=label,
                        data_move=move,
                    )
                )
        s.flush()
        if not any(st.code == "S-11" for st in steps):  # Arden: S-10 goes to the end
            s.add(Edge(version_id=version.id, from_element_id=ids["S-10"], to_element_id=ids["end"],
                       kind="sequence", label=""))  # fmt: skip
        built.steps = {k: v for k, v in ids.items() if k.startswith("S-")}
    if codes:
        _codes(built)
    return built


def _codes(b: Built) -> None:
    """Belmar's frozen snapshot, worked out by the Reality rules, with the brief's X codes in it
    (the discrepancy engine's own tests cover how codes are found)."""
    with session_scope(b.client.app.state.sessions) as s:  # type: ignore[attr-defined]
        version = versions_repo.get(s, b.version_id)
        assert version is not None
        snapshot = reality_action.snapshot_of(s, version)
        keys = {e.id: e.stable_key for e in s.query(Element).filter_by(version_id=b.version_id)}
        snapshot.codes = [
            CodeView.model_validate({
                "code": code, "item_id": code.lower(), "title": title, "types": types,
                "impact_class": "control", "impact_word": "Control", "glyph": "triangle",
                "impact_note": "", "location": {"kind": "step", "keys": [keys[b.steps[at]]]},
                "element_ids": [b.steps[at]], "column_id": None,
                "delta": {"id": f"{code}-delta", "value": None, "unit": "", "text": "",
                          "label": "stated"},
                "minutes": None, "hours": None, "verdict": None,
                "evidence": {"documents": 1, "interviews": 1, "system_cases": None,
                             "chips": {"documents": True, "interviews": True, "system": False},
                             "sentence": ""},
                "control": True, "shown": True, "rank": n,
            })
            for n, (code, types, at, title) in enumerate(CODES, start=1)
        ]  # fmt: skip
        stored = snapshots_repo.get(s, b.version_id)
        assert stored is not None and stored.frozen
        row = s.query(RealitySnapshot).filter_by(version_id=b.version_id).one()
        row.payload = snapshot.model_dump(mode="json")


def build(client: TestClient) -> Fixture:
    """Arden (the reference) and Belmar, each with its published map of VS-01, with the Reality
    views on and the names of the two interviewees on their lists of names to hide."""
    assert (
        client.put("/api/settings/modules", json={"reality_views_enabled": True}).status_code == 200
    )
    arden = start_country(client, "arden").json()
    belmar = start_country(client, "belmar", reference_engagement_id=arden["id"]).json()
    for country, made in (("arden", arden), ("belmar", belmar)):
        term = {"term": PERSON[country], "replacement": "the interviewee"}
        assert (
            client.post(f"/api/engagements/{made['id']}/redaction-terms", json=term).status_code
            == 201
        )
    return Fixture(
        client=client,
        arden=_publish(client, arden["id"], "arden", ARDEN, codes=False),
        belmar=_publish(client, belmar["id"], "belmar", BELMAR, codes=True),
    )
