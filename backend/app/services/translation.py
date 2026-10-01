"""Deterministic verbatim-to-workflow translation rules (PRD §3.12.3, §3.12.10 step C,
§3.12.11). Pure functions on explicit inputs; no database access."""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.graph import AccountSummary
from app.domain.sensemaking import (
    SequenceBasis,
    TranslatedEdge,
    Translation,
    TranslationEdge,
    TranslationQuestion,
    TranslationStep,
    ViewMembership,
)


def account_summary(account_types: Iterable[str | None]) -> AccountSummary:
    """How many of a step's interview claims give the official, lived or unclear account
    (claims from other kinds of source carry no account and are not counted)."""
    types = [t for t in account_types if t is not None]
    return AccountSummary(
        official=types.count("official"), lived=types.count("lived"), unclear=types.count("unclear")
    )


def practice_described(summary: AccountSummary) -> bool | None:
    """§3.12.3: the lived account is the practice voice. True when a lived claim describes the
    step; False when only the official account does ("Practice not described"); None when the
    interview gives no account of it either way."""
    if summary.lived:
        return True
    if summary.official:
        return False
    return None


# --- Views, sequence basis and "not described" connectors (§3.12.10 rules 1-7, §3.12.11) -------

STRUCTURAL = {"start", "end"}
DECIDING = {"decision", "approval"}
# Exits and loops: the step's own claims state them (S4 draws only the paths the claims describe).
BRANCH = {"yes", "no", "approve", "reject", "rework", "exception"}
BACKWARD = {"reject", "rework"}  # never followed when looking for the next step in a view
DONE, DOCUMENTED = "done", "documented"
NOT_DESCRIBED = "Not described"

_MEMBERSHIP: dict[str, ViewMembership] = {
    "corroborated": "both",
    "contested": "both",
    "trace_contradicted": "both",  # the trace and the documents describe the same step
    "not_assessed": "both",  # steps Eric added; start and end
    "practiced_only": "done_only",
    "documented_only": "documented_only",
}


def element_view(step: TranslationStep) -> ViewMembership:
    """§3.12.11 view membership from the source state; R (recommended practice) is documented."""
    if step.kind in STRUCTURAL:
        return "both"
    if step.provenance == "R":
        return "documented_only"
    return _MEMBERSHIP.get(step.source_state, "both")


def _views(membership: str) -> set[str]:
    return {"both": {DONE, DOCUMENTED}, "done_only": {DONE}, "documented_only": {DOCUMENTED}}[
        membership
    ]


def _membership(views: set[str]) -> ViewMembership:
    if views == {DONE, DOCUMENTED}:
        return "both"
    return "documented_only" if views == {DOCUMENTED} else "done_only"


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def explicit_after(a: TranslationStep, b: TranslationStep) -> bool:
    """Rule 1: the lived account states that B follows A: a lived claim of B confirmed an
    explicit-order marker ("first", "then", "around T-90") and A was described earlier in the
    same interview. A step Eric added was put in the flow by him, so its order is stated."""
    if a.added_by_owner or b.added_by_owner:
        return True
    return any(
        p.explicit
        and p.lived
        and any(q.source_id == p.source_id and q.seq <= p.seq for q in a.interview)
        for p in b.interview
    )


def document_after(a: TranslationStep, b: TranslationStep) -> bool:
    """One document describes A before B (its step order)."""
    return any(
        pa.source_id == pb.source_id and pa.seq < pb.seq for pa in a.documents for pb in b.documents
    )


_ARTICLE = ("the ", "a ", "an ", "our ", "their ")


def information_name(text: str) -> str:
    """What passes across, as a matching key: lower case, single spaces, no leading article."""
    name = _norm(text)
    for article in _ARTICLE:
        if name.startswith(article):
            return name[len(article) :]
    return name


def shared_information(a: TranslationStep, b: TranslationStep) -> str | None:
    """Rule 8: what A passes on that B receives (by the same term), or None."""
    takes = {information_name(t): t for t in b.takes}
    for given in a.gives:
        if information_name(given) in takes:
            return information_name(given)
    return None


def sequence_basis(a: TranslationStep, b: TranslationStep, kind: str) -> SequenceBasis:
    """Codebook tier 2, strongest first: explicit order words or times → the documents' step
    order → dependency (what A hands over is what B takes in) → the order of mentioning."""
    if a.kind in STRUCTURAL or b.kind in STRUCTURAL or kind in BRANCH:
        return "explicit_order"  # the scope card's trigger and end point; stated exits and loops
    if explicit_after(a, b):
        return "explicit_order"
    if document_after(a, b):
        return "document_order"
    if a.handoff_out and _norm(a.handoff_out) == _norm(b.handoff_in):
        return "dependency"
    if shared_information(a, b):
        return "dependency"
    return "narration_order"


def translate(steps: list[TranslationStep], edges: list[TranslationEdge]) -> Translation:
    """Both views from one graph (§3.12.11): each step's and line's view membership, every line's
    sequence basis, and the lines each view needs where the other view's steps are left out:
    in As documented a plain line; in As done a line only when the lived account states the order
    (rule 1), otherwise a dashed "not described" connector, never an invented step (rule 7).
    Lines resting only on the order of mentioning, and "not described" connectors, each raise a
    validation question."""
    by_id = {s.id: s for s in steps}
    views = {s.id: element_view(s) for s in steps}
    out: list[TranslatedEdge] = []
    questions: list[TranslationQuestion] = []

    def in_view(step_id: str, view: str) -> bool:
        return view in _views(views[step_id])

    def chain(start: str, view: str, exclude: str) -> bool:
        """Is there a path start → … → exclude through steps of only the other view?"""
        seen, todo = set(), [start]
        while todo:
            node = todo.pop()
            for e in edges:
                if e.from_id != node or e.kind in BACKWARD or e.to_id in seen:
                    continue
                if e.to_id == exclude:
                    return True
                if views[e.to_id] == view:
                    seen.add(e.to_id)
                    todo.append(e.to_id)
        return False

    for e in edges:
        a, b = by_id[e.from_id], by_id[e.to_id]
        shared = _views(views[a.id]) & _views(views[b.id])
        if shared == {DONE, DOCUMENTED} and e.kind == "sequence":
            # A line both views share, unless one view goes another way between the same steps.
            if any(chain(x.to_id, "done_only", b.id) for x in edges if x.from_id == a.id
                   and x.to_id != b.id and views[x.to_id] == "done_only"):  # fmt: skip
                shared = {DOCUMENTED}
            elif any(chain(x.to_id, "documented_only", b.id) for x in edges if x.from_id == a.id
                     and x.to_id != b.id and views[x.to_id] == "documented_only"):  # fmt: skip
                shared = {DONE}
        if e.kind == "gap":
            shared = {DONE}  # a "not described" connector is drawn in As done only
        if not shared:
            shared = {DONE} if DONE in _views(views[a.id]) | _views(views[b.id]) else {DOCUMENTED}
        basis = sequence_basis(a, b, e.kind)
        out.append(TranslatedEdge(**e.model_dump(), sequence_basis=basis,
                                  view_membership=_membership(shared),
                                  information_payload=shared_information(a, b)))  # fmt: skip

    # Rule 8: information one step passes on that a step in another lane receives, with no line
    # between them yet, becomes a candidate line (`dependency`, with what passes across), even
    # when the two come from different interviews. Unmatched information becomes a question.
    joined = {(e.from_id, e.to_id) for e in out}
    for a in steps:
        for b in steps:
            payload = shared_information(a, b)
            if a.id == b.id or not payload or a.lane == b.lane or (a.id, b.id) in joined:
                continue
            both = _views(views[a.id]) & _views(views[b.id])
            if not both:
                continue
            joined.add((a.id, b.id))
            out.append(TranslatedEdge(
                from_id=a.id, to_id=b.id, kind="sequence", label="",
                sequence_basis="dependency", view_membership=_membership(both),
                information_payload=payload,
            ))  # fmt: skip
    for a in steps:
        for given in a.gives:
            if not any(information_name(given) in map(information_name, b.takes)
                       for b in steps if b.id != a.id):  # fmt: skip
                questions.append(TranslationQuestion(
                    element_id=a.id, reason="information",
                    question=f'"{a.label}" passes on {given}. Who uses it next?',
                ))  # fmt: skip
        for taken in a.takes:
            if not any(information_name(taken) in map(information_name, b.gives)
                       for b in steps if b.id != a.id):  # fmt: skip
                questions.append(TranslationQuestion(
                    element_id=a.id, reason="information",
                    question=f'"{a.label}" receives {taken}. Where does it come from?',
                ))  # fmt: skip

    # Each view's own next step where the other view's steps are left out.
    for view in (DONE, DOCUMENTED):
        present = {(e.from_id, e.to_id) for e in out if view in _views(e.view_membership)}
        for e in edges:
            if not in_view(e.from_id, view) or in_view(e.to_id, view) or e.kind in BACKWARD:
                continue
            a = by_id[e.from_id]
            skipped: list[str] = []
            reached: list[str] = []
            todo, seen = [e.to_id], {e.to_id}
            while todo:
                node = todo.pop(0)
                skipped.append(by_id[node].label)
                for x in edges:
                    if x.from_id != node or x.kind in BACKWARD or x.to_id in seen:
                        continue
                    seen.add(x.to_id)
                    if in_view(x.to_id, view):
                        reached.append(x.to_id)
                    else:
                        todo.append(x.to_id)
            for target in dict.fromkeys(reached):
                if (a.id, target) in present:
                    continue
                present.add((a.id, target))
                b = by_id[target]
                if view == DOCUMENTED:
                    out.append(TranslatedEdge(
                        from_id=a.id, to_id=b.id, kind=e.kind, label=e.label,
                        sequence_basis=sequence_basis(a, b, e.kind),
                        view_membership="documented_only",
                    ))  # fmt: skip
                elif explicit_after(a, b):
                    out.append(TranslatedEdge(
                        from_id=a.id, to_id=b.id, kind="sequence", label="",
                        sequence_basis="explicit_order", view_membership="done_only",
                    ))  # fmt: skip
                else:
                    out.append(TranslatedEdge(
                        from_id=a.id, to_id=b.id, kind="gap", label=NOT_DESCRIBED,
                        sequence_basis="document_order", view_membership="done_only",
                    ))  # fmt: skip
                    between = ", ".join(f'"{s}"' for s in dict.fromkeys(skipped))
                    questions.append(TranslationQuestion(
                        element_id=b.id, reason="not_described",
                        question=f'The documents describe {between} between "{a.label}" and '
                        f'"{b.label}", but the interview doesn\'t say what happens there. What '
                        "happens in practice?",
                    ))  # fmt: skip

    for e in out:
        if e.sequence_basis == "narration_order":
            a, b = by_id[e.from_id], by_id[e.to_id]
            questions.append(TranslationQuestion(
                element_id=b.id, reason="sequence",
                question=f'Does "{b.label}" come right after "{a.label}"? The sources mention it '
                "later but don't say it comes next.",
            ))  # fmt: skip
    return Translation(element_views=views, edges=out, questions=questions)
