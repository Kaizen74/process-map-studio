import { useState, type FormEvent, type ReactNode } from "react";
import { plural } from "../../lib/format";
import {
  barWidths,
  confidenceText,
  minutes,
  weightText,
  type CauseSummary,
  type DecisionNeeded,
  type LeadershipView,
  type PhaseFacts,
} from "../../lib/leadership";
import { divergenceLabel } from "../../lib/matrix";
import { causeTypeLabel } from "../../lib/registers";
import { Button, Chip, TextAreaField } from "../common";
import { AiFlagList } from "../registers";
import "./leadership.css";

type Labels = ReadonlyMap<string, string>;
type Open = (elementId: string) => void;

/**
 * A figure that opens the steps behind it (PRD §5.4: every figure links to its elements): the
 * figure is the summary of a disclosure listing each step, and each step opens on the map.
 */
export function StepsBehind({
  figure,
  ids,
  labels,
  onOpen,
}: {
  figure: ReactNode;
  ids: readonly string[];
  labels: Labels;
  onOpen: Open;
}) {
  if (ids.length === 0) return <span className="figure figure--none">{figure}</span>;
  return (
    <details className="figure">
      <summary>
        {figure}
        <span className="figure__count"> · {plural(ids.length, "step")}</span>
      </summary>
      <ul className="figure__steps">
        {ids.map((id) => (
          <li key={id}>
            <button type="button" className="btn btn--link" onClick={() => onOpen(id)}>
              Open {labels.get(id) ?? "the step"}
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}

function PhaseRow({ phase, width, labels, onOpen }: { phase: PhaseFacts; width: { work: number; wait: number }; labels: Labels; onOpen: Open }) {
  const divergences = Object.entries(phase.divergence_counts);
  return (
    <li className="phase-facts">
      <p className="phase-facts__name">{phase.name}</p>
      <span className="phase-bar" aria-hidden="true">
        <span className="phase-bar__work" style={{ width: `${width.work}%` }} />
        <span className="phase-bar__wait" style={{ width: `${width.wait}%` }} />
      </span>
      <div className="phase-facts__figures">
        <StepsBehind figure={`Work ${minutes(phase.work_min)}`} ids={phase.links.work} labels={labels} onOpen={onOpen} />
        <StepsBehind figure={`Wait ${minutes(phase.wait_min)}`} ids={phase.links.wait} labels={labels} onOpen={onOpen} />
        <StepsBehind
          figure={plural(phase.rework_loops, "rework loop")}
          ids={phase.links.rework_loops}
          labels={labels}
          onOpen={onOpen}
        />
        <StepsBehind
          figure={plural(phase.handoffs, "handoff between lanes", "handoffs between lanes")}
          ids={phase.links.handoffs}
          labels={labels}
          onOpen={onOpen}
        />
        {divergences.length === 0 ? (
          <span className="figure figure--none">No disagreement between sources</span>
        ) : (
          divergences.map(([type, count]) => (
            <StepsBehind
              key={type}
              figure={`${divergenceLabel(type)} disagreement: ${count}`}
              ids={phase.links.divergence[type] ?? []}
              labels={labels}
              onOpen={onOpen}
            />
          ))
        )}
      </div>
    </li>
  );
}

/** Facts: where the time goes, phase by phase (work solid, wait hatched), and the counts. */
export function FactsColumn({ view, labels, onOpen }: { view: LeadershipView; labels: Labels; onOpen: Open }) {
  const widths = barWidths(view.facts.phases);
  return (
    <section className="leadership-column" aria-labelledby="leadership-facts">
      <h2 id="leadership-facts">Facts</h2>
      <p className="leadership-column__intro">What the published map shows, phase by phase.</p>
      <p className="phase-legend">
        <span className="phase-bar__work phase-legend__swatch" aria-hidden="true" /> Work
        <span className="phase-bar__wait phase-legend__swatch" aria-hidden="true" /> Wait
      </p>
      <ul className="leadership-list">
        {view.facts.phases.map((phase, n) => (
          <PhaseRow key={phase.phase_id ?? "none"} phase={phase} width={widths[n] ?? { work: 0, wait: 0 }} labels={labels} onOpen={onOpen} />
        ))}
      </ul>
    </section>
  );
}

function CauseCard({ cause, labels, onOpen }: { cause: CauseSummary; labels: Labels; onOpen: Open }) {
  return (
    <li className="cause-card">
      <p className="cause-card__head">
        <span className="cause-card__title">{causeTypeLabel(cause.cause_type)}</span>
        <Chip tone={cause.systemic ? "decision" : "neutral"} dashed={!cause.systemic}>
          {cause.systemic ? "Systemic" : "Local"}
        </Chip>
      </p>
      <p className="leadership-column__intro">{cause.reason}</p>
      <p>
        {weightText(cause.evidence_weight)} · {confidenceText(cause.confidence)}
      </p>
      <ul className="cause-card__constraints">
        {cause.constraints.map((c) => (
          <li key={`${c.element_id}-${c.text}`}>
            {c.text}
            {c.is_key && <span className="cause-card__key"> (key constraint)</span>} ·{" "}
            <button type="button" className="btn btn--link" onClick={() => onOpen(c.element_id)}>
              Open {labels.get(c.element_id) ?? c.label}
            </button>
          </li>
        ))}
      </ul>
    </li>
  );
}

/** Interpretation: one card per cause type, systemic or local, with how well it is supported. */
export function InterpretationColumn({ view, labels, onOpen }: { view: LeadershipView; labels: Labels; onOpen: Open }) {
  const causes = view.interpretation.causes;
  return (
    <section className="leadership-column" aria-labelledby="leadership-interpretation">
      <h2 id="leadership-interpretation">Interpretation</h2>
      <p className="leadership-column__intro">
        Why it jams: the causes recorded on the steps. Systemic causes recur across lanes or phases; local ones stay with
        one team.
      </p>
      {causes.length === 0 ? (
        <p className="tab-empty">No causes are recorded on this map's constraints.</p>
      ) : (
        <ul className="leadership-list">
          {causes.map((cause) => (
            <CauseCard key={cause.cause_type} cause={cause} labels={labels} onOpen={onOpen} />
          ))}
        </ul>
      )}
    </section>
  );
}

export interface RecommendationColumnProps {
  view: LeadershipView;
  labels: Labels;
  saving: boolean;
  problem: string | null;
  onOpen: Open;
  onSave: (lines: DecisionNeeded[]) => void;
}

/** Recommendation: what could be won back, the AI flags, and one decision per systemic cause. */
export function RecommendationColumn({ view, labels, saving, problem, onOpen, onSave }: RecommendationColumnProps) {
  const rec = view.recommendation;
  const [lines, setLines] = useState<DecisionNeeded[]>(rec.decisions_needed);
  const [missing, setMissing] = useState<string | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    const long = lines.find((l) => l.text.trim().length > 500);
    if (long) return setMissing("Keep each decision under 500 characters.");
    setMissing(null);
    if (!saving) onSave(lines.map((l) => ({ ...l, text: l.text.trim() })));
  }

  return (
    <section className="leadership-column" aria-labelledby="leadership-recommendation">
      <h2 id="leadership-recommendation">Recommendation</h2>
      <p className="leadership-column__intro">Where to act first.</p>
      <div className="leadership-list">
        <StepsBehind
          figure={`Recoverable wait: ${minutes(rec.recoverable_wait_min)}`}
          ids={rec.recoverable_wait_element_ids}
          labels={labels}
          onOpen={onOpen}
        />
        <p className="leadership-column__intro">Waiting on steps held up by a systemic cause.</p>
        <StepsBehind
          figure={`Rework loops: ${rec.rework_loops}`}
          ids={rec.rework_element_ids}
          labels={labels}
          onOpen={onOpen}
        />
      </div>
      <h3 className="leadership-column__subtitle">AI flags</h3>
      <AiFlagList items={rec.ai_flags} onGoTo={onOpen} />
      <h3 className="leadership-column__subtitle">Decisions needed</h3>
      {lines.length === 0 ? (
        <p className="tab-empty">No systemic cause on this map, so no decision is asked for.</p>
      ) : (
        <form className="leadership-decisions" onSubmit={submit} aria-label="Decisions needed">
          {lines.map((line, n) => (
            <TextAreaField
              key={line.cause_type}
              label={`Decision needed: ${causeTypeLabel(line.cause_type)}`}
              value={line.text}
              onChange={(text) => setLines(lines.map((l, i) => (i === n ? { ...l, text } : l)))}
              help="What should leadership decide about this cause? Up to 500 characters."
            />
          ))}
          {(missing ?? problem) && (
            <p className="leadership-decisions__problem" role="alert">
              {missing ?? problem}
            </p>
          )}
          <Button variant="primary" type="submit" aria-busy={saving || undefined}>
            {saving ? "Saving…" : "Save decisions"}
          </Button>
        </form>
      )}
    </section>
  );
}
