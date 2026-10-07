import {
  ROUTE_KIND_LABELS,
  exitText,
  frequencyText,
  summaryText,
  type ExceptionReport,
} from "../../lib/exceptions";
import { Chip } from "../common";
import "../tabs/tabs.css";
import "./registers.css";

type GoTo = (elementId: string) => void;

/**
 * Exceptions and workarounds (X3): how much of the process, in one view, is the usual route and
 * how much is exception handling, rework and workarounds. Facts from the map's structure and
 * the SME's own words, kept apart from the questions still to ask; nothing here changes the map.
 * Presentational: the screen fetches.
 */
export function ExceptionList({ report, onGoTo }: { report: ExceptionReport; onGoTo: GoTo }) {
  const { summary, routes, loops, workarounds, questions } = report;
  return (
    <div className="exceptions">
      <h2 className="register-heading">Facts</h2>
      <p className="register-summary">{summaryText(summary)}</p>

      <h3 className="register-subheading">Exception routes and variations</h3>
      {routes.length === 0 ? (
        <p className="tab-empty">No exception routes or variations in this view.</p>
      ) : (
        <ul className="tab-cards" aria-label="Exception routes and variations">
          {routes.map((route) => (
            <li key={route.id} className="register-card">
              <p className="register-card__title">
                {route.from_label} → {route.condition}{" "}
                <Chip dashed={route.kind === "variation"}>{ROUTE_KIND_LABELS[route.kind]}</Chip>
              </p>
              <p>
                {route.labels.join(" → ")}
                {route.lanes.length > 0 && <span className="register-card__lane"> · {route.lanes.join(", ")}</span>}
              </p>
              <p>Then it {route.exits.length > 0 ? route.exits.map(exitText).join(", or ") : "stops (no line out)"}.</p>
              <dl className="register-fields">
                <div>
                  <dt>Extra hand-overs</dt>
                  <dd>{route.handoffs}</dd>
                </div>
                <div>
                  <dt>Frequency</dt>
                  <dd>{route.frequency || "Not stated yet"}</dd>
                </div>
                {route.stated_reason && (
                  <div>
                    <dt>Reason the SME gave</dt>
                    <dd>
                      <q>{route.stated_reason}</q>
                    </dd>
                  </div>
                )}
              </dl>
              <button
                type="button"
                className="btn btn--link"
                onClick={() => onGoTo(route.element_ids[0] ?? route.from_element_id)}
              >
                Go to {route.labels[0] ?? route.from_label}
              </button>
            </li>
          ))}
        </ul>
      )}

      <h3 className="register-subheading">Rework loops</h3>
      {loops.length === 0 ? (
        <p className="tab-empty">No rework loops in this view.</p>
      ) : (
        <ul className="register-plain" aria-label="Rework loops">
          {loops.map((loop) => (
            <li key={`${loop.from_element_id}>${loop.to_element_id}`}>
              {loop.from_label} goes back to {loop.to_label}
              {loop.label && ` (${loop.label})`}{" "}
              <button type="button" className="btn btn--link" onClick={() => onGoTo(loop.from_element_id)}>
                Go to {loop.from_label}
              </button>
            </li>
          ))}
        </ul>
      )}

      <h3 className="register-subheading">Workarounds</h3>
      {workarounds.length === 0 ? (
        <p className="tab-empty">
          No workarounds found. A step appears here when an interviewee gives their reason for doing it another way, or
          tells a workaround story about it.
        </p>
      ) : (
        <ul className="tab-cards" aria-label="Workarounds">
          {workarounds.map((w) => (
            <li key={w.element_id} className="register-card">
              <p className="register-card__title">
                {w.label} <span className="register-card__lane">· {w.lane}</span>
              </p>
              {w.condition && <p>When: {w.condition}</p>}
              {w.stated_reason ? (
                <p>
                  Reason the SME gave: <q>{w.stated_reason}</q>
                </p>
              ) : (
                <p>Told as a workaround story (see the step&apos;s stories).</p>
              )}
              <p>{frequencyText(w.frequency)}</p>
              <button type="button" className="btn btn--link" onClick={() => onGoTo(w.element_id)}>
                Go to {w.label}
              </button>
            </li>
          ))}
        </ul>
      )}

      <h2 className="register-heading">Still to ask</h2>
      {questions.length === 0 ? (
        <p className="tab-empty">Nothing to ask: every route and workaround says how often it happens.</p>
      ) : (
        <ul className="register-plain" aria-label="Questions still to ask">
          {questions.map((q) => (
            <li key={q.about}>
              <span className="mono">[{q.question_id}]</span> {q.wording} <span className="register-card__meta">(about {q.about})</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
