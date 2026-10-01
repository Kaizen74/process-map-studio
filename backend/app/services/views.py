"""The two views of one map (PRD §3.12.11): As done and As documented. Pure; no database.

A step or line belongs to a view by its view membership (B.35); a map drafted before v1.10 has
none, and everything on it is in both views. A line is in a view only if both its ends are.
"""

from __future__ import annotations

from app.domain.graph import Graph
from app.domain.layout import Layout
from app.domain.sensemaking import View

VIEWS: tuple[View, ...] = ("done", "documented")
NAMES: dict[View, str] = {"done": "As done", "documented": "As documented"}


def in_view(membership: str | None, view: View) -> bool:
    return membership in (None, "both") or membership == f"{view}_only"


def added_by_translation(provenance: str, membership: str | None) -> bool:
    """A line the translation added (provenance I): worked out again on every update."""
    return provenance == "I" and membership is not None


def added_for_one_view(provenance: str, membership: str | None) -> bool:
    """A line the translation added where one view leaves out the other view's steps (a stitched
    line, which both views draw, is not one of them)."""
    return provenance == "I" and membership in ("done_only", "documented_only")


def combined(graph: Graph) -> Graph:
    """The one map that shows both views' steps (until each view is drawn on its own): every
    line except those added for a single view, so nothing is counted twice."""
    edges = [e for e in graph.edges if not added_for_one_view(e.provenance, e.view_membership)]
    return graph.model_copy(update={"edges": edges})


def with_other_view(graph: Graph, view: View) -> Graph:
    """For "Show the other view": every step of both views, the combined map's lines and the
    lines this view adds (its "not described" connectors and stated-order lines)."""
    edges = [
        e
        for e in graph.edges
        if not added_for_one_view(e.provenance, e.view_membership)
        or in_view(e.view_membership, view)
    ]
    return graph.model_copy(update={"edges": edges})


def mark_ghosts(layout: Layout, graph: Graph, view: View) -> Layout:
    """The steps and lines only in the other view, marked to be drawn ghosted (no new marker)."""
    other_steps = {e.id for e in graph.elements if not in_view(e.view_membership, view)}
    other_lines = {
        e.id
        for e in graph.edges
        if not in_view(e.view_membership, view) or e.from_ in other_steps or e.to in other_steps
    }
    return layout.model_copy(update={
        "view": view,
        "nodes": [n.model_copy(update={"ghost": n.id in other_steps}) for n in layout.nodes],
        "edges": [e.model_copy(update={"ghost": e.id in other_lines}) for e in layout.edges],
    })  # fmt: skip


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
