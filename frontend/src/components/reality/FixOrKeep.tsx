import type { CodeView, FixView } from "../../lib/reality";
import { canvasWidth, verdictText } from "../../lib/reality";
import { EvidenceChips, ImpactWord } from "./RealityBits";
import "./reality.css";

export interface FixOrKeepProps {
  view: FixView;
  codes: readonly CodeView[];
  selected: string | null;
  onSelect: (code: string) => void;
  showAll: boolean;
  onShowAll: () => void;
}

/**
 * RV3 Fix or keep (PRD §5.12.3): the 2 × 2 of following or departing from the manual against
 * delivering the promise or not, each X code as a circle (area = hours a month), and the Decide
 * first list beside it. Drawn from the backend geometry only.
 */
export function FixOrKeep({ view, codes, selected, onSelect, showAll, onShowAll }: FixOrKeepProps) {
  const g = view.geometry;
  const byCode = new Map(codes.map((c) => [c.code, c]));
  const rows = view.fix.decide_first.map((c) => byCode.get(c)).filter((c): c is CodeView => Boolean(c));
  const shown = showAll ? rows : rows.slice(0, view.fix.limit);
  return (
    <div className="fix-or-keep">
      <svg className="reality-canvas" style={canvasWidth(g.width)} viewBox={`0 0 ${g.width} ${g.height}`} role="img" aria-label={`${view.title} ${view.headline}`}>
        {g.zones.map((z) => (
          <rect key={z.id} className={`fix-zone fix-zone--${z.id}`} x={z.x} y={z.y} width={z.width} height={z.height} />
        ))}
        {g.labels.map((l) => (
          <text key={l.id} className="reality-label" x={l.x} y={l.y}>
            {l.lines.map((line, i) => (
              <tspan key={i} x={l.x} dy={i === 0 ? 0 : 16} className={i === 0 ? "reality-label--strong" : undefined}>
                {line}
              </tspan>
            ))}
          </text>
        ))}
        {g.circles.map((c) => {
          const code = byCode.get(c.code);
          const dimmed = selected !== null && selected !== c.code;
          return (
            <g key={c.code} className={dimmed ? "is-dimmed" : undefined} onClick={() => onSelect(c.code)}>
              <circle className={`fix-circle fix-circle--${code?.impact_class ?? "neutral"}`} cx={c.cx} cy={c.cy} r={c.r} />
              <text className="fix-code" x={c.cx} y={c.cy + c.r + 16} textAnchor="middle">
                {c.code}
              </text>
            </g>
          );
        })}
      </svg>
      <section className="decide-first" aria-labelledby="decide-first-title">
        <h3 id="decide-first-title">Decide first</h3>
        <ol className="decide-first__list">
          {shown.map((c) => (
            <li key={c.code} className={selected !== null && selected !== c.code ? "is-dimmed" : undefined}>
              <button type="button" className="decide-first__row" aria-pressed={selected === c.code} onClick={() => onSelect(c.code)}>
                <span className="decide-first__code">{c.code}</span>{" "}
                <span className="decide-first__title">{c.title}</span>
              </button>
              <span className="decide-first__meta">
                <ImpactWord code={c} />
                <span>{verdictText(c.verdict)}</span>
                <span>{c.hours ? c.hours.text : "Needs system records"}</span>
                <EvidenceChips evidence={c.evidence} />
              </span>
              {c.verdict?.reason && <span className="decide-first__reason">{c.verdict.reason}</span>}
              {c.impact_note && <span className="decide-first__reason">{c.impact_note}</span>}
            </li>
          ))}
        </ol>
        {rows.length > view.fix.limit && !showAll && (
          <button type="button" className="btn btn--link" onClick={onShowAll}>
            Show all {rows.length}
          </button>
        )}
        <p className="inline-note">{view.fix.note}</p>
      </section>
    </div>
  );
}
