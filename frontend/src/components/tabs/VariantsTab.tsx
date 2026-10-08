import { Button, Chip } from "../common";
import { plural } from "../../lib/format";
import {
  percent,
  type HiddenWorkItem,
  type LogVariants,
  type SystemVariants,
  type VariantStep,
  type ViewFit,
} from "../../lib/systemRecords";
import "./tabs.css";

export interface VariantsTabProps {
  data: SystemVariants;
  onSelect: (elementId: string) => void;
  /** Add as step from hidden work; omitted where the version can't change. */
  onAddHidden?: ((item: HiddenWorkItem, log: LogVariants) => void) | undefined;
}

const VIEW_NAMES = { done: "As done", documented: "As documented" } as const;

function PathStep({ step, onSelect }: { step: VariantStep; onSelect: (id: string) => void }) {
  if (step.status === "matched" && step.element_id) {
    const id = step.element_id;
    return (
      <button type="button" className="btn btn--link variants__step" onClick={() => onSelect(id)}>
        {step.label}
      </button>
    );
  }
  const why = step.status === "hidden_work" ? "hidden work" : "not matched yet";
  return (
    <span className="variants__step variants__step--off">
      {step.activity} <span className="variants__muted">({why})</span>
    </span>
  );
}

function Fit({ view, fit }: { view: keyof typeof VIEW_NAMES; fit: ViewFit }) {
  return (
    <div className="variants__fit">
      {fit.fits ? (
        <Chip tone="good">Fits {VIEW_NAMES[view]}</Chip>
      ) : (
        <Chip dashed>Doesn&apos;t fit {VIEW_NAMES[view]}</Chip>
      )}
      {fit.notes.length > 0 && (
        <ul className="variants__notes">
          {fit.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function HiddenWork({ log, onAddHidden }: { log: LogVariants; onAddHidden: VariantsTabProps["onAddHidden"] }) {
  if (log.hidden_work.length === 0) return null;
  return (
    <section className="variants__hidden" aria-label={`Hidden work in ${log.log_name}`}>
      <h4 className="variants__title">Hidden work</h4>
      <p className="variants__muted">Work the system records that no step on the map shows.</p>
      <ul className="variants__list">
        {log.hidden_work.map((item) => (
          <li key={item.activity} className="variants__row">
            <div>
              <p className="variants__name">{item.activity}</p>
              <p className="variants__muted">
                {plural(item.cases, "case")} ({percent(item.share)})
                {item.after_label && `, mostly after ${item.after_label}`}
                {item.before_label && `, before ${item.before_label}`}
              </p>
            </div>
            {onAddHidden && (
              <Button aria-label={`Add ${item.activity} as a step`} onClick={() => onAddHidden(item, log)}>
                Add as step
              </Button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/**
 * The Variants tab (PRD §5.7.10; R8): each log's top variants, each compared with the As done and
 * As documented paths (the backend says what doesn't fit and why), and the Hidden work list with
 * Add as step. Figures from at least 5 cases only.
 */
export function VariantsTab({ data, onSelect, onAddHidden }: VariantsTabProps) {
  if (data.logs.length === 0) {
    return <p className="tab-empty">No system log is imported for this engagement yet.</p>;
  }
  return (
    <div className="variants">
      {data.logs.map((log) => (
        <section key={log.log_id} className="variants__log" aria-label={`Variants in ${log.log_name}`}>
          <h3 className="variants__title">
            {log.log_name} · {plural(log.cases, "case")}
          </h3>
          {log.variants.length === 0 ? (
            <p className="variants__muted">Too few cases for any variant to be shown.</p>
          ) : (
            <ol className="variants__list">
              {log.variants.map((v) => (
                <li key={v.rank} className="variants__variant" aria-label={`Variant ${v.rank}`}>
                  <p className="variants__name">
                    Variant {v.rank} · {plural(v.cases, "case")} ({percent(v.share)}) · top {v.rank} cover{" "}
                    {percent(v.cumulative_share)}
                  </p>
                  <ol className="variants__path" aria-label={`Variant ${v.rank} path`}>
                    {v.path.map((step, i) => (
                      <li key={`${step.activity}-${i}`}>
                        <PathStep step={step} onSelect={onSelect} />
                      </li>
                    ))}
                  </ol>
                  <div className="variants__fits">
                    <Fit view="done" fit={v.views.done} />
                    <Fit view="documented" fit={v.views.documented} />
                  </div>
                </li>
              ))}
            </ol>
          )}
          {log.too_few > 0 && (
            <p className="variants__muted">
              {plural(log.too_few, "other variant")} not shown: fewer than 5 cases each.
            </p>
          )}
          <HiddenWork log={log} onAddHidden={onAddHidden} />
        </section>
      ))}
      {data.too_few_steps.length > 0 && (
        <p className="variants__muted">
          {plural(data.too_few_steps.length, "matched step")} recorded in fewer than 5 cases: no figures shown.
        </p>
      )}
    </div>
  );
}
