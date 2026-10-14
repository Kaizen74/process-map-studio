import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  codesAt,
  intentsAt,
  verdictText,
  type Availability,
  type Band,
  type Callout,
  type Circle,
  type CodeEvidence,
  type CodeVerdict,
  type CodeView,
  type Column,
  type Figure,
  type FixGeometry,
  type FixModel,
  type GlanceGeometry,
  type GlanceModel,
  type IntentStatement,
  type Label,
  type Legend,
  type LensBox,
  type Mark,
  type Placed,
  type RealityFigures,
  type RealitySnapshot,
  type Ribbon,
  type Route,
  type SnapshotIntent,
  type StackGeometry,
  type StackItem,
  type StackModel,
  type Tile,
  type VerdictDecided,
  type Zone,
} from "../../src/lib/reality";

// What the backend really sends (written by backend/tests/unit/test_reality_api.py on fixture A.12).
const REALITY = JSON.parse(readFileSync(join(__dirname, "..", "fixtures", "reality.json"), "utf-8")) as {
  snapshot: RealitySnapshot;
  decided: RealitySnapshot;
  intent: IntentStatement[];
  verdict: VerdictDecided;
  leadership_reality: RealityFigures;
};

// Every field of each type, exactly (`satisfies` refuses a missing or an extra one).
const SNAPSHOT = { version_id: 1, rules_version: 1, copy_version: 1, layout_version: 1, app_version: 1, inputs_hash: 1, frozen: 1, draft: 1, process_name: 1, data_label: 1, evidence: 1, figures: 1, tiles: 1, columns: 1, columns_note: 1, codes: 1, intents: 1, views: 1, legend: 1 } satisfies Record<keyof RealitySnapshot, 1>; // prettier-ignore
const FIGURE = { id: 1, value: 1, unit: 1, text: 1, label: 1, percent_type: 1 } satisfies Record<keyof Figure, 1>; // prettier-ignore
const TILE = { figure: 1, caption: 1 } satisfies Record<keyof Tile, 1>; // prettier-ignore
const COLUMN = { id: 1, name: 1, kind: 1, step_keys: 1 } satisfies Record<keyof Column, 1>; // prettier-ignore
const CODE = { code: 1, item_id: 1, title: 1, types: 1, impact_class: 1, impact_word: 1, glyph: 1, impact_note: 1, location: 1, element_ids: 1, column_id: 1, delta: 1, minutes: 1, hours: 1, verdict: 1, evidence: 1, control: 1, shown: 1, rank: 1 } satisfies Record<keyof CodeView, 1>; // prettier-ignore
const VERDICT = { suggested: 1, decided: 1, shown: 1, status: 1, reason: 1, note: 1 } satisfies Record<keyof CodeVerdict, 1>; // prettier-ignore
const EVIDENCE = { documents: 1, interviews: 1, system_cases: 1, chips: 1, sentence: 1 } satisfies Record<keyof CodeEvidence, 1>; // prettier-ignore
const INTENT = { id: 1, kind: 1, text: 1, scope: 1, step_keys: 1, result: 1, target: 1 } satisfies Record<keyof SnapshotIntent, 1>; // prettier-ignore
const VIEW = { id: 1, title: 1, headline: 1, callouts: 1, availability: 1, table: 1 }; // the shared part
const CALLOUT = { code: 1, impact_class: 1, lines: 1 } satisfies Record<keyof Callout, 1>; // prettier-ignore
const AVAILABILITY = { state: 1, message: 1, action: 1 } satisfies Record<keyof Availability, 1>; // prettier-ignore
const GLANCE = { basis: 1, routes: 1 } satisfies Record<keyof GlanceModel, 1>; // prettier-ignore
const ROUTE = { id: 1, name: 1, documented: 1, share: 1, codes: 1, impact_class: 1, other_count: 1 } satisfies Record<keyof Route, 1>; // prettier-ignore
const GLANCE_GEOMETRY = { width: 1, height: 1, trunk: 1, ribbons: 1, scale_note: 1 } satisfies Record<keyof GlanceGeometry, 1>; // prettier-ignore
const RIBBON = { route_id: 1, path: 1, width: 1, style: 1, label_x: 1, label_y: 1 } satisfies Record<keyof Ribbon, 1>; // prettier-ignore
const STACK = { bands: 1, lens: 1, highlighted: 1, listed: 1 } satisfies Record<keyof StackModel, 1>; // prettier-ignore
const BAND = { id: 1, name: 1, evidence: 1, state: 1, message: 1, cells: 1 } satisfies Record<keyof Band, 1>; // prettier-ignore
const ITEM = { kind: 1, key: 1, label: 1, figure: 1, code: 1, impact_class: 1, result: 1, note: 1 } satisfies Record<keyof StackItem, 1>; // prettier-ignore
const STACK_GEOMETRY = { width: 1, height: 1, columns: 1, bands: 1, marks: 1, lens: 1, column_labels: 1, band_labels: 1 } satisfies Record<keyof StackGeometry, 1>; // prettier-ignore
const MARK = { kind: 1, band_id: 1, column_id: 1, x: 1, y: 1, width: 1, height: 1, lines: 1, code: 1, key: 1, impact_class: 1, style: 1 } satisfies Record<keyof Mark, 1>; // prettier-ignore
const LABEL = { id: 1, x: 1, y: 1, lines: 1 } satisfies Record<keyof Label, 1>; // prettier-ignore
const LENS = { x: 1, y: 1, width: 1, height: 1, label_x: 1, label_y: 1 } satisfies Record<keyof LensBox, 1>; // prettier-ignore
const FIX = { quadrants: 1, circles: 1, ask: 1, decide_first: 1, limit: 1, note: 1 } satisfies Record<keyof FixModel, 1>; // prettier-ignore
const PLACED = { code: 1, zone: 1 } satisfies Record<keyof Placed, 1>; // prettier-ignore
const FIX_GEOMETRY = { width: 1, height: 1, zones: 1, circles: 1, labels: 1, scale_note: 1 } satisfies Record<keyof FixGeometry, 1>; // prettier-ignore
const ZONE = { id: 1, x: 1, y: 1, width: 1, height: 1, label_x: 1, label_y: 1 } satisfies Record<keyof Zone, 1>; // prettier-ignore
const CIRCLE = { code: 1, cx: 1, cy: 1, r: 1 } satisfies Record<keyof Circle, 1>; // prettier-ignore
const LEGEND = { impacts: 1, lines: 1, scales: 1, data_label: 1 } satisfies Record<keyof Legend, 1>; // prettier-ignore
const STATEMENT = { id: 1, engagement_id: 1, scope: 1, element_stable_key: 1, element_label: 1, phase_name: 1, kind: 1, origin: 1, text: 1, metric: 1, comparator: 1, target_value: 1, unit: 1, source_id: 1, source_name: 1, anchor: 1, quote: 1, owner_role_id: 1, owner_role_name: 1, stated_on: 1, label: 1, verification_status: 1, rejection_guardrail: 1, status: 1, note: 1, created_at: 1 } satisfies Record<keyof IntentStatement, 1>; // prettier-ignore
const DECIDED = { item_id: 1, code: 1, verdict_decided: 1, verdict_note: 1, decision_owner_role_id: 1 } satisfies Record<keyof VerdictDecided, 1>; // prettier-ignore

const keys = (o: object) => Object.keys(o).sort();
const figure = (f: Figure | null) => f && expect(keys(f)).toEqual(keys(FIGURE));

/** Every figure object anywhere in a value. */
function figures(value: unknown): Figure[] {
  if (Array.isArray(value)) return value.flatMap(figures);
  if (value && typeof value === "object") {
    const o = value as Record<string, unknown>;
    const own = ["id", "value", "unit", "text", "label"].every((k) => k in o) ? [o as unknown as Figure] : [];
    return [...own, ...Object.values(o).flatMap(figures)];
  }
  return [];
}

describe("the frontend's Reality types match what the backend sends (P13b)", () => {
  const s = REALITY.snapshot;

  it("every field of the snapshot, its tiles, columns, codes and intents", () => {
    expect(keys(s)).toEqual(keys(SNAPSHOT));
    Object.values(s.figures).forEach(figure);
    expect(s.tiles.length).toBeGreaterThan(0);
    s.tiles.forEach((t) => {
      expect(keys(t)).toEqual(keys(TILE));
      figure(t.figure);
    });
    s.columns.forEach((c) => expect(keys(c)).toEqual(keys(COLUMN)));
    expect(s.codes.length).toBeGreaterThan(0);
    for (const c of s.codes) {
      expect(keys(c)).toEqual(keys(CODE));
      [c.delta, c.minutes, c.hours].forEach(figure);
      expect(keys(c.evidence)).toEqual(keys(EVIDENCE));
      if (c.verdict) expect(keys(c.verdict)).toEqual(keys(VERDICT));
    }
    s.intents.forEach((i) => expect(keys(i)).toEqual(keys(INTENT)));
    expect(keys(s.legend)).toEqual(keys(LEGEND));
  });

  it("every field of the three views, their models and geometry", () => {
    const { rv1, rv2, rv3 } = s.views;
    for (const v of [rv1, rv2, rv3]) {
      for (const k of keys(VIEW)) expect(v).toHaveProperty(k);
      expect(keys(v.availability)).toEqual(keys(AVAILABILITY));
      v.callouts.forEach((c) => expect(keys(c)).toEqual(keys(CALLOUT)));
    }
    expect(keys(rv1)).toEqual(keys({ ...VIEW, glance: 1, geometry: 1 }));
    expect(keys(rv1.glance)).toEqual(keys(GLANCE));
    rv1.glance.routes.forEach((r) => expect(keys(r)).toEqual(keys(ROUTE)));
    expect(keys(rv1.geometry)).toEqual(keys(GLANCE_GEOMETRY));
    rv1.geometry.ribbons.forEach((r) => expect(keys(r)).toEqual(keys(RIBBON)));

    expect(keys(rv2)).toEqual(keys({ ...VIEW, stack: 1, geometry: 1 }));
    expect(keys(rv2.stack)).toEqual(keys(STACK));
    rv2.stack.bands.forEach((b) => {
      expect(keys(b)).toEqual(keys(BAND));
      b.cells.forEach((c) => c.items.forEach((i) => expect(keys(i)).toEqual(keys(ITEM))));
    });
    expect(keys(rv2.geometry)).toEqual(keys(STACK_GEOMETRY));
    rv2.geometry.marks.forEach((m) => expect(keys(m)).toEqual(keys(MARK)));
    [...rv2.geometry.column_labels, ...rv2.geometry.band_labels].forEach((l) => expect(keys(l)).toEqual(keys(LABEL)));
    if (rv2.geometry.lens) expect(keys(rv2.geometry.lens)).toEqual(keys(LENS));

    expect(keys(rv3)).toEqual(keys({ ...VIEW, fix: 1, geometry: 1 }));
    expect(keys(rv3.fix)).toEqual(keys(FIX));
    rv3.fix.circles.forEach((c) => expect(keys(c)).toEqual(keys(PLACED)));
    expect(keys(rv3.geometry)).toEqual(keys(FIX_GEOMETRY));
    rv3.geometry.zones.forEach((z) => expect(keys(z)).toEqual(keys(ZONE)));
    rv3.geometry.circles.forEach((c) => expect(keys(c)).toEqual(keys(CIRCLE)));
    rv3.geometry.labels.forEach((l) => expect(keys(l)).toEqual(keys(LABEL)));
  });

  it("every field of an intent statement, a decided verdict and Leadership's Reality figures", () => {
    expect(REALITY.intent.length).toBeGreaterThan(0);
    REALITY.intent.forEach((i) => expect(keys(i)).toEqual(keys(STATEMENT)));
    expect(keys(REALITY.verdict)).toEqual(keys(DECIDED));
    expect(keys(REALITY.leadership_reality)).toEqual(keys({ data_label: 1, tiles: 1 }));
  });

  it("each figure has one value everywhere (RQ9) and Leadership shows the snapshot's tiles", () => {
    for (const f of figures({ tiles: s.tiles, codes: s.codes, views: s.views })) {
      expect(s.figures[f.id]).toEqual(f);
    }
    const shared = REALITY.leadership_reality.tiles.map((t) => [t.figure.id, t.figure.text]);
    expect(shared).toEqual(s.tiles.map((t) => [t.figure.id, t.figure.text]));
  });

  it("Eric's verdict shows as confirmed, and the panel helpers find a step's codes and intent", () => {
    const x7 = REALITY.decided.codes.find((c) => c.code === "X7");
    expect(x7?.verdict && verdictText(x7.verdict)).toBe("Codify (confirmed)");
    const x1 = s.codes.find((c) => c.code === "X1");
    expect(x1 && verdictText(x1.verdict)).toBe("Correct (suggested)");
    const element = x1?.element_ids[0] ?? "";
    expect(codesAt(s, element).map((c) => c.code)).toEqual(["X1"]);
    const key = x1?.location.keys[0] ?? "";
    expect(intentsAt(s, key).map((i) => i.kind)).toEqual(["control_objective"]);
  });
});
