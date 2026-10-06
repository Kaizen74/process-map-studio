// State glyphs (PRD §5.2): every source stance or source state is shown by a shape plus a text
// label, never by colour alone. Pure data; components/common/StateGlyph draws it.

export type StanceOrState =
  | "supports"
  | "silent"
  | "contradicts"
  | "corroborated"
  | "documented_only"
  | "practiced_only"
  | "contested"
  | "trace_contradicted"
  | "not_assessed"
  | "not_applicable"
  // Coverage report (§3.12.8): how well the interviews covered a dimension.
  | "covered"
  | "thin"
  | "missing";

export type GlyphShape =
  | "filled-circle"
  | "dashed-ring"
  | "open-ring"
  | "left-half"
  | "right-half"
  | "ring-cross"
  | "outlined-square"
  | "dash";

export type GlyphTone = "good" | "neutral" | "danger";

export interface GlyphSpec {
  shape: GlyphShape;
  tone: GlyphTone;
  label: string;
  /** Label shown in danger text (contested). */
  dangerText: boolean;
}

export const STATE_GLYPHS: Readonly<Record<StanceOrState, GlyphSpec>> = {
  supports: { shape: "filled-circle", tone: "good", label: "Supports", dangerText: false },
  silent: { shape: "dashed-ring", tone: "neutral", label: "Silent", dangerText: false },
  contradicts: { shape: "open-ring", tone: "danger", label: "Contradicts", dangerText: false },
  corroborated: { shape: "filled-circle", tone: "good", label: "Corroborated", dangerText: false },
  documented_only: { shape: "left-half", tone: "good", label: "Documented only", dangerText: false },
  practiced_only: { shape: "right-half", tone: "good", label: "Practiced only", dangerText: false },
  contested: { shape: "open-ring", tone: "danger", label: "Contested", dangerText: true },
  trace_contradicted: {
    shape: "ring-cross",
    tone: "danger",
    label: "Trace contradicted",
    dangerText: false,
  },
  not_assessed: { shape: "outlined-square", tone: "neutral", label: "Not assessed", dangerText: false },
  // Alignment matrix (P9): the engagement has no source of that kind.
  not_applicable: { shape: "dash", tone: "neutral", label: "No source of this kind", dangerText: false },
  covered: { shape: "filled-circle", tone: "good", label: "Covered", dangerText: false },
  thin: { shape: "left-half", tone: "neutral", label: "Thin", dangerText: false },
  missing: { shape: "dashed-ring", tone: "neutral", label: "Missing", dangerText: false },
};

export function glyphFor(state: StanceOrState): GlyphSpec {
  return STATE_GLYPHS[state];
}
