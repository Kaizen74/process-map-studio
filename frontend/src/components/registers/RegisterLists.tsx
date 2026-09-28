import {
  VALIDATION_LABELS,
  basisLabel,
  causeTypeLabel,
  componentLabel,
  type AiFlagItem,
  type CauseEntry,
  type ConstraintGroup,
  type ExternalPracticeItem,
  type KRiskItem,
  type ValidationResult,
} from "../../lib/registers";
import { divergenceLabel } from "../../lib/matrix";
import { Button, Chip } from "../common";
import "../tabs/tabs.css";
import "./registers.css";

type GoTo = (elementId: string) => void;

function GoToStep({ elementId, label, onGoTo }: { elementId: string; label: string; onGoTo: GoTo }) {
  return (
    <button type="button" className="btn btn--link" onClick={() => onGoTo(elementId)}>
      Go to {label}
    </button>
  );
}

/** Knowledge risk (PRD §5.4 Registers): steps only a few people know how to do. */
export function KRiskList({ items, onGoTo }: { items: readonly KRiskItem[]; onGoTo: GoTo }) {
  if (items.length === 0) {
    return (
      <p className="tab-empty">
        No knowledge risks recorded. A step appears here when your sources say only one or two people know how to do it.
      </p>
    );
  }
  return (
    <ul className="tab-cards">
      {items.map((item) => (
        <li key={item.element_id} className="register-card">
          <p className="register-card__title">
            {item.label} <span className="register-card__lane">· {item.lane}</span>
          </p>
          <p>{item.k_risk}</p>
          <GoToStep elementId={item.element_id} label={item.label} onGoTo={onGoTo} />
        </li>
      ))}
    </ul>
  );
}

/** AI flags in the fixed five-field block; a judgment step's flag reads as support only. */
export function AiFlagList({ items, onGoTo }: { items: readonly AiFlagItem[]; onGoTo: GoTo }) {
  if (items.length === 0) {
    return (
      <p className="tab-empty">No AI flags on this map. Steps where AI could help appear here, with what goes in and out.</p>
    );
  }
  return (
    <ul className="tab-cards">
      {items.map((item) => (
        <li key={item.element_id} className="register-card">
          <p className="register-card__title">
            {item.label} <span className="register-card__lane">· {item.lane}</span>
          </p>
          <dl className="register-fields">
            <div>
              <dt>Component</dt>
              <dd>{componentLabel(item.component)}</dd>
            </div>
            <div>
              <dt>Input</dt>
              <dd>{item.input}</dd>
            </div>
            <div>
              <dt>Output</dt>
              <dd>{item.output}</dd>
            </div>
            <div>
              <dt>Handoff</dt>
              <dd>{item.handoff}</dd>
            </div>
            <div>
              <dt>Basis</dt>
              <dd>{basisLabel(item.basis, item.mechanism)}</dd>
            </div>
          </dl>
          <GoToStep elementId={item.element_id} label={item.label} onGoTo={onGoTo} />
        </li>
      ))}
    </ul>
  );
}

/** Constraints grouped by cause type; key constraints carry the coral dot and the word "Key". */
export function ConstraintGroups({ groups, onGoTo }: { groups: readonly ConstraintGroup[]; onGoTo: GoTo }) {
  if (groups.length === 0) {
    return <p className="tab-empty">No constraints recorded on the steps of this map.</p>;
  }
  return (
    <div className="tab-stack">
      {groups.map((group) => (
        <section
          key={group.cause_type ?? "none"}
          className="tab-group"
          aria-label={causeTypeLabel(group.cause_type)}
        >
          <h3 className="tab-group__title">
            {causeTypeLabel(group.cause_type)} <span className="mono">({group.constraints.length})</span>
          </h3>
          <ul className="tab-cards">
            {group.constraints.map((c, i) => (
              <li key={`${c.element_id}-${i}`} className="register-card">
                <p className="register-constraint">
                  {c.is_key && <span className="register-dot" aria-hidden="true" />}
                  {c.is_key && <span className="visually-hidden">Key constraint: </span>}
                  {c.text}
                </p>
                <p className="register-card__meta">
                  {c.is_key ? "Key · " : ""}Provenance {c.provenance}
                </p>
                <GoToStep elementId={c.element_id} label={c.label} onGoTo={onGoTo} />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

/** Steps added from external practice (provenance R) with their reference. */
export function ExternalPracticeList({ items, onGoTo }: { items: readonly ExternalPracticeItem[]; onGoTo: GoTo }) {
  if (items.length === 0) {
    return (
      <p className="tab-empty">
        No recommended-practice steps. A step appears here when you add one from an external reference.
      </p>
    );
  }
  return (
    <ul className="tab-cards">
      {items.map((item) => (
        <li key={item.element_id} className="register-card">
          <p className="register-card__title">{item.label}</p>
          <p>
            <span className="register-card__meta">Reference: </span>
            {item.r_reference}
          </p>
          <GoToStep elementId={item.element_id} label={item.label} onGoTo={onGoTo} />
        </li>
      ))}
    </ul>
  );
}

export interface CauseListProps {
  entries: readonly CauseEntry[];
  /** The entry being saved right now. */
  busyId: string | null;
  onGoTo: GoTo;
  onValidate: (entry: CauseEntry, result: ValidationResult) => void;
}

/**
 * The cause library: what the sources disagree about (fact), a possible cause only when the step's
 * own constraints name one (inference, to validate), and Eric's verdict.
 */
export function CauseList({ entries, busyId, onGoTo, onValidate }: CauseListProps) {
  if (entries.length === 0) {
    return (
      <p className="tab-empty">
        No entries yet. Each step where the sources disagree gets one when a draft map is made or refreshed.
      </p>
    );
  }
  return (
    <ul className="tab-cards">
      {entries.map((entry) => {
        const pending = entry.validation_result === "pending";
        return (
          <li key={entry.id} className="register-card" aria-busy={busyId === entry.id || undefined}>
            <p className="register-card__title">
              {entry.element_label}
              {entry.divergence_type && (
                <>
                  {" "}
                  <Chip tone="danger">{divergenceLabel(entry.divergence_type)}</Chip>
                </>
              )}{" "}
              <Chip tone={entry.validation_result === "confirmed" ? "good" : "neutral"} dashed={pending}>
                {VALIDATION_LABELS[entry.validation_result] ?? entry.validation_result}
              </Chip>
            </p>
            <p>
              <span className="register-card__meta">What differs (observed): </span>
              {entry.pattern}
            </p>
            {entry.inferred_cause ? (
              <p>
                <span className="register-card__meta">
                  Possible cause (inferred from this step's constraints, {causeTypeLabel(entry.cause_type)}):{" "}
                </span>
                {entry.inferred_cause}
              </p>
            ) : (
              <p className="register-card__meta">Cause not known yet: ask your SME in the validation session.</p>
            )}
            <div className="question__meta">
              {entry.element_id ? (
                <GoToStep elementId={entry.element_id} label={entry.element_label} onGoTo={onGoTo} />
              ) : (
                <span className="register-card__meta">This step is no longer on the map.</span>
              )}
              {pending ? (
                <>
                  <Button onClick={() => onValidate(entry, "confirmed")}>Confirm</Button>
                  <Button onClick={() => onValidate(entry, "refuted")}>Refute</Button>
                </>
              ) : (
                <Button onClick={() => onValidate(entry, "pending")}>Reopen</Button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
