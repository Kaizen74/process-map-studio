"""Two small fictional published maps of `VS-01` "Bid to contract renewal", in Arden and Belmar
(2026-11-13, Eric's brief §7; DECISIONS 98), built the way the A.12 fixtures are: the engagements
start from the Compass samples (`tests/fixtures/compass/countries/`), Belmar from Arden's scope
card, and each map is written as a published version with its own small sources.

What the two maps are built to show (Eric's acceptance test 4):
- "Approve the renewal price" is approved by the Regional finance controller in Arden and by the
  Country manager in Belmar: a `decision_right` difference (and a different lane).
- "Legal review of terms" is in Arden only; "Check the credit limit" is in Belmar only, in the lane
  of the Country manager, a role Arden doesn't have (`role_presence`).
- "Draft the renewal price" takes 120 min in Arden and 60 in Belmar (twice as long: a difference);
  "Receive the renewal request" takes 30 and 25 (under 1.5 times: none).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from fastapi.testclient import TestClient

from app.db import session_scope
from app.repositories.tables import (
    Edge,
    Element,
    EvidenceLink,
    MapVersion,
    Phase,
    Source,
    SourceSegment,
    VersionSource,
)
from tests.unit.test_countries_start import start_country

SHARED_LANES = [
    "Head of Pricing / Revenue Management",
    "Global Head, Commercial Excellence",
    "Bid & Solutions Architect",
    "VP Global Account Management",
]
RFC = "Regional finance controller"
CM = "Country manager"
PRICING, COMMERCIAL, ARCHITECT, ACCOUNT = SHARED_LANES

# (label, kind, lane, phase, work_min, decider)
ARDEN = [
    ("Receive the renewal request", "activity", ACCOUNT, "Prepare", 30, None),
    ("Build the bid solution", "activity", ARCHITECT, "Prepare", 240, None),
    ("Draft the renewal price", "activity", PRICING, "Price", 120, None),
    ("Approve the renewal price", "approval", RFC, "Price", 15, RFC),
    ("Legal review of terms", "activity", COMMERCIAL, "Close", 45, None),
    ("Send the renewal offer", "activity", ACCOUNT, "Close", 20, None),
]
BELMAR = [
    ("Receive the renewal request", "activity", ACCOUNT, "Prepare", 25, None),
    ("Build the bid solution", "activity", ARCHITECT, "Prepare", 240, None),
    ("Draft the renewal price", "activity", PRICING, "Price", 60, None),
    ("Approve the renewal price", "approval", CM, "Price", 15, CM),
    ("Check the credit limit", "activity", CM, "Close", 10, None),
    ("Send the renewal offer", "activity", ACCOUNT, "Close", 20, None),
]
PHASES = ["Prepare", "Price", "Close"]
# A person's name in each interview, on its list of names to hide: it must never leave the app.
PERSON = {"arden": "Rosa Delgado", "belmar": "Tomas Vrba"}


def key_of(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-")


@dataclass
class Countries:
    client: TestClient
    arden: str  # engagement IDs
    belmar: str
    arden_version: str
    belmar_version: str

    def get(self, path: str) -> Any:
        response = self.client.get(path)
        assert response.status_code == 200, response.text
        return response.json()


def _publish_map(
    client: TestClient,
    engagement_id: str,
    country: str,
    steps: list[tuple[str, str, str, str, int, str | None]],
) -> str:
    roles = {
        r["name"]: r["id"] for r in client.get(f"/api/engagements/{engagement_id}/roles").json()
    }
    with session_scope(client.app.state.sessions) as s:  # type: ignore[attr-defined]
        interview = Source(
            engagement_id=engagement_id,
            kind="interview_transcript",
            filename=f"interview_{country}_pricing.txt",
            stored_path="",
            format="txt",
            text_status="ready",
        )
        sop = Source(
            engagement_id=engagement_id,
            kind="sop",
            filename=f"sop_{country}_renewals.docx",
            stored_path="",
            format="docx",
            text_status="ready",
        )
        s.add_all([interview, sop])
        s.flush()
        version = MapVersion(
            engagement_id=engagement_id,
            label="v1.0",
            state="published",
            published_at="2026-11-13T09:00:00+00:00",
            published_by="Eric",
        )
        s.add(version)
        s.flush()
        s.add_all([VersionSource(version_id=version.id, source_id=x.id) for x in (interview, sop)])
        phases = {}
        for order, name in enumerate(PHASES, start=1):
            phase = Phase(version_id=version.id, name=name, sort_order=order)
            s.add(phase)
            s.flush()
            phases[name] = phase.id
        start = Element(
            version_id=version.id,
            stable_key="start",
            kind="start",
            label="Renewal due",
            provenance="O",
            review_status="confirmed",
        )
        end = Element(
            version_id=version.id,
            stable_key="end",
            kind="end",
            label="Renewal offer sent",
            provenance="O",
            review_status="confirmed",
        )
        s.add_all([start, end])
        s.flush()
        previous = start.id
        for seq, (label, kind, lane, phase, work, decider) in enumerate(steps, start=1):
            element = Element(
                version_id=version.id,
                stable_key=key_of(label),
                kind=kind,
                label=label,
                lane_role_id=roles[lane],
                phase_id=phases[phase],
                work_min=float(work),
                decision_mechanism="judgment" if decider else "none",
                decider_role_id=roles[decider] if decider else None,
                provenance="O",
                source_state="corroborated",
                review_status="confirmed",
                view_membership="both",
            )
            s.add(element)
            s.flush()
            said = f"{PERSON[country]} said the {label.casefold()} is done by the {lane}."
            segment = SourceSegment(
                source_id=interview.id, seq=seq, speaker_label=PERSON[country], text=said
            )
            written = SourceSegment(
                source_id=sop.id, seq=seq, section=f"{seq}", text=f"{label}: {lane}."
            )
            s.add_all([segment, written])
            s.flush()
            s.add_all(
                [
                    EvidenceLink(
                        element_id=element.id,
                        segment_id=segment.id,
                        source_kind="interview_transcript",
                        stance="supports",
                        verified=True,
                        quote=said,
                    ),
                    EvidenceLink(
                        element_id=element.id,
                        segment_id=written.id,
                        source_kind="sop",
                        stance="supports",
                        verified=True,
                        quote=f"{label}: {lane}.",
                    ),
                ]
            )
            s.add(
                Edge(
                    version_id=version.id,
                    from_element_id=previous,
                    to_element_id=element.id,
                    kind="approve" if kind == "approval" else "sequence",
                    label="Approve" if kind == "approval" else "",
                )
            )
            if kind == "approval":
                s.add(
                    Edge(
                        version_id=version.id,
                        from_element_id=element.id,
                        to_element_id=previous,
                        kind="rework",
                        label="Rework",
                    )
                )
            previous = element.id
        s.add(
            Edge(
                version_id=version.id,
                from_element_id=previous,
                to_element_id=end.id,
                kind="sequence",
            )
        )
        return version.id


def build(client: TestClient) -> Countries:
    """Arden and Belmar, each with its published map of VS-01; Belmar started from Arden."""
    arden = start_country(client, "arden", role_names=SHARED_LANES).json()
    assert (
        client.post(f"/api/engagements/{arden['id']}/roles", json={"name": RFC}).status_code == 201
    )
    belmar = start_country(
        client, "belmar", role_names=SHARED_LANES, reference_engagement_id=arden["id"]
    ).json()
    assert (
        client.post(f"/api/engagements/{belmar['id']}/roles", json={"name": CM}).status_code == 201
    )
    for country, made in (("arden", arden), ("belmar", belmar)):
        term = {"term": PERSON[country], "replacement": "the pricing lead"}
        added = client.post(f"/api/engagements/{made['id']}/redaction-terms", json=term)
        assert added.status_code == 201, added.text
    return Countries(
        client=client,
        arden=arden["id"],
        belmar=belmar["id"],
        arden_version=_publish_map(client, arden["id"], "arden", ARDEN),
        belmar_version=_publish_map(client, belmar["id"], "belmar", BELMAR),
    )


def republish(client: TestClient, engagement_id: str, version_id: str, label: str = "v2.0") -> str:
    """A newer published version with the same map (the old one superseded), as a republish leaves
    it: the steps keep their stable keys."""
    from app.repositories import versions

    with session_scope(client.app.state.sessions) as s:  # type: ignore[attr-defined]
        fresh = versions.create(s, engagement_id=engagement_id, label=label, state="draft")
        versions.copy_content(s, version_id, fresh.id)
        old = s.get(MapVersion, version_id)
        new = s.get(MapVersion, fresh.id)
        assert old is not None and new is not None
        old.state = "superseded"
        new.state, new.published_at, new.published_by = (
            "published",
            "2026-11-14T09:00:00+00:00",
            "Eric",
        )
        return fresh.id
