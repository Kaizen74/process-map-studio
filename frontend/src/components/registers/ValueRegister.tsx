import { useState, type FormEvent } from "react";
import {
  DISPOSITION_LABELS,
  EVIDENCE_LABELS,
  hoursText,
  money,
  type Assumption,
  type Disposition,
  type DispositionRow,
  type RoleCosts,
  type StepValue,
  type ValueReport,
  type ValueTotal,
} from "../../lib/value";
import { Button, TextField } from "../common";
import "../panel/panel.css";
import "../tabs/tabs.css";
import "./registers.css";

type GoTo = (elementId: string) => void;

/**
 * Disposition and value (PRD §3.14-3.15, §5.4 Registers; R10c): the value calculator's figures
 * for one view, kept in three parts (constraint 9): facts (measured figures), interpretation
 * (estimated, mixed or assumed figures) and recommendation (dispositions and the scenarios,
 * always "Potential, not committed"). Then the inputs Eric sets: role costs and the assumed
 * reduction per disposition. Presentational: the backend works out every figure; the screen
 * fetches and saves. Money is per step, phase and disposition, never per person.
 */
export interface ValueRegisterProps {
  report: ValueReport;
  /** Every step's disposition with its reason; only the view's steps are listed. */
  dispositions: readonly DispositionRow[];
  onGoTo: GoTo;
}

function evidenceText(evidence: ValueTotal["evidence"]): string {
  return evidence ? EVIDENCE_LABELS[evidence].toLowerCase() : "no figures";
}

function totalsText(totals: ValueTotal, currency: string): string {
  if (totals.steps_counted === 0) return "No step has both a time per case and a volume yet, so there are no totals.";
  const steps = totals.steps_counted === 1 ? "1 step" : `${totals.steps_counted} steps`;
  const cost =
    totals.steps_without_cost === totals.steps_counted ? "no cost yet" : `${money(totals.cost_per_month, currency)} a month`;
  return `${hoursText(totals.hours_per_month)} and ${cost} (${evidenceText(totals.evidence)}), from ${steps}.`;
}

function StepTable({ caption, steps, currency, onGoTo }: { caption: string; steps: StepValue[]; currency: string; onGoTo: GoTo }) {
  return (
    <div className="value-table__scroll">
      <table className="value-table">
        <caption className="value-table__caption">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Step</th>
            <th scope="col">Time a case</th>
            <th scope="col">Volume</th>
            <th scope="col">Hours</th>
            <th scope="col">Cost</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((s) => (
            <tr key={s.element_id}>
              <th scope="row">
                <button type="button" className="btn btn--link" onClick={() => onGoTo(s.element_id)}>
                  {s.label}
                </button>
                <span className="value-table__muted">
                  {" "}
                  · {s.role_name}
                  {s.phase_name && ` · ${s.phase_name}`}
                </span>
              </th>
              <td className="mono">
                {s.time ? `${s.time.value.toLocaleString("en-GB", { maximumFractionDigits: 1 })} min` : "Not known"}
                {s.time && <span className="value-table__muted"> {EVIDENCE_LABELS[s.time.label].toLowerCase()}</span>}
              </td>
              <td className="mono">
                {s.volume ? `${s.volume.value.toLocaleString("en-GB", { maximumFractionDigits: 1 })} a month` : "Not known"}
                {s.volume && <span className="value-table__muted"> {EVIDENCE_LABELS[s.volume.label].toLowerCase()}</span>}
              </td>
              <td className="mono">{s.hours_per_month === null ? "Not known" : hoursText(s.hours_per_month)}</td>
              <td className="mono">
                {s.cost_per_month === null ? "No hourly cost" : `${money(s.cost_per_month, currency)} a month`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PhaseTable({ phases, currency }: { phases: ValueTotal[]; currency: string }) {
  return (
    <div className="value-table__scroll">
      <table className="value-table">
        <caption className="value-table__caption">By phase</caption>
        <thead>
          <tr>
            <th scope="col">Phase</th>
            <th scope="col">Hours</th>
            <th scope="col">Cost</th>
            <th scope="col">Evidence</th>
            <th scope="col">Steps counted</th>
          </tr>
        </thead>
        <tbody>
          {phases.map((p) => (
            <tr key={p.phase_id ?? "none"}>
              <th scope="row">{p.name || "No phase"}</th>
              <td className="mono">{hoursText(p.hours_per_month)}</td>
              <td className="mono">
                {p.steps_counted > 0 && p.steps_without_cost === p.steps_counted
                  ? "No hourly cost"
                  : `${money(p.cost_per_month, currency)} a month`}
                {p.steps_without_cost > 0 && p.steps_without_cost < p.steps_counted && (
                  <span className="value-table__muted"> partial: {p.steps_without_cost} without a cost</span>
                )}
              </td>
              <td>{evidenceText(p.evidence)}</td>
              <td className="mono">
                {p.steps_counted}
                {p.steps_missing > 0 && <span className="value-table__muted"> ({p.steps_missing} without figures)</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ValueRegister({ report, dispositions, onGoTo }: ValueRegisterProps) {
  const { currency, potential, steps, phases, totals, scenarios } = report;
  if (steps.length === 0) {
    return (
      <p className="tab-empty">
        No steps in this view yet. Hours and cost appear here for each step once the map has steps with a time per case and
        a volume.
      </p>
    );
  }
  const measured = steps.filter((s) => s.evidence === "measured");
  const interpreted = steps.filter((s) => s.evidence !== null && s.evidence !== "measured");
  const missing = steps.filter((s) => s.evidence === null);
  const inView = new Set(steps.map((s) => s.element_id));
  const rows = dispositions.filter((d) => inView.has(d.element_id));
  const released = scenarios.filter((s) => s.steps > 0);
  return (
    <div className="exceptions">
      <p className="register-summary">{totalsText(totals, currency)}</p>
      {totals.steps_without_cost > 0 && totals.steps_without_cost < totals.steps_counted && (
        <p className="sense-note">
          The cost is partial: {totals.steps_without_cost} of the steps counted have no hourly cost for their role. Add
          role costs below.
        </p>
      )}
      {phases.length > 0 && <PhaseTable phases={phases} currency={currency} />}

      <h2 className="register-heading">Facts: measured figures</h2>
      {measured.length === 0 ? (
        <p className="tab-empty">No step has measured figures. They come from system records matched to the map.</p>
      ) : (
        <StepTable caption="Steps with measured time and volume" steps={measured} currency={currency} onGoTo={onGoTo} />
      )}

      <h2 className="register-heading">Interpretation: estimated, mixed or assumed figures</h2>
      {interpreted.length === 0 ? (
        <p className="tab-empty">No step relies on an estimate or your own figures.</p>
      ) : (
        <StepTable
          caption="Steps with estimated or assumed figures"
          steps={interpreted}
          currency={currency}
          onGoTo={onGoTo}
        />
      )}
      {missing.length > 0 && (
        <>
          <h3 className="register-subheading">Steps without figures</h3>
          <ul className="register-plain" aria-label="Steps without figures">
            {missing.map((s) => (
              <li key={s.element_id}>
                <button type="button" className="btn btn--link" onClick={() => onGoTo(s.element_id)}>
                  {s.label}
                </button>
                : {s.missing.join(" ")}
              </li>
            ))}
          </ul>
        </>
      )}

      <h2 className="register-heading">Recommendation: dispositions and what they could release</h2>
      <p className="value-scenario">
        <em>{potential}.</em> Each figure is the step&apos;s hours times the reduction assumed for its disposition (your
        choice, else the suggestion).
      </p>
      {released.length > 0 && (
        <div className="value-table__scroll">
          <table className="value-table">
            <caption className="value-table__caption">By disposition ({potential.toLowerCase()})</caption>
            <thead>
              <tr>
                <th scope="col">Disposition</th>
                <th scope="col">Steps</th>
                <th scope="col">Hours now</th>
                <th scope="col">Reduction assumed</th>
                <th scope="col">Could release</th>
              </tr>
            </thead>
            <tbody>
              {released.map((s) => (
                <tr key={s.disposition}>
                  <th scope="row">{DISPOSITION_LABELS[s.disposition]}</th>
                  <td className="mono">{s.steps}</td>
                  <td className="mono">{hoursText(s.hours_per_month)}</td>
                  <td className="mono">{s.reduction_pct}%</td>
                  <td className="mono">
                    {hoursText(s.hours_released)}
                    {s.cost_released > 0 && ` · ${money(s.cost_released, currency)} a month`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <h3 className="register-subheading">Disposition by step</h3>
      <ul className="tab-cards" aria-label="Disposition by step">
        {rows.map((row) => (
          <li key={row.element_id} className="register-card">
            <p className="register-card__title">
              {row.label}{" "}
              <span className="register-card__lane">
                · {DISPOSITION_LABELS[row.disposition ?? row.suggested]} ({row.disposition ? "your choice" : "suggested"})
              </span>
            </p>
            <p>
              Suggested: {DISPOSITION_LABELS[row.suggested]}. {row.reason}
            </p>
            {row.note && <p className="register-card__meta">Your note: {row.note}</p>}
            <button type="button" className="btn btn--link" onClick={() => onGoTo(row.element_id)}>
              Go to {row.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

const COST_PROBLEM = "Give an hourly cost from 0 to 100,000.";
const PCT_PROBLEM = "Give a reduction from 0 to 100 percent.";

/** A number from a field: empty is `null`; anything that isn't a number is `undefined`. */
function parsed(text: string): number | null | undefined {
  if (text.trim() === "") return null;
  const n = Number(text);
  return Number.isFinite(n) ? n : undefined;
}

export interface RoleCostsFormProps {
  costs: RoleCosts;
  busy: boolean;
  error: string | null;
  onSave: (rows: { role_id: string; hourly_cost: number | null; note: string }[]) => void;
}

/** Loaded hourly cost per role (§3.14 inputs); empty means no cost, so its steps show hours only. */
export function RoleCostsForm({ costs, busy, error, onSave }: RoleCostsFormProps) {
  const [values, setValues] = useState(() =>
    costs.rows.map((r) => ({ role_id: r.role_id, cost: r.hourly_cost === null ? "" : String(r.hourly_cost), note: r.note })),
  );
  const [problem, setProblem] = useState<string | null>(null);
  const set = (i: number, field: "cost" | "note", text: string) =>
    setValues((current) => current.map((v, j) => (j === i ? { ...v, [field]: text } : v)));
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const rows = values.map((v) => ({ role_id: v.role_id, hourly_cost: parsed(v.cost), note: v.note.trim() }));
    if (rows.some((r) => r.hourly_cost === undefined || (r.hourly_cost !== null && (r.hourly_cost < 0 || r.hourly_cost > 100000)))) {
      return setProblem(COST_PROBLEM);
    }
    setProblem(null);
    onSave(rows.map((r) => ({ ...r, hourly_cost: r.hourly_cost ?? null })));
  }
  if (costs.rows.length === 0) {
    return <p className="tab-empty">This engagement has no roles yet. Add them on Setup to give each an hourly cost.</p>;
  }
  return (
    <form className="stack value-inputs" onSubmit={onSubmit} aria-label="Role costs">
      <p className="sense-note">
        A loaded hourly cost for each role, in {costs.currency}. Leave it empty if you don&apos;t know it: those steps then
        show hours only. Per role, never per person.
      </p>
      {costs.rows.map((r, i) => (
        <fieldset key={r.role_id} className="value-inputs__row">
          <legend>{r.role_name}</legend>
          <TextField
            label={`Hourly cost (${costs.currency})`}
            value={values[i]?.cost ?? ""}
            onChange={(t) => set(i, "cost", t)}
            mono
          />
          <TextField label="Note (optional)" value={values[i]?.note ?? ""} onChange={(t) => set(i, "note", t)} />
        </fieldset>
      ))}
      {(problem ?? error) && (
        <p className="panel-danger" role="alert">
          {problem ?? error}
        </p>
      )}
      <div className="work-type-choice__actions">
        <Button type="submit" variant="primary" disabled={busy}>
          Save role costs
        </Button>
      </div>
    </form>
  );
}

export interface AssumptionsFormProps {
  assumptions: readonly Assumption[];
  busy: boolean;
  error: string | null;
  onSave: (rows: { disposition: Disposition; reduction_pct: number; note: string }[]) => void;
}

/** The time reduction assumed per disposition (§3.14 scenarios); shown as assumptions everywhere. */
export function AssumptionsForm({ assumptions, busy, error, onSave }: AssumptionsFormProps) {
  const [values, setValues] = useState(() =>
    assumptions.map((a) => ({ disposition: a.disposition, pct: String(a.reduction_pct), note: a.note })),
  );
  const [problem, setProblem] = useState<string | null>(null);
  const set = (i: number, field: "pct" | "note", text: string) =>
    setValues((current) => current.map((v, j) => (j === i ? { ...v, [field]: text } : v)));
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const rows = values.map((v) => ({ disposition: v.disposition, reduction_pct: parsed(v.pct), note: v.note.trim() }));
    const bad = rows.some((r) => r.reduction_pct === undefined || r.reduction_pct === null || r.reduction_pct < 0 || r.reduction_pct > 100);
    if (bad) return setProblem(PCT_PROBLEM);
    setProblem(null);
    onSave(rows.map((r) => ({ ...r, reduction_pct: r.reduction_pct ?? 0 })));
  }
  return (
    <form className="stack value-inputs" onSubmit={onSubmit} aria-label="Value assumptions">
      <p className="sense-note">
        How much of a step&apos;s time each disposition is assumed to release. These are assumptions, not measurements;
        every scenario that uses them says so.
      </p>
      {assumptions.map((a, i) => (
        <fieldset key={a.disposition} className="value-inputs__row">
          <legend>
            {DISPOSITION_LABELS[a.disposition]}
            {a.default && " "}
            {a.default && <span className="sense-note">(default)</span>}
          </legend>
          <TextField label="Reduction (%)" value={values[i]?.pct ?? ""} onChange={(t) => set(i, "pct", t)} mono />
          <TextField label="Note (optional)" value={values[i]?.note ?? ""} onChange={(t) => set(i, "note", t)} />
        </fieldset>
      ))}
      {(problem ?? error) && (
        <p className="panel-danger" role="alert">
          {problem ?? error}
        </p>
      )}
      <div className="work-type-choice__actions">
        <Button type="submit" variant="primary" disabled={busy}>
          Save assumptions
        </Button>
      </div>
    </form>
  );
}
