import type { ReactNode } from "react";
import type { Graph } from "../../api/types";
import { plural } from "../../lib/format";

function Fact({ label, value, children }: { label: string; value: string; children?: ReactNode }) {
  return (
    <div className="header-card">
      <p className="header-card__label">{label}</p>
      <p className={value ? "header-card__value" : "header-card__value header-card__value--missing"}>
        {value || "Not stated"}
      </p>
      {children}
    </div>
  );
}

/** Trigger · End point · Cycle time · Process KPI, from the graph's process block (PRD §5.7.2). */
export function HeaderStrip({ process }: { process: Graph["process"] }) {
  const { elapsed_min: elapsed, work_min: work, incomplete_steps: incomplete } = process.cycle_time;
  // No step on the main path states a time: "Not stated", never "~0 min" (2026-10-20).
  const cycle = elapsed === 0 && work === 0 ? "" : `~${elapsed} min elapsed, ~${work} min work`;
  return (
    <section className="header-strip" aria-label="Process at a glance">
      <Fact label="Trigger" value={process.trigger} />
      <Fact label="End point" value={process.end_point} />
      <Fact label="Cycle time · main path" value={cycle}>
        {incomplete > 0 && (
          <p className="header-card__danger">Incomplete: {plural(incomplete, "step")} without time</p>
        )}
      </Fact>
      <Fact label="Process KPI" value={process.kpi} />
    </section>
  );
}
