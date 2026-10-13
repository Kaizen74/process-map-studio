import { useState, type FormEvent } from "react";
import {
  DISPOSITION_LABELS,
  EVIDENCE_LABELS,
  RISK_FLAG_LABELS,
  figureText,
  hoursText,
  money,
  type Disposition,
  type DispositionChoice,
  type DispositionRow,
  type RiskFlag,
  type StepValue,
  type ValueOverride,
} from "../../lib/value";
import { Button, SelectField, TextField } from "../common";
import { PanelSection } from "./PanelSections";

// Panel section "Disposition and value" (PRD §5.7.7 4e, §3.14-3.15; R10b). Presentational: the
// backend suggests the disposition, says why some can't be chosen, and works out every figure;
// the screen saves Eric's choice and figures. Shown only while the value module is on.

export interface DispositionValueSectionProps {
  row: DispositionRow;
  /** The step's figures; omitted while they load or when the step has none. */
  value?: StepValue | undefined;
  currency: string;
  /** "Potential, not committed", as the backend words it. */
  potential: string;
  /** Changing the choice or the figures; omitted where the version can't change. */
  edit?:
    | {
        busy: boolean;
        error: string | null;
        onChoose: (choice: DispositionChoice) => void;
        overrideError: string | null;
        onOverride: (override: ValueOverride) => void;
      }
    | undefined;
}

const RISKS = Object.keys(RISK_FLAG_LABELS) as RiskFlag[];

function ChoiceForm({
  row,
  edit,
  onDone,
}: {
  row: DispositionRow;
  edit: NonNullable<DispositionValueSectionProps["edit"]>;
  onDone: () => void;
}) {
  const start = row.disposition ?? (row.allowed.includes(row.suggested) ? row.suggested : row.allowed[0]);
  const [choice, setChoice] = useState<Disposition | undefined>(start);
  const [risk, setRisk] = useState<RiskFlag>(row.risk_flag);
  const [note, setNote] = useState(row.note);
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!choice) return;
    edit.onChoose({ disposition: choice, note: note.trim(), risk_flag: risk });
    onDone();
  }
  return (
    <form className="stack disposition-form" onSubmit={onSubmit}>
      <fieldset className="disposition-form__choices">
        <legend>Your disposition</legend>
        {row.allowed.map((d) => (
          <label key={d} className="disposition-form__choice">
            <input type="radio" name="disposition" value={d} checked={choice === d} onChange={() => setChoice(d)} />
            {DISPOSITION_LABELS[d]}
            {d === row.suggested && <span className="sense-note"> (suggested)</span>}
          </label>
        ))}
      </fieldset>
      {row.not_allowed.length > 0 && (
        <div className="disposition-form__refused">
          <p className="sense-note">Not open to this step:</p>
          <ul>
            {row.not_allowed.map((n) => (
              <li key={n.disposition}>
                <b>{DISPOSITION_LABELS[n.disposition]}</b>: {n.reason}
              </li>
            ))}
          </ul>
        </div>
      )}
      <SelectField
        label="Risk"
        value={risk}
        options={RISKS.map((r) => ({ value: r, label: RISK_FLAG_LABELS[r] }))}
        onChange={(v) => setRisk(v as RiskFlag)}
        help="A financial, safety or regulatory risk means a person authorises the step."
      />
      <TextField label="Note (optional)" value={note} onChange={setNote} help="One line, up to 300 characters; roles, not names." />
      <div className="work-type-choice__actions">
        <Button type="submit" variant="primary" disabled={edit.busy}>
          Save disposition
        </Button>
        <Button onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}

function OverrideForm({
  value,
  edit,
  onDone,
}: {
  value: StepValue | undefined;
  edit: NonNullable<DispositionValueSectionProps["edit"]>;
  onDone: () => void;
}) {
  const own = (f: StepValue["time"]) => (f?.label === "assumed" ? String(f.value) : "");
  const [time, setTime] = useState(own(value?.time ?? null));
  const [volume, setVolume] = useState(own(value?.volume ?? null));
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const number = (text: string) => (text.trim() === "" ? null : Number(text));
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const t = number(time);
    const v = number(volume);
    if ((t !== null && !(t > 0)) || (v !== null && !(v > 0))) return setProblem("Give figures above 0, or leave them empty.");
    if ((t !== null || v !== null) && !note.trim()) return setProblem("Say where the figure comes from.");
    setProblem(null);
    edit.onOverride({ time_min: t, volume_month: v, note: note.trim() });
    onDone();
  }
  return (
    <form className="stack disposition-form" onSubmit={onSubmit}>
      <p className="sense-note">Used only where nothing is measured or stated. Labelled assumed.</p>
      <TextField label="Minutes of work a case" value={time} onChange={setTime} mono />
      <TextField label="Cases a month" value={volume} onChange={setVolume} mono />
      <TextField label="Where the figures come from" value={note} onChange={setNote} error={problem} />
      <div className="work-type-choice__actions">
        <Button type="submit" variant="primary" disabled={edit.busy}>
          Save figures
        </Button>
        <Button onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}

function ValueRows({ value, currency, potential }: { value: StepValue; currency: string; potential: string }) {
  const label = value.evidence ? EVIDENCE_LABELS[value.evidence].toLowerCase() : "";
  return (
    <>
      <dl className="panel-rows">
        <div>
          <dt>Time a case</dt>
          <dd className="mono">{value.time ? figureText(value.time, "min a case") : "Not known"}</dd>
        </div>
        <div>
          <dt>Volume</dt>
          <dd className="mono">{value.volume ? figureText(value.volume, "cases a month") : "Not known"}</dd>
        </div>
        {value.hours_per_month !== null && (
          <div>
            <dt>Hours</dt>
            <dd className="mono">
              {hoursText(value.hours_per_month)} · {label}
            </dd>
          </div>
        )}
        {value.cost_per_month !== null && (
          <div>
            <dt>Cost</dt>
            <dd className="mono">
              {money(value.cost_per_month, currency)} a month · {label}
            </dd>
          </div>
        )}
      </dl>
      {value.missing.length > 0 && (
        <ul className="sense-note value-missing">
          {value.missing.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}
      {value.hours_released !== null && value.reduction_pct > 0 && (
        <p className="value-scenario">
          If {DISPOSITION_LABELS[value.disposition].toLowerCase()}: up to {hoursText(value.hours_released)}
          {value.cost_released !== null && ` and ${money(value.cost_released, currency)} a month`} could be released (
          {value.reduction_pct}% assumed). <em>{potential}.</em>
        </p>
      )}
    </>
  );
}

export function DispositionValueSection({ row, value, currency, potential, edit }: DispositionValueSectionProps) {
  const [mode, setMode] = useState<"view" | "choose" | "figures">("view");
  const suggestionOpen = row.allowed.includes(row.suggested);
  return (
    <PanelSection title="Disposition and value" note="indicative; never per person">
      <dl className="panel-rows">
        <div>
          <dt>Suggested</dt>
          <dd>
            <b>{DISPOSITION_LABELS[row.suggested]}</b>. {row.reason}
          </dd>
        </div>
        <div>
          <dt>Your choice</dt>
          <dd>
            {row.disposition ? (
              <b>{DISPOSITION_LABELS[row.disposition]}</b>
            ) : (
              "Not chosen yet: the figures use the suggestion."
            )}
            {row.note && <span className="sense-note"> {row.note}</span>}
          </dd>
        </div>
        {row.risk_flag !== "none" && (
          <div>
            <dt>Risk</dt>
            <dd>{RISK_FLAG_LABELS[row.risk_flag]}</dd>
          </div>
        )}
      </dl>
      {edit && mode === "choose" && <ChoiceForm row={row} edit={edit} onDone={() => setMode("view")} />}
      {edit && mode === "view" && (
        <div className="work-type-choice__actions">
          {!row.disposition && suggestionOpen && (
            <Button
              variant="primary"
              disabled={edit.busy}
              onClick={() => edit.onChoose({ disposition: row.suggested, note: row.note })}
            >
              Accept the suggestion
            </Button>
          )}
          <Button disabled={edit.busy} onClick={() => setMode("choose")}>
            {row.disposition ? "Change disposition" : "Choose another"}
          </Button>
          {row.disposition && (
            <Button disabled={edit.busy} onClick={() => edit.onChoose({ disposition: null, note: "" })}>
              Clear my choice
            </Button>
          )}
        </div>
      )}
      {edit?.error && (
        <p className="panel-danger" role="alert">
          {edit.error}
        </p>
      )}
      {value && <ValueRows value={value} currency={currency} potential={potential} />}
      {edit && mode === "figures" && <OverrideForm value={value} edit={edit} onDone={() => setMode("view")} />}
      {edit && mode === "view" && (
        <button type="button" className="btn btn--link" onClick={() => setMode("figures")}>
          Set your own figures for this step
        </button>
      )}
      {edit?.overrideError && (
        <p className="panel-danger" role="alert">
          {edit.overrideError}
        </p>
      )}
    </PanelSection>
  );
}
