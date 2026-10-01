"""The two views of one map (PRD §3.12.11): As done and As documented. Pure; no database.

A step or line belongs to a view by its view membership (B.35); a map drafted before v1.10 has
none, and everything on it is in both views. A line is in a view only if both its ends are.
"""

from __future__ import annotations

from app.domain.graph import Graph
from app.domain.sensemaking import View

VIEWS: tuple[View, ...] = ("done", "documented")
NAMES: dict[View, str] = {"done": "As done", "documented": "As documented"}


def in_view(membership: str | None, view: View) -> bool:
    return membership in (None, "both") or membership == f"{view}_only"


def added_for_one_view(provenance: str, membership: str | None) -> bool:
    """A line the translation added where one view leaves out the other view's steps."""
    return provenance == "I" and membership is not None


def combined(graph: Graph) -> Graph:
    """The one map that shows both views' steps (until each view is drawn on its own): every
    line except those added for a single view, so nothing is counted twice."""
    edges = [e for e in graph.edges if not added_for_one_view(e.provenance, e.view_membership)]
    return graph.model_copy(update={"edges": edges})


def view_graph(graph: Graph, view: View) -> Graph:
    """The graph as one view draws it: its steps and the lines between them."""
    elements = [e for e in graph.elements if in_view(e.view_membership, view)]
    ids = {e.id for e in elements}
    edges = [
        e
        for e in graph.edges
        if in_view(e.view_membership, view) and e.from_ in ids and e.to in ids
    ]
    return graph.model_copy(update={"elements": elements, "edges": edges})
