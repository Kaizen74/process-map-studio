import type { BeliefView, CaseView, RedlineView, TimeView } from "../../lib/reality";
import { MetricTiles } from "./RealityBits";
import { ShapeCanvas } from "./ShapeCanvas";
import "./reality.css";

interface DetailProps<V> {
  view: V;
  selected: string | null;
  onSelect: (code: string) => void;
}

/** RV4 Redline (§5.12.3): tracked changes on the SOP, with the markups not drawn listed beside. */
export function Redline({ view, selected, onSelect }: DetailProps<RedlineView>) {
  return (
    <figure className="reality-figure">
      <ShapeCanvas geometry={view.geometry} label={`${view.title} ${view.headline}`} selected={selected} onSelect={onSelect} />
      <figcaption className="inline-note">{view.geometry.scale_note}</figcaption>
    </figure>
  );
}

/** RV5 Where the time goes: the manual's clock against practice's, on one scale. */
export function TimeStretch({ view, selected, onSelect }: DetailProps<TimeView>) {
  return (
    <figure className="reality-figure">
      <ShapeCanvas geometry={view.geometry} label={`${view.title} ${view.headline}`} selected={selected} onSelect={onSelect} />
      <figcaption className="inline-note">{view.geometry.scale_note}</figcaption>
    </figure>
  );
}

/**
 * RV6 Belief vs evidence: believed (hollow) and measured (solid) per row, the gap first. The
 * neutral note and how belief is measured are part of the drawing, with or without rows.
 */
export function BeliefDumbbells({ view, selected, onSelect }: DetailProps<BeliefView>) {
  const b = view.belief;
  return (
    <figure className="reality-figure">
      <ShapeCanvas
        geometry={view.geometry}
        label={`${view.title} ${view.headline} ${b.note} ${b.method}`}
        selected={selected}
        onSelect={onSelect}
      />
      <figcaption className="inline-note">{view.geometry.scale_note}</figcaption>
    </figure>
  );
}

/** RV7 Typical case: a composite of at least 5 cases, labelled as one, never a real case. */
export function CaseJourney({ view, selected, onSelect }: DetailProps<CaseView>) {
  const c = view.case;
  if (c.events.length === 0) return null; // the availability sentence says what it needs
  return (
    <figure className="reality-figure">
      <p className="reality-figure__note">{c.label}</p>
      <MetricTiles tiles={c.tiles} />
      <ShapeCanvas geometry={view.geometry} label={`${view.title} ${view.headline} ${c.label}`} selected={selected} onSelect={onSelect} />
      <figcaption className="inline-note">
        {c.route_name} · {view.geometry.scale_note}
      </figcaption>
    </figure>
  );
}
