"""Geometry of the four P13c Reality views (PRD §5.12.3, §5.12.6; P13c): Redline (RV4), Where
the time goes (RV5), Belief vs evidence (RV6) and Typical case (RV7), as plain shapes on the
1600-wide reference frame. The UI only draws them (constraint 20). Pure and deterministic; part
of the one versioned layout rule set (`reality_layout.LAYOUT_VERSION`).

Conventions every shape follows (the UI relies on them):
- rect: x, y, width, height. circle: centre x, y and r. line: x, y to x2, y2.
- path: the SVG path in `path`, with its bounding box in x, y, width, height.
- text: the box's top-left x, y with its width and height; line i sits at y + 12 + 16 i.

RQ7 (no collisions): text boxes never overlap one another or any path's bounding box. Labels
that compete for room are given levels (`_Levels`): a label moves to the next level up or down
until its box clears every other label on that level.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.domain.reality import (
    BeliefModel,
    CaseModel,
    Figure,
    Markup,
    RedlineModel,
    RedlineStep,
    Shape,
    ShapeGeometry,
    TimeModel,
)
from app.services.reality_layout import CHAR_PX, LINE_PX, WIDTH, wrap

GAP = 8.0  # the least room between two label boxes on one level
TEXT_PAD = 4.0


def _text_width(lines: Sequence[str]) -> float:
    return round(max((len(t) for t in lines), default=0) * CHAR_PX + 2 * TEXT_PAD, 1)


def text(role: str, x: float, y: float, lines: Sequence[str], *, code: str | None = None,
         key: str | None = None, impact_class: str | None = None) -> Shape:  # fmt: skip
    return Shape(kind="text", role=role, x=round(x, 1), y=round(y, 1),
                 width=_text_width(lines), height=round(len(lines) * LINE_PX, 1),
                 lines=list(lines), code=code, key=key, impact_class=impact_class)  # fmt: skip


def rect(role: str, x: float, y: float, width: float, height: float, *, style: str = "solid",
         code: str | None = None, key: str | None = None,
         impact_class: str | None = None) -> Shape:  # fmt: skip
    return Shape(kind="rect", role=role, x=round(x, 1), y=round(y, 1), width=round(width, 1),
                 height=round(height, 1), style=style, code=code, key=key,
                 impact_class=impact_class)  # fmt: skip


def line(role: str, x: float, y: float, x2: float, y2: float, *, style: str = "solid",
         code: str | None = None, key: str | None = None) -> Shape:  # fmt: skip
    return Shape(kind="line", role=role, x=round(x, 1), y=round(y, 1), x2=round(x2, 1),
                 y2=round(y2, 1), style=style, code=code, key=key)  # fmt: skip


def circle(role: str, cx: float, cy: float, r: float, *, key: str | None = None,
           code: str | None = None, impact_class: str | None = None) -> Shape:  # fmt: skip
    return Shape(kind="circle", role=role, x=round(cx, 1), y=round(cy, 1), r=r, key=key,
                 code=code, impact_class=impact_class)  # fmt: skip


def arc(role: str, x1: float, x2: float, base: float, peak: float, *, style: str,
        code: str | None = None, impact_class: str | None = None) -> Shape:  # fmt: skip
    """A curve from (x1, base) to (x2, base) bowing to `peak` (above or below the base)."""
    path = (f"M{x1:.1f} {base:.1f} C {x1:.1f} {peak:.1f}, {x2:.1f} {peak:.1f}, "
            f"{x2:.1f} {base:.1f}")  # fmt: skip
    top, bottom = min(base, peak), max(base, peak)
    return Shape(kind="path", role=role, x=round(min(x1, x2), 1), y=round(top, 1),
                 width=round(abs(x2 - x1), 1), height=round(bottom - top, 1), path=path,
                 style=style, code=code, impact_class=impact_class)  # fmt: skip


def overlaps(a: Shape, b: Shape) -> bool:
    """Whether two boxes (text or a path's bounding box) share any area."""
    return (a.x < b.x + b.width and b.x < a.x + a.width and a.y < b.y + b.height
            and b.y < a.y + a.height)  # fmt: skip


def collisions(shapes: Sequence[Shape]) -> list[tuple[Shape, Shape]]:
    """RQ7: every pair of text boxes that overlap, and every text box crossing a path's box."""
    texts = [s for s in shapes if s.kind == "text"]
    paths = [s for s in shapes if s.kind == "path"]
    out = [(a, b) for i, a in enumerate(texts) for b in texts[i + 1 :] if overlaps(a, b)]
    return out + [(t, p) for t in texts for p in paths if overlaps(t, p)]


class _Levels:
    """Horizontal intervals per level: a box takes the first level where it clears the rest."""

    def __init__(self) -> None:
        self.rows: list[list[tuple[float, float]]] = []

    def take(self, x1: float, x2: float) -> int:
        for i, row in enumerate(self.rows):
            if all(x2 + GAP <= a or x1 >= b + GAP for a, b in row):
                row.append((x1, x2))
                return i
        self.rows.append([(x1, x2)])
        return len(self.rows) - 1

    @property
    def count(self) -> int:
        return len(self.rows)


def _clamp(x: float, width: float, left: float, right: float) -> float:
    return max(left, min(x, right - width))


def _empty(scale_note: str) -> ShapeGeometry:
    return ShapeGeometry(width=WIDTH, height=120.0, shapes=[], scale_note=scale_note)


# --- RV4 Redline --------------------------------------------------------------------------------

R_LEFT = 24.0
SIDE_W = 300.0
ROW_RIGHT = WIDTH - SIDE_W - 24.0
MAX_SLOT = 170.0
STEP_GAP = 40.0
STEP_H = 72.0
ARC_H = 44.0
PILL_H = 28.0
TITLE_H = 32.0
R_LEVEL = 4 * LINE_PX + 10  # a markup label: up to two lines of title, two of its share
LABEL_W = 220.0
PAGE_GAP = 36.0
ABOVE = {"added", "skipped", "bypass", "reorder", "owner", "longer"}
BADGES = {"off_system", "no_record", "owner", "longer"}
GLYPH_STEP = 24.0  # glyphs on one side of the row sit at least this far apart
REDLINE_NOTE = "The documented steps once, in the manual's order; markups show practice"
MARKUP_WORDS = {  # the legend of markup types on the canvas
    "added": "Added in practice", "skipped": "Skipped in practice", "reorder": "Other order",
    "loop": "Loops back", "bypass": "Goes round", "off_system": "Off-system",
    "longer": "Takes longer", "wait": "Waits", "no_record": "No record",
    "owner": "Done by another role",
}  # fmt: skip


def _spot(taken: list[float], want: float) -> float:
    """The first free spot from `want` along the row: glyphs never sit on top of each other."""
    x = want
    while any(abs(x - t) < GLYPH_STEP for t in taken):
        x += GLYPH_STEP
    taken.append(x)
    return x


def redline(model: RedlineModel) -> ShapeGeometry:
    if not model.pages:
        return _empty(REDLINE_NOTE)
    steps = {s.key: s for s in model.steps}
    pills = {f.id.removeprefix("rv4.pill."): f for f in model.pills}
    shapes: list[Shape] = []
    y = 16.0
    for page in model.pages:
        page_shapes, y = _redline_page(page.name, page.step_keys, steps, model, pills, y)
        shapes += page_shapes
        y += PAGE_GAP
    # The markups not drawn, listed at the side (§5.12.3), and the legend under the steps.
    side_x = ROW_RIGHT + 24
    if model.listed:
        shapes.append(text("side-title", side_x, 16.0, ["Not drawn on the view"]))
        sy = 16.0 + LINE_PX + 12
        labels = {m.code: m.label for m in model.markups}
        for code in model.listed:
            lines = wrap(f"{code} {labels.get(code, '')}", SIDE_W - 40, 2)
            shapes.append(text("side-item", side_x, sy, lines, code=code))
            sy += len(lines) * LINE_PX + 8
        y = max(y, sy + PAGE_GAP)
    kinds = list(dict.fromkeys(m.kind for m in model.markups if m.drawn))
    x = R_LEFT
    for kind in kinds:
        word = MARKUP_WORDS.get(kind, kind)
        w = _text_width([word]) + 24
        if x + w > ROW_RIGHT:
            x, y = R_LEFT, y + LINE_PX + 12
        shapes.append(rect(f"legend-{kind.replace('_', '-')}", x, y + 2, 14, 12, key=kind))
        shapes.append(text("legend", x + 18, y, [word], key=kind))
        x += w + 16
    height = y + (LINE_PX + 24 if kinds else 0)
    return ShapeGeometry(width=WIDTH, height=round(height, 1), shapes=shapes,
                         scale_note=REDLINE_NOTE)  # fmt: skip


def _redline_page(name: str, keys: Sequence[str], steps: Mapping[str, RedlineStep],
                  model: RedlineModel, pills: Mapping[str, Figure],
                  y: float) -> tuple[list[Shape], float]:  # fmt: skip
    n = len(keys)
    slot = min(MAX_SLOT, (ROW_RIGHT - R_LEFT) / max(1, n))
    box_w = slot - STEP_GAP
    index = {k: i for i, k in enumerate(keys)}

    def bx(i: int) -> float:
        return R_LEFT + i * slot + STEP_GAP / 2

    def cx(i: int) -> float:
        return bx(i) + box_w / 2

    drawn = [m for m in model.markups if m.drawn and any(k in index for k in m.keys)]
    # Each markup's anchor x (its glyph or arc's middle) and side, then its label's level. Glyphs
    # on one side of the row never share a spot: a taken spot moves the next one along (RQ7).
    above, below = _Levels(), _Levels()
    spots: dict[bool, list[float]] = {True: [], False: []}
    placed: list[tuple[Markup, float, float, bool, int, list[str], float]] = []
    for m in drawn:
        at = [index[k] for k in m.keys if k in index]
        first, last = min(at), max(at)
        up = m.kind in ABOVE
        if m.kind == "wait":  # on the connector into the step (or out of the first one)
            ax = bx(first) - STEP_GAP / 2 if first > 0 else bx(first) + box_w + STEP_GAP / 2
        elif m.kind == "added":  # between the step it follows and the next
            ax = _spot(spots[up], bx(last) + box_w + STEP_GAP / 2)
        elif m.kind in BADGES:
            ax = _spot(spots[up], cx(first))
        else:
            ax = (cx(first) + cx(last)) / 2
        inner = LABEL_W - 2 * TEXT_PAD
        lines = [*wrap(f"{m.code} {m.label}", inner, 2),
                 *wrap(f"{m.share.text} ({m.share.label})", inner, 2)]  # fmt: skip
        w = _text_width(lines)
        lx = _clamp(ax - w / 2, w, R_LEFT, ROW_RIGHT)
        level = (above if up else below).take(lx, lx + w)
        placed.append((m, ax, lx, up, level, lines, w))
    shapes = [text("page-title", R_LEFT, y, [name])]
    arc_top = y + TITLE_H + above.count * R_LEVEL
    row_top = arc_top + ARC_H
    row_bot = row_top + STEP_H
    arc_bot = row_bot + ARC_H
    pill_top = arc_bot
    below_top = pill_top + PILL_H + 8
    mid = row_top + STEP_H / 2
    for i, key in enumerate(keys):
        step = steps[key]
        style = "dashed" if step.ghost else "solid"
        shapes.append(rect("step-ghost" if step.ghost else "step-documented", bx(i), row_top,
                           box_w, STEP_H, style=style, key=key))  # fmt: skip
        if step.ghost:
            shapes.append(line("strike", bx(i) + 4, mid, bx(i) + box_w - 4, mid, key=key))
        inner = box_w - 2 * TEXT_PAD
        lines = wrap(step.label, inner, 2)
        if step.minutes is not None:
            lines.append(step.minutes.text)
        shapes.append(text("step-label", bx(i) + 2, row_top + 6, lines, key=key))
        if i + 1 < n:
            shapes.append(line("connector", bx(i) + box_w, mid, bx(i + 1), mid))
        pill = pills.get(key)
        if pill is not None:
            w = _text_width([pill.text])
            # Right-aligned under its step: leaders drop from the step's middle, clear of it.
            shapes.append(text("pill", bx(i) + box_w - w, pill_top + 6, [pill.text], key=key))
    for m, ax, lx, up, level, lines, w in placed:
        at = [index[k] for k in m.keys if k in index]
        first, last = min(at), max(at)
        code, impact = m.code, m.impact_class
        if m.kind in ("skipped", "bypass", "reorder"):
            x1 = cx(first - 1) if m.kind == "skipped" and first > 0 else bx(first)
            x2 = cx(last + 1) if m.kind == "skipped" and last + 1 < n else bx(last) + box_w
            style = {"skipped": "dashed", "bypass": "dotted", "reorder": "dashed"}[m.kind]
            shapes.append(arc(f"arc-{m.kind}", x1, x2, row_top, arc_top + 4, style=style,
                              code=code, impact_class=impact))  # fmt: skip
            tip_y = arc_top
        elif m.kind == "loop":
            x1, x2 = (cx(first), cx(last)) if last > first else (bx(first) + 8, bx(first) +
                                                                  box_w - 8)  # fmt: skip
            shapes.append(arc("arc-loop", x2, x1, row_bot, arc_bot - 4, style="dashed",
                              code=code, impact_class=impact))  # fmt: skip
            tip_y = arc_bot
        elif m.kind == "wait":
            shapes.append(rect("markup-wait", ax - 14, mid - 7, 28, 14, code=code,
                               impact_class=impact))  # fmt: skip
            shapes.append(line("leader", ax, mid + 7, ax, arc_bot, style="dotted"))
            tip_y = arc_bot
        elif m.kind == "added":
            shapes.append(rect("markup-added", ax - 10, row_top - 24, 20, 20, code=code,
                               impact_class=impact))  # fmt: skip
            tip_y = row_top - 24
        else:  # badges: off-system and no record below, another role and longer above
            gx = ax - 9
            if up:
                gy = row_top - 22
            else:
                gy = row_bot + ARC_H - 22
                shapes.append(line("drop", gx + 9, row_bot, gx + 9, gy))
            shapes.append(rect(f"markup-{m.kind.replace('_', '-')}", gx, gy, 18, 18,
                               code=code, impact_class=impact))  # fmt: skip
            tip_y = gy if up else gy + 18
        h = len(lines) * LINE_PX
        if up:
            ly = arc_top - (level + 1) * R_LEVEL + 4
            shapes.append(line("leader", ax, tip_y, lx + w / 2, ly + h, style="dotted"))
        else:
            ly = below_top + level * R_LEVEL
            shapes.append(line("leader", ax, tip_y, lx + w / 2, ly, style="dotted"))
        shapes.append(text("markup-label", lx, ly, lines, code=code, impact_class=impact))
    end = below_top + below.count * R_LEVEL
    return shapes, end


# --- RV5 Where the time goes --------------------------------------------------------------------

T_LEFT = 24.0
T_X0 = 170.0
T_X1 = WIDTH - 240.0
STRIP_H = 36.0
GUIDE_H = 64.0
T_LEVEL = 3 * LINE_PX + 8  # up to three lines: work, extra work, waiting
CAUSE_H = 28.0
CAUSE_X = 470.0
NO_TIME_W = 96.0
TIME_NOTE = "Both strips share one scale: width is minutes a case"


def _minutes(f: Figure | None) -> float:
    return max(0.0, f.value or 0.0) if f is not None else 0.0


def time(model: TimeModel, impacts: Mapping[str, str]) -> ShapeGeometry:
    if not model.columns:
        return _empty(TIME_NOTE)
    manual_sum = sum(_minutes(c.manual) for c in model.columns)
    practice_sum = sum(_minutes(c.wait) + _minutes(c.work) for c in model.columns)
    missing = sum(1 for c in model.columns if c.manual is None)
    missing_work = sum(1 for c in model.columns if c.work is None)
    room = T_X1 - T_X0 - NO_TIME_W * max(missing, missing_work)
    scale = room / max(manual_sum, practice_sum, 1.0)
    shapes: list[Shape] = []
    # The manual's strip: one baseline box per column ("No time stated" when it has none).
    top_levels, bottom_levels = _Levels(), _Levels()
    manual_boxes: list[tuple[str, float, float]] = []  # column id, x, width
    x = T_X0
    for c in model.columns:
        w = _minutes(c.manual) * scale if c.manual is not None else NO_TIME_W
        manual_boxes.append((c.column_id, x, w))
        x += w
    practice_boxes: list[tuple[str, float, list[tuple[str, float]]]] = []
    x = T_X0
    for c in model.columns:
        parts: list[tuple[str, float]] = []
        if c.wait is not None and _minutes(c.wait) > 0:
            parts.append(("wait", _minutes(c.wait) * scale))  # between steps, never inside one
        if c.work is None:
            parts.append(("no-time", NO_TIME_W))
        elif c.designed is not None and c.extra is not None:
            parts.append(("work-designed", _minutes(c.designed) * scale))
            if _minutes(c.extra) > 0:
                parts.append(("work-extra", _minutes(c.extra) * scale))
        else:
            parts.append(("work", _minutes(c.work) * scale))
        practice_boxes.append((c.column_id, x, parts))
        x += sum(w for _, w in parts)
    # Labels: column names over the manual's strip, practice figures under practice's.
    tops = []
    for c, (_, bx, _) in zip(model.columns, manual_boxes, strict=True):
        lines = [*wrap(c.name, 200, 1), c.manual.text if c.manual else "No time stated"]
        w = _text_width(lines)
        lx = _clamp(bx, w, T_X0, T_X1)
        tops.append((lx, top_levels.take(lx, lx + w), lines, c.column_id))
    bottoms = []
    for c, (_, px, _) in zip(model.columns, practice_boxes, strict=True):
        work = c.work.text if c.work else "No time stated"
        extra = [f"Extra {c.extra.text}"] if c.extra is not None and _minutes(c.extra) > 0 else []
        lines = [f"Work {work}", *extra, *([f"Waiting {c.wait.text}"] if c.wait else [])]
        w = _text_width(lines)
        lx = _clamp(px, w, T_X0, T_X1)
        bottoms.append((lx, bottom_levels.take(lx, lx + w), lines, c.column_id))
    manual_y = 16 + top_levels.count * T_LEVEL
    practice_y = manual_y + STRIP_H + GUIDE_H
    labels_y = practice_y + STRIP_H + 12
    for lx, level, lines, cid in tops:
        ly = manual_y - (level + 1) * T_LEVEL + 4
        shapes.append(text("column-label", lx, ly, lines, key=cid))
    for lx, level, lines, cid in bottoms:
        shapes.append(text("practice-label", lx, labels_y + level * T_LEVEL, lines, key=cid))
    shapes.append(text("strip-name", T_LEFT, manual_y + 10, ["The manual"]))
    shapes.append(text("strip-name", T_LEFT, practice_y + 10, ["In practice"]))
    for (cid, bx, w), (_, px, parts) in zip(manual_boxes, practice_boxes, strict=True):
        none = w == NO_TIME_W and not any(c.column_id == cid and c.manual for c in model.columns)
        shapes.append(rect("no-time" if none else "manual", bx, manual_y, w, STRIP_H,
                           style="dashed" if none else "solid", key=cid))  # fmt: skip
        shapes.append(line("guide", bx, manual_y + STRIP_H, px, practice_y, style="dotted"))
        x = px
        for role, pw in parts:
            style = "dashed" if role == "no-time" else "solid"
            shapes.append(rect(role, x, practice_y, pw, STRIP_H, style=style, key=cid))
            x += pw
    # Totals and the multiplier at the right.
    right = T_X1 + 24
    suffix = "" if model.complete else ", incomplete"
    total_m = (model.manual_total.text if model.manual_total else "No time stated") + suffix
    total_p = (model.practice_total.text if model.practice_total else "No time stated") + suffix
    shapes.append(text("total", right, manual_y + 10, [total_m]))
    shapes.append(text("total", right, practice_y + 10, [total_p]))
    if model.multiplier is not None:  # without every time the totals already say "incomplete"
        shapes.append(text("multiplier", right, manual_y + STRIP_H + 16, [model.multiplier.text]))
    # Below: the added minutes broken down by cause, on the same scale.
    y = labels_y + max(1, bottom_levels.count) * T_LEVEL + 24
    if model.causes:
        shapes.append(text("causes-title", T_LEFT, y, ["Added minutes by cause"]))
        y += LINE_PX + 12
        for cause in model.causes:
            impact = impacts.get(cause.code)
            lines = wrap(f"{cause.code} {cause.title}", CAUSE_X - T_LEFT - 24, 1)
            shapes.append(text("cause-label", T_LEFT, y + 4, lines, code=cause.code,
                               impact_class=impact))  # fmt: skip
            w = max(2.0, _minutes(cause.minutes) * scale)
            shapes.append(rect("cause", CAUSE_X, y + 4, w, CAUSE_H - 12, code=cause.code,
                               impact_class=impact))  # fmt: skip
            shapes.append(text("cause-figure", CAUSE_X + w + 8, y + 4, [cause.minutes.text],
                               code=cause.code))  # fmt: skip
            y += CAUSE_H
    return ShapeGeometry(width=WIDTH, height=round(y + 16, 1), shapes=shapes,
                         scale_note=TIME_NOTE)  # fmt: skip


# --- RV6 Belief vs evidence ---------------------------------------------------------------------

B_LEFT = 24.0
B_X0 = 340.0
B_X1 = 1160.0
B_RIGHT = 1190.0
ROW_H = 80.0
BELIEF_NOTE = "Each row has its own scale, from 0 to a little past the larger value"


def belief(model: BeliefModel) -> ShapeGeometry:
    shapes: list[Shape] = []
    y = 16.0
    for row in model.rows:
        b, m = _minutes(row.believed), _minutes(row.measured)
        top = max(b, m) * 1.15 or 1.0
        span = B_X1 - B_X0
        mid = y + ROW_H / 2
        bx, mx = B_X0 + b / top * span, B_X0 + m / top * span
        label = [*wrap(row.label, B_X0 - B_LEFT - 24, 2), f"Scale 0 to {top:.0f} min"]
        shapes.append(text("row-label", B_LEFT, mid - 24, label, key=row.key))
        shapes.append(line("axis", B_X0, mid, B_X1, mid, style="dotted"))
        shapes.append(rect("gap-bar", min(bx, mx), mid - 3, abs(mx - bx), 6, code=row.code,
                           key=row.key, impact_class=row.impact_class))  # fmt: skip
        shapes.append(circle("dot-believed", bx, mid, 7.0, key=row.key))
        shapes.append(circle("dot-measured", mx, mid, 7.0, key=row.key, code=row.code,
                             impact_class=row.impact_class))  # fmt: skip
        believed = [f"Believed {row.believed.text}"]
        measured = [f"Measured {row.measured.text}"]
        wb, wm = _text_width(believed), _text_width(measured)
        lb = _clamp(bx - wb / 2, wb, B_X0 - 8, B_X1 + 8)
        lm = _clamp(mx - wm / 2, wm, B_X0 - 8, B_X1 + 8)
        shapes.append(text("value-believed", lb, mid - 12 - LINE_PX - 4, believed, key=row.key))
        clash = lm < lb + wb + GAP and lb < lm + wm + GAP
        my = mid + 12 if clash else mid - 12 - LINE_PX - 4
        shapes.append(text("value-measured", lm, my, measured, key=row.key))
        shapes.append(text("gap", B_RIGHT, mid - LINE_PX, [row.gap.text, row.prevalence],
                           code=row.code, key=row.key, impact_class=row.impact_class))  # fmt: skip
        y += ROW_H
    note = wrap(model.note, 700, 1)
    shapes.append(text("note", B_LEFT, y + 12, note))
    method = wrap(model.method, WIDTH - 2 * B_LEFT, 3)
    shapes.append(text("method", B_LEFT, y + 12 + LINE_PX + 8, method))
    height = y + 12 + LINE_PX + 8 + len(method) * LINE_PX + 16
    return ShapeGeometry(width=WIDTH, height=round(height, 1), shapes=shapes,
                         scale_note=BELIEF_NOTE)  # fmt: skip


# --- RV7 Typical case ---------------------------------------------------------------------------

C_LEFT = 16.0
C_X0 = 240.0
C_X1 = WIDTH - 120.0
LANE_H = 72.0
C_LEVEL = 2 * LINE_PX + 8
TICKS = (5, 10, 15, 30, 60, 120, 240, 480, 960, 1440, 2880, 5760, 10080)
OFF_STEP = 48.0  # an off-system event with no recorded time after it sits this far on
CASE_NOTE = "Across: minutes since the case started (median timings, not one real case)"


def case(model: CaseModel) -> ShapeGeometry:
    if not model.events:
        return _empty(CASE_NOTE)
    times = [e.minutes.value or 0.0 for e in model.events if e.minutes is not None]
    finishes = [f.value or 0.0 for f in (model.actual_finish, model.designed_finish,
                                         model.promise) if f is not None]  # fmt: skip
    top = max([*times, *finishes, 1.0]) * 1.05
    scale = (C_X1 - C_X0) / top
    # x of every event: recorded at its median time; off-system ones spread between the
    # recorded events either side (never given a time of their own).
    xs: list[float] = []
    i = 0
    events = model.events
    while i < len(events):
        e = events[i]
        if e.minutes is not None:
            xs.append(C_X0 + (e.minutes.value or 0.0) * scale)
            i += 1
            continue
        j = i
        while j < len(events) and events[j].minutes is None:
            j += 1
        start = xs[-1] if xs else C_X0
        nxt = events[j].minutes if j < len(events) else None
        end = C_X0 + (nxt.value or 0.0) * scale if nxt is not None else None
        for k in range(i, j):
            n = k - i + 1
            xs.append(start + (end - start) * n / (j - i + 1) if end is not None and end > start
                      else min(C_X1, start + OFF_STEP * n))  # fmt: skip
        i = j
    # The finish lines' labels at the top, levelled.
    marks = [("finish-designed", "Designed finish", model.designed_finish, "dashed"),
             ("promise", "Promise", model.promise, "double"),
             ("finish-actual", "Actual finish", model.actual_finish, "solid")]  # fmt: skip
    top_levels = _Levels()
    tops = []
    for role, word, f, style in marks:
        if f is None:
            continue
        fx = C_X0 + (f.value or 0.0) * scale
        lines = [word, f.text]
        w = _text_width(lines)
        lx = _clamp(fx - w / 2, w, C_X0, WIDTH - 8)
        tops.append((role, fx, lx, top_levels.take(lx, lx + w), lines, style))
    lanes_top = 16 + max(1, top_levels.count) * C_LEVEL + 8
    lane_y = {lane.id: lanes_top + i * LANE_H for i, lane in enumerate(model.lanes)}
    lanes_bot = lanes_top + len(model.lanes) * LANE_H
    shapes: list[Shape] = []
    for lane in model.lanes:
        ly = lane_y[lane.id]
        shapes.append(rect(f"lane-{lane.kind}", C_X0 - 8, ly, C_X1 - C_X0 + 16, LANE_H,
                           key=lane.id))  # fmt: skip
        shapes.append(text("lane-name", C_LEFT, ly + LANE_H / 2 - LINE_PX,
                           wrap(lane.name, C_X0 - C_LEFT - 24, 2), key=lane.id))  # fmt: skip
    for role, fx, lx, level, lines, style in tops:
        shapes.append(line(role, fx, lanes_top - 4, fx, lanes_bot + 4, style=style))
        shapes.append(text(f"{role}-label", lx, lanes_top - 8 - (level + 1) * C_LEVEL + 4, lines))
    points = [(xs[i], lane_y.get(e.lane_id, lanes_top) + LANE_H / 2) for i, e in enumerate(events)]
    for i in range(1, len(events)):
        a, b = events[i - 1], events[i]
        solid = a.recorded and b.recorded
        shapes.append(
            line("path", *points[i - 1], *points[i], style="solid" if solid else "dotted")
        )
    for e, (px, py) in zip(events, points, strict=True):
        shapes.append(circle("event-recorded" if e.recorded else "event-off-system", px, py,
                             6.0, key=e.key))  # fmt: skip
    # The axis: ticks at a round step, at most 8.
    step = next((t for t in TICKS if top / t <= 8), TICKS[-1])
    axis_y = lanes_bot + 8
    shapes.append(line("axis", C_X0, axis_y, C_X1, axis_y))
    tick = 0.0
    while tick <= top:
        tx = C_X0 + tick * scale
        shapes.append(line("tick", tx, axis_y, tx, axis_y + 6))
        tick_text = [f"{tick:.0f} min"]
        shapes.append(text("tick-label", tx - _text_width(tick_text) / 2, axis_y + 8, tick_text))
        tick += step
    # The step band below: each event's label and time, levelled so none overlaps.
    band_top = axis_y + 8 + LINE_PX + 16
    levels = _Levels()
    for i, (e, (px, _)) in enumerate(zip(events, points, strict=True)):
        lines = [*wrap(e.label, 150, 1), e.minutes.text if e.minutes else "no time recorded"]
        w = _text_width(lines)
        lx = _clamp(px - w / 2, w, C_X0 - 40, WIDTH - 8)
        ly = band_top + levels.take(lx, lx + w) * C_LEVEL
        # A short tick under the axis: the label sits below it at its level, never crossed.
        shapes.append(line("event-tick", px, axis_y + 6 + LINE_PX + 4, px, band_top - 2,
                           style="dotted"))  # fmt: skip
        shapes.append(text("event-label", lx, ly, lines, key=e.key or f"event-{i}"))
    height = band_top + max(1, levels.count) * C_LEVEL + 16
    return ShapeGeometry(width=WIDTH, height=round(height, 1), shapes=shapes,
                         scale_note=CASE_NOTE)  # fmt: skip
