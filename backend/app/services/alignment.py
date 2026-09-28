"""The alignment matrix (PRD §4 Views, §5.4 Matrix, §3.7 Stage 3): how each kind of source stands
on each step, read from the graph. Deterministic, no AI, no database.

Sources are classified, never reconciled (constraint 3): a column is `contradicts` when any source
of its kind contradicts the step, else `supports` when any supports it, else `silent` when the
draft was made from a source of that kind (silence is never contradiction, constraint 4), else
`not_applicable`. The columns group source kinds the way calibration does, so a row always agrees
with the step's source state.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.enums import ElementKind, Provenance, ReviewStatus, Stance
from app.domain.graph import AlignmentRow, Graph, GraphEvidence
from app.services.calibration import ARTEFACTS, DOCUMENTS, INTERVIEW, JOB_DESCRIPTIONS

NOT_APPLICABLE = "not_applicable"
STEPS = {ElementKind.ACTIVITY.value, ElementKind.DECISION.value, ElementKind.APPROVAL.value}
COLUMNS: dict[str, set[str]] = {
    "sop": DOCUMENTS,
    "interview": INTERVIEW,
    "jd": JOB_DESCRIPTIONS,
    "artefact": ARTEFACTS,
}


def cell(evidence: Iterable[GraphEvidence], kinds: set[str]) -> str:
    """One column of one step: the strongest stance of the sources of those kinds."""
    stances = {e.stance for e in evidence if e.source_kind in kinds}
    for stance in (Stance.CONTRADICTS.value, Stance.SUPPORTS.value, Stance.SILENT.value):
        if stance in stances:
            return stance
    return NOT_APPLICABLE


def alignment_matrix(graph: Graph) -> list[AlignmentRow]:
    """One row per step that is on the map (not start, end or rejected), in process order."""
    rows = []
    for element in graph.elements:
        if element.kind not in STEPS or element.review_status == ReviewStatus.REJECTED.value:
            continue
        # A recommended step comes from external practice: no source is asked about it.
        evidence = [] if element.provenance == Provenance.RECOMMENDED.value else element.evidence
        rows.append(
            AlignmentRow(
                element_id=element.id,
                label=element.label,
                kind=element.kind,
                state=element.source_state,
                divergence_types=list(element.divergence_types),
                **{column: cell(evidence, kinds) for column, kinds in COLUMNS.items()},
            )
        )
    return rows
