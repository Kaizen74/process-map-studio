import { WIZARD_STEPS } from "../../lib/systemRecords";
import "./system.css";

/** Where the import wizard is: done steps, the current one and those to come, in words. */
export function WizardProgress({ current }: { current: number }) {
  return (
    <ol className="log-wizard__steps" aria-label="Import steps">
      {WIZARD_STEPS.map((label, n) => {
        const state = n < current ? "done" : n === current ? "current" : "to come";
        return (
          <li
            key={label}
            className={`log-wizard__step log-wizard__step--${state.replace(" ", "-")}`}
            aria-current={n === current ? "step" : undefined}
          >
            <span className="log-wizard__num" aria-hidden="true">
              {n + 1}
            </span>
            {label}
            <span className="visually-hidden">, {state}</span>
          </li>
        );
      })}
    </ol>
  );
}
