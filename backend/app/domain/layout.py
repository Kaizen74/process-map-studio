"""Layout JSON (PRD §3.9): where the UI draws every lane, phase, node and edge.

The backend computes it (`services/layout.py`); the UI draws exactly these positions and never
computes layout itself (PRD §5.5, §5.8). All values are whole pixels so the same graph always gives
byte-identical JSON.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Align = Literal["left", "center", "right"]
Shape = Literal["rounded_rect", "pill", "diamond", "circle", "double_circle"]


class TextPos(BaseModel):
    """Where a text sits: `x` is its left edge, centre or right edge (per `align`); `y` is the top
    of the text for node labels and lens lines, and the vertical centre for edge-label chips."""

    x: int
    y: int
    align: Align


class LayoutCanvas(BaseModel):
    w: int
    h: int


class LayoutLane(BaseModel):
    role_id: str
    label: str
    step_count: int
    y: int
    h: int


class LayoutPhase(BaseModel):
    phase_id: str
    label: str
    time_window: str
    x: int
    w: int


class LayoutNode(BaseModel):
    """`x, y, w, h` is the node's box (for a diamond, the box around the rotated square)."""

    id: str
    shape: Shape
    x: int
    y: int
    w: int
    h: int
    label_lines: list[str]
    label_pos: TextPos
    lens_pos: TextPos


class LayoutEdge(BaseModel):
    """`points` are the corners of an orthogonal line, from the source to the target."""

    id: str
    kind: str
    is_back_edge: bool
    points: list[tuple[int, int]]
    label: str
    label_pos: TextPos | None


class Layout(BaseModel):
    canvas: LayoutCanvas
    lanes: list[LayoutLane]
    phases: list[LayoutPhase]
    nodes: list[LayoutNode]
    edges: list[LayoutEdge]
