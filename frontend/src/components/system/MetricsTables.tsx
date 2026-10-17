import type { ReactNode } from "react";
import { formatDate, plural } from "../../lib/format";
import {
  basisText,
  percent,
  spreadText,
  tooFewText,
  type ActivityMetrics,
  type CaseMetrics,
  type MetricsResponse,
  type RoleMetrics,
  type TransitionMetrics,
  type VariantMetrics,
} from "../../lib/systemRecords";
import "./system.css";

// The Metrics tab (PRD §5.4 System records, §3.13.5): the figures the import worked out, shown as
// they come. Groups of fewer than 5 cases never reach the screen; the backend counts them in
// `too_few` and each table says how many were left out. Role and step level only (constraint 24).

function Section({ title, note, children }: { title: string; note?: string | undefined; children: ReactNode }) {
  return (
    <section className="log-metrics__section" aria-label={title}>
      <h3 className="log-metrics__title">{title}</h3>
      {children}
      {note && <p className="log-metrics__note">{note}</p>}
    </section>
  );
}

export function CaseSummary({ data }: { data: MetricsResponse<CaseMetrics> }) {
  const group = data.groups[0];
  if (!group) {
    return (
      <Section title="All cases">
        <p>Too few cases to show (fewer than {data.minimum_cases}).</p>
      </Section>
    );
  }
  const m = group.metrics;
  return (
    <Section title="All cases" note={basisText(m.basis)}>
      <dl className="log-metrics__summary">
        <dt>Cases</dt>
        <dd>{m.cases}</dd>
        <dt>Events</dt>
        <dd>{m.events}</dd>
        <dt>Dates</dt>
        <dd>
          {m.date_from && m.date_to ? `${formatDate(m.date_from)} to ${formatDate(m.date_to)}` : "None"} (
          {plural(m.weeks, "week")})
        </dd>
        <dt>Start to finish</dt>
        <dd>{spreadText(m.cycle_time)}</dd>
        <dt>Rework</dt>
        <dd>
          {percent(m.rework_share)} of cases ({m.rework_cases})
        </dd>
        <dt>Handoffs</dt>
        <dd>{m.handoffs_per_case} per case</dd>
        <dt>Variants</dt>
        <dd>
          {m.variants}; {percent(m.exception_share)} of cases don&apos;t follow the most common one
        </dd>
      </dl>
    </Section>
  );
}

export function ActivityTable({ data }: { data: MetricsResponse<ActivityMetrics> }) {
  return (
    <Section title="Volume and waits per activity" note={tooFewText(data.too_few, "activity", "activities")}>
      <table className="log-metrics__table">
        <thead>
          <tr>
            <th scope="col">Activity</th>
            <th scope="col">Cases</th>
            <th scope="col">Per week</th>
            <th scope="col">Work</th>
            <th scope="col">Wait before</th>
            <th scope="col">Repeated in</th>
          </tr>
        </thead>
        <tbody>
          {data.groups.map(({ key, metrics: m }) => (
            <tr key={key}>
              <th scope="row">{m.activity}</th>
              <td>{m.cases}</td>
              <td>{m.cases_per_week}</td>
              <td>{m.work ? spreadText(m.work) : "No end times"}</td>
              <td>
                {spreadText(m.wait_before)}
                {m.basis === "not_separable" && <span className="log-metrics__muted"> (working and waiting)</span>}
              </td>
              <td>
                {percent(m.rework_share)} ({m.rework_cases})
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

export function TransitionTable({ data }: { data: MetricsResponse<TransitionMetrics> }) {
  return (
    <Section title="Handoffs and waits between activities" note={tooFewText(data.too_few, "move")}>
      <table className="log-metrics__table">
        <thead>
          <tr>
            <th scope="col">From</th>
            <th scope="col">To</th>
            <th scope="col">Cases</th>
            <th scope="col">Time between</th>
            <th scope="col">Handoffs</th>
          </tr>
        </thead>
        <tbody>
          {data.groups.map(({ key, metrics: m }) => (
            <tr key={key}>
              <th scope="row">{m.from_activity}</th>
              <td>{m.to_activity}</td>
              <td>{m.cases}</td>
              <td>{spreadText(m.elapsed)}</td>
              <td>
                {m.handoffs} of {m.count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

export function VariantTable({ data }: { data: MetricsResponse<VariantMetrics> }) {
  const last = data.groups.at(-1)?.metrics.cumulative_share ?? 0;
  return (
    <Section
      title="Variants (top 10)"
      note={[`These variants cover ${percent(last)} of cases.`, tooFewText(data.too_few, "variant")].filter(Boolean).join(" ")}
    >
      <table className="log-metrics__table">
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Path</th>
            <th scope="col">Cases</th>
            <th scope="col">Share</th>
            <th scope="col">Coverage</th>
          </tr>
        </thead>
        <tbody>
          {data.groups.map(({ key, metrics: m }) => (
            <tr key={key}>
              <th scope="row">{m.rank}</th>
              <td>{m.activities.join(" → ")}</td>
              <td>{m.cases}</td>
              <td>{percent(m.share)}</td>
              <td>{percent(m.cumulative_share)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

export function RoleTable({ data }: { data: MetricsResponse<RoleMetrics> }) {
  return (
    <Section title="Per role" note={tooFewText(data.too_few, "role")}>
      <table className="log-metrics__table">
        <thead>
          <tr>
            <th scope="col">Role</th>
            <th scope="col">Cases</th>
            <th scope="col">Events</th>
            <th scope="col">Work</th>
            <th scope="col">Activities</th>
          </tr>
        </thead>
        <tbody>
          {data.groups.map(({ key, metrics: m }) => (
            <tr key={key}>
              <th scope="row">{m.role}</th>
              <td>{m.cases}</td>
              <td>{m.events}</td>
              <td>{m.work ? spreadText(m.work) : "No end times"}</td>
              <td>{m.activities.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Section>
  );
}

