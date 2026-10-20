import type { JSX } from "react";
import type {
  Callout,
  CodeEvidence,
  CodeView,
  ImpactClass,
  ImpactGlyph as Glyph,
  Legend,
  Tile,
  ViewTable,
} from "../../lib/reality";
import "./reality.css";

const GLYPH_PATHS: Readonly<Record<Glyph, JSX.Element>> = {
  triangle: <path d="M7 1.5 13 12.5H1Z" />,
  clock: (
    <>
      <circle cx="7" cy="7" r="5.5" />
      <path d="M7 3.8V7l2.4 1.6" />
    </>
  ),
  bars: (
    <>
      <path d="M2 4h10M2 7h10M2 10h10" />
    </>
  ),
  dotted_square: <rect x="2" y="2" width="10" height="10" strokeDasharray="1.6 1.6" />,
};

export interface ImpactGlyphProps {
  glyph: Glyph;
  impact: ImpactClass;
}

/** The impact class's glyph (ER-02): always next to its word, so colour never carries it alone. */
export function ImpactGlyph({ glyph, impact }: ImpactGlyphProps) {
  return (
    <svg className={`impact-glyph impact-glyph--${impact}`} viewBox="0 0 14 14" width="14" height="14" aria-hidden="true">
      {GLYPH_PATHS[glyph]}
    </svg>
  );
}

/** Glyph and word: "▲ Control exposure". */
export function ImpactWord({ code }: { code: Pick<CodeView, "glyph" | "impact_class" | "impact_word"> }) {
  return (
    <span className={`impact-word impact-word--${code.impact_class}`}>
      <ImpactGlyph glyph={code.glyph} impact={code.impact_class} />
      {code.impact_word}
    </span>
  );
}

export interface XBadgeProps {
  code: CodeView;
  selected: boolean;
  onSelect: (code: string) => void;
}

/** An X code's hexagon badge, the same in every view; selecting it highlights it everywhere. */
export function XBadge({ code, selected, onSelect }: XBadgeProps) {
  return (
    <button
      type="button"
      className={`x-badge x-badge--${code.impact_class}`}
      aria-pressed={selected}
      title={`${code.code} · ${code.title} · ${code.delta.text}`}
      onClick={() => onSelect(code.code)}
    >
      {code.code}{" "}
      <span className="visually-hidden">
        {code.title}, {code.impact_word}
      </span>
    </button>
  );
}

/** Evidence chips D · I · S, filled when that kind of evidence exists, with their sentence. */
export function EvidenceChips({ evidence }: { evidence: CodeEvidence }) {
  const chips: [string, boolean][] = [
    ["D", evidence.chips.documents],
    ["I", evidence.chips.interviews],
    ["S", evidence.chips.system],
  ];
  return (
    <span className="evidence-chips">
      {chips.map(([letter, on]) => (
        <span key={letter} className={`evidence-chip${on ? " evidence-chip--on" : ""}`} aria-hidden="true">
          {letter}
        </span>
      ))}
      <span className="visually-hidden">{evidence.sentence}</span>
    </span>
  );
}

/** Up to five metric tiles, each with its figure label (§3.18.5). */
export function MetricTiles({ tiles }: { tiles: readonly Tile[] }) {
  if (tiles.length === 0) return null;
  return (
    <ul className="metric-tiles">
      {tiles.map((t) => (
        <li key={t.figure.id} className="metric-tile">
          <span className="metric-tile__number">{t.figure.text}</span>
          <span className="metric-tile__caption">{t.caption}</span>
          <span className="metric-tile__label">{t.figure.label}</span>
        </li>
      ))}
    </ul>
  );
}

/** The legend strip: impacts with glyphs, line styles, scale notes and the data label. */
export function RealityLegend({ legend, evidence }: { legend: Legend; evidence: string }) {
  return (
    <footer className="reality-legend" aria-label="Legend">
      <ul className="reality-legend__row">
        {legend.impacts.map((i) => (
          <li key={i.impact_class}>
            <ImpactWord code={{ glyph: i.glyph, impact_class: i.impact_class, impact_word: i.word }} />
          </li>
        ))}
      </ul>
      <ul className="reality-legend__row">
        {legend.lines.map((l) => (
          <li key={l.style}>
            <svg width="28" height="8" aria-hidden="true">
              <line x1="0" y1="4" x2="28" y2="4" className={`legend-line legend-line--${l.style}`} />
            </svg>
            {l.meaning}
          </li>
        ))}
      </ul>
      <p className="reality-legend__note">
        {legend.scales.join(" · ")}
      </p>
      {legend.evidence_key && <p className="reality-legend__note">{legend.evidence_key}</p>}
      <p className="reality-legend__note">
        {legend.data_label} · {evidence}
      </p>
    </footer>
  );
}

/** "Show as table": the view's accessible equivalent, with the same figure texts. */
export function RealityTable({ table, caption }: { table: ViewTable; caption: string }) {
  return (
    <div className="reality-table-wrap">
      <table className="reality-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            {table.columns.map((c, i) => (
              <th key={`${c}-${i}`} scope="col">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, r) => (
            <tr key={r}>
              {row.map((cell, i) => (
                <td key={i}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** At most three callouts, each with its impact border and at most two lines. */
export function Callouts({ callouts, legend }: { callouts: readonly Callout[]; legend: Legend }) {
  if (callouts.length === 0) return null;
  // A callout's impact colour comes with the legend's glyph and word (constraint 17).
  const impacts = new Map(legend.impacts.map((i) => [i.impact_class, i]));
  return (
    <ul className="callouts" aria-label="Callouts">
      {callouts.map((c, i) => {
        const impact = c.impact_class ? impacts.get(c.impact_class) : undefined;
        return (
          <li key={`${c.code ?? "note"}-${i}`} className={`callout${c.impact_class ? ` callout--${c.impact_class}` : ""}`}>
            {impact && (
              <p className="callout__impact">
                <ImpactWord code={{ glyph: impact.glyph, impact_class: impact.impact_class, impact_word: impact.word }} />
              </p>
            )}
            {c.lines.map((line, n) => (
              <p key={n}>{line}</p>
            ))}
          </li>
        );
      })}
    </ul>
  );
}

/** The X codes a view draws, as badges: Tab reaches each, selecting one highlights it everywhere. */
export function CodeBadges({
  codes,
  selected,
  onSelect,
}: {
  codes: readonly CodeView[];
  selected: string | null;
  onSelect: (code: string) => void;
}) {
  if (codes.length === 0) return null;
  return (
    <ul className="code-badges" aria-label="Codes on this view">
      {codes.map((c) => (
        <li key={c.code} className={selected !== null && selected !== c.code ? "is-dimmed" : undefined}>
          <XBadge code={c} selected={selected === c.code} onSelect={onSelect} />
        </li>
      ))}
    </ul>
  );
}
