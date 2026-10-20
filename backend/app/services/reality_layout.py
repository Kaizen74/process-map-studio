"""The Reality views' geometry (PRD §5.12.6; P13b): where every ribbon, band, mark and circle
sits on a 1600-wide reference frame. The UI scales and draws it and never computes layout
(constraint 20). Pure and deterministic; the rules are one versioned set (`LAYOUT_VERSION`).

- Glance: a grey trunk (the manual) from the left that fractures into one ribbon per route,
  ordered by share; ribbon width is linear in the share (26 px = 100%, at least 1.5 px).
- Reality stack: five bands on shared columns (the axis of §3.18.2, the whole process last);
  every mark of a column sits inside that column's x range (RQ1); text wraps to the column.
- Fix or keep: the 2 x 2 of zones with an Ask strip below; circle area is hours a month.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from app.domain.reality import (
    Box,
    Circle,
    Column,
    FixGeometry,
    FixModel,
    GlanceGeometry,
    GlanceModel,
    Label,
    LensBox,
    Mark,
    Ribbon,
    StackGeometry,
    StackModel,
    Trunk,
    Zone,
)
from app.services import reality_copy as copy

LAYOUT_VERSION = "5"  # 2: labels (P13b-4); 3: RV4-RV7 (P13c); 4: case starts at 0 (E1);
# 5: the stack's whole-process column has its heading (comprehension pilot)
WIDTH = 1600.0
CHAR_PX = 7.2  # an average 12.5 px IBM Plex Sans character
LINE_PX = 16.0

# Glance
TRUNK_X1, TRUNK_X2, RIBBON_X2, LABEL_X = 80.0, 560.0, 1120.0, 1140.0
MAX_WIDTH, MIN_WIDTH = 26.0, 1.5
RIBBON_GAP = 72.0
GLANCE_MARGIN = 80.0

# Reality stack
GUTTER = 210.0  # band names on the left
RIGHT = 16.0
PROCESS_WIDTH = 190.0
HEADER_Y = 20.0  # column names
LENS_LABEL_Y = 40.0
BAND_TOP = 52.0
BAND_GAP = 12.0
PAD = 8.0
MIN_BAND = {"promise": 72.0, "belief": 64.0, "documented": 96.0, "done": 150.0,
            "consequence": 72.0}  # fmt: skip
MAX_LINES = 2

# Fix or keep
ZONE_X, ZONE_Y, ZONE_W, ZONE_H = 80.0, 40.0, 520.0, 300.0
ASK_H = 150.0
MAX_R, MIN_R = 44.0, 9.0


def wrap(text: str, width: float, max_lines: int = MAX_LINES) -> list[str]:
    """Greedy word wrap to the width; the last line ends in an ellipsis when text is left over."""
    chars = max(4, int(width / CHAR_PX))
    words = " ".join(text.split()).split(" ")
    lines: list[str] = []
    line = ""
    for w in words:
        if not w:
            continue
        candidate = f"{line} {w}".strip()
        if len(candidate) <= chars:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = w if len(w) <= chars else w[: chars - 1] + "…"
    if line:
        lines.append(line)
    if len(lines) > max_lines:
        last = lines[max_lines - 1]
        lines = [*lines[: max_lines - 1], last[: chars - 1].rstrip() + "…"]
    return lines


# --- Glance -------------------------------------------------------------------------------------


def ribbon_width(share: float) -> float:
    return round(max(MIN_WIDTH, MAX_WIDTH * share), 1)


def glance(model: GlanceModel) -> GlanceGeometry:
    n = max(1, len(model.routes))
    height = 2 * GLANCE_MARGIN + (n - 1) * RIBBON_GAP
    middle = height / 2
    widths = [ribbon_width((r.share.value or 0.0) / (100.0 if r.share.unit == "pct" else 1.0)
                           if r.share.unit == "pct" else _step_share(r.share.text))
              for r in model.routes]  # fmt: skip
    total = sum(widths) or MAX_WIDTH
    top = middle - total / 2
    ribbons = []
    for i, (route, w) in enumerate(zip(model.routes, widths, strict=True)):
        start = round(top + w / 2, 1)
        top += w
        end = round(GLANCE_MARGIN + i * RIBBON_GAP, 1)
        path = (f"M{TRUNK_X2:.0f} {start} C {TRUNK_X2 + 240:.0f} {start}, "
                f"{RIBBON_X2 - 260:.0f} {end}, {RIBBON_X2:.0f} {end}")  # fmt: skip
        style = "solid" if route.documented else "dotted" if route.impact_class is None and (
            route.other_count) else "dashed"  # fmt: skip
        ribbons.append(Ribbon(route_id=route.id, path=path, width=w, style=style,
                              label_x=LABEL_X, label_y=end))  # fmt: skip
    scale = ("Line width = share of cases (26 px = 100%)" if model.basis == "cases"
             else "Line width = share of documented steps (26 px = all)")  # fmt: skip
    return GlanceGeometry(width=WIDTH, height=round(height, 1),
                          trunk=Trunk(x1=TRUNK_X1, x2=TRUNK_X2, y=round(middle, 1),
                                      width=round(total, 1)),
                          ribbons=ribbons, scale_note=scale)  # fmt: skip


def _step_share(text: str) -> float:
    """ "3 of 9 steps" → 3/9."""
    parts = text.split(" ")
    try:
        return int(parts[0]) / int(parts[2])
    except (ValueError, IndexError, ZeroDivisionError):
        return 0.0


# --- Reality stack ------------------------------------------------------------------------------


def _columns(columns: Sequence[Column]) -> list[Box]:
    steps = [c for c in columns if c.kind != "process"]
    room = WIDTH - GUTTER - PROCESS_WIDTH - RIGHT
    width = room / max(1, len(steps))
    boxes = [Box(id=c.id, x=round(GUTTER + i * width, 1), y=0.0, width=round(width, 1), height=0.0)
             for i, c in enumerate(steps)]  # fmt: skip
    boxes.append(Box(id="process", x=round(WIDTH - RIGHT - PROCESS_WIDTH, 1), y=0.0,
                     width=PROCESS_WIDTH, height=0.0))  # fmt: skip
    return boxes


def _item_lines(kind: str, label: str, figure: str, note: str, width: float,
                code: str | None = None) -> list[str]:  # fmt: skip
    inner = width - 2 * PAD
    if kind == "branch":
        return [*wrap(f"{code} {label}" if code else label, inner, 1), *wrap(note, inner, 1)]
    if kind in ("minutes", "hours"):
        return wrap(figure, inner, 1)
    lines = wrap(label, inner)
    extra = " · ".join(t for t in (figure, note) if t)
    return [*lines, *wrap(extra, inner, 1)] if extra else lines


def stack(model: StackModel, columns: Sequence[Column]) -> StackGeometry:
    boxes = _columns(columns)
    by_id = {b.id: b for b in boxes}
    marks: list[Mark] = []
    bands: list[Box] = []
    band_labels: list[Label] = []
    y = BAND_TOP
    for band in model.bands:
        name = [*wrap(band.name, GUTTER - 24, 1), *wrap(band.evidence, GUTTER - 24, 2)]
        if band.state == "missing" and band.message:
            name += wrap(band.message, GUTTER - 24, 3)
        band_labels.append(Label(id=band.id, x=12.0, y=round(y + 20, 1), lines=name))
        needed = max(MIN_BAND.get(band.id, 64.0), len(name) * LINE_PX + 2 * PAD)
        placed: list[Mark] = []
        for cell in band.cells:
            box = by_id.get(cell.column_id)
            if box is None:
                continue
            cy = y + PAD
            for it in cell.items:
                figure = it.figure.text if it.figure is not None else ""
                lines = _item_lines(it.kind, it.label, figure, it.note, box.width, it.code)
                h = len(lines) * LINE_PX + PAD
                style = "dashed" if it.kind == "belief" else "solid"
                placed.append(Mark(kind=it.kind, band_id=band.id, column_id=cell.column_id,
                                   x=round(box.x + PAD / 2, 1), y=round(cy, 1),
                                   width=round(box.width - PAD, 1), height=round(h, 1),
                                   lines=lines, code=it.code, key=it.key,
                                   impact_class=it.impact_class, style=style))  # fmt: skip
                cy += h + PAD / 2
            needed = max(needed, cy - y + PAD)
        bands.append(Box(id=band.id, x=0.0, y=round(y, 1), width=WIDTH, height=round(needed, 1)))
        marks += placed
        y += needed + BAND_GAP
    height = round(y + BAND_TOP, 1)
    lens = None
    if model.lens is not None and model.lens.column_id in by_id:
        b = by_id[model.lens.column_id]
        lens = LensBox(x=b.x, y=LENS_LABEL_Y - 14, width=b.width,
                       height=round(height - LENS_LABEL_Y + 6, 1), label_x=round(b.x + PAD, 1),
                       label_y=LENS_LABEL_Y)  # fmt: skip
    names = {c.id: c.name for c in columns} | {"process": copy.WHOLE_PROCESS}
    headers = [Label(id=b.id, x=round(b.x + PAD, 1), y=HEADER_Y,
                     lines=wrap(names.get(b.id, ""), b.width - 2 * PAD, 1))
               for b in boxes]  # fmt: skip
    return StackGeometry(width=WIDTH, height=height,
                         columns=[b.model_copy(update={"height": height}) for b in boxes],
                         bands=bands, marks=marks, lens=lens, column_labels=headers,
                         band_labels=band_labels)  # fmt: skip


# --- Fix or keep --------------------------------------------------------------------------------

ZONES = {  # (column, row) of the 2 x 2: columns follow / depart, rows deliver / fall short
    "as_designed": (0, 0),
    "codify": (1, 0),
    "rewrite": (0, 1),
    "correct": (1, 1),
}


def radius(hours: float, most: float) -> float:
    """Circle area is proportional to hours a month (area, not radius)."""
    if hours <= 0 or most <= 0:
        return MIN_R
    return round(max(MIN_R, MAX_R * math.sqrt(hours / most)), 1)


def fix(model: FixModel, hours: Mapping[str, float]) -> FixGeometry:
    names = {q.id: (q.name, q.meaning) for q in model.quadrants}
    zones = []
    for zid, (col, row) in ZONES.items():
        x, y = ZONE_X + col * ZONE_W, ZONE_Y + row * ZONE_H
        zones.append(Zone(id=zid, x=x, y=y, width=ZONE_W, height=ZONE_H,
                          label_x=x + 12, label_y=y + 20))  # fmt: skip
    ask_y = ZONE_Y + 2 * ZONE_H + 24
    zones.append(Zone(id="ask", x=ZONE_X, y=ask_y, width=2 * ZONE_W, height=ASK_H,
                      label_x=ZONE_X + 12, label_y=ask_y + 20))  # fmt: skip
    by_zone = {z.id: z for z in zones}
    most = max((hours.get(p.code, 0.0) for p in model.circles), default=0.0)
    slots: dict[str, int] = {}
    circles = []
    for p in model.circles:
        z = by_zone[p.zone]
        n = slots.get(p.zone, 0)
        slots[p.zone] = n + 1
        per_row = 4 if p.zone != "ask" else 9
        cx = z.x + 70 + (n % per_row) * 110
        cy = z.y + (96 if p.zone != "ask" else 84) + (n // per_row) * 100
        circles.append(Circle(code=p.code, cx=round(cx, 1), cy=round(cy, 1),
                              r=radius(hours.get(p.code, 0.0), most)))  # fmt: skip
    labels = [Label(id=f"zone:{z.id}", x=z.label_x, y=z.label_y,
                    lines=[names.get(z.id, (z.id, ""))[0],
                           *wrap(names.get(z.id, ("", ""))[1], z.width - 24, 1)])
              for z in zones]  # fmt: skip
    labels += [
        Label(id="axis:follows", x=ZONE_X + 12, y=ZONE_Y - 12, lines=["Follows the manual"]),
        Label(id="axis:departs", x=ZONE_X + ZONE_W + 12, y=ZONE_Y - 12, lines=["Departs from it"]),
        Label(id="axis:delivers", x=ZONE_X + 2 * ZONE_W + 16, y=ZONE_Y + ZONE_H / 2,
              lines=["Delivers the", "promise"]),
        Label(id="axis:short", x=ZONE_X + 2 * ZONE_W + 16, y=ZONE_Y + 1.5 * ZONE_H,
              lines=["Falls short of", "the promise"]),
    ]  # fmt: skip
    return FixGeometry(width=WIDTH, height=round(ask_y + ASK_H + 24, 1), zones=zones,
                       circles=circles, labels=labels,
                       scale_note="Circle area = hours a month; small circles have no measured "
                       "hours")  # fmt: skip
