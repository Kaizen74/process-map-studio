import { formatDate, plural } from "../../lib/format";
import type { GraphElement } from "../../lib/mapTypes";
import { percent, spreadText, type SystemTrace } from "../../lib/systemRecords";
import { PanelSection } from "./PanelSections";

export interface SystemDataSectionProps {
  /** The step's system-trace evidence, one per log (only logs with at least 5 cases). */
  traces: readonly SystemTrace[];
  /** The step, for its stated times in each account (SME, documented). */
  element: Pick<GraphElement, "variants" | "time">;
  /** The step is matched but recorded in fewer than 5 cases: no figure is shown. */
  tooFew?: boolean;
}

function logWindow(t: SystemTrace): string {
  return t.window_start && t.window_end ? `${formatDate(t.window_start)} to ${formatDate(t.window_end)}` : "";
}

/** "SME estimate ~10 min · SOP 10 min · measured median 14 min": each account's own words. */
function comparison(element: SystemDataSectionProps["element"], t: SystemTrace): string {
  const sme = element.variants?.done?.time ?? "";
  const documented = element.variants?.documented?.time ?? "";
  const stated = sme || documented ? "" : element.time.text;
  const parts = [
    sme && `SME estimate ${sme}`,
    documented && `SOP ${documented}`,
    stated && `Stated ${stated}`,
    t.work ? `measured median ${t.work.median_min} min` : "",
  ].filter(Boolean);
  return parts.length > 1 ? parts.join(" · ") : "";
}

/**
 * Panel section 4e, System data (PRD §5.7.7; R8): the step's figures from each log matched to it,
 * per step and role, never per person. Shown only while System records is on.
 */
export function SystemDataSection({ traces, element, tooFew = false }: SystemDataSectionProps) {
  if (traces.length === 0) {
    if (!tooFew) return null;
    return (
      <PanelSection title="System data">
        <p>Matched to a system activity, but recorded in fewer than 5 cases: too few cases to show figures.</p>
      </PanelSection>
    );
  }
  return (
    <PanelSection title="System data" note="per step, never per person">
      {traces.map((t) => (
        <div key={t.log_id} className="system-data">
          <p className="system-data__source">
            {t.log_name}
            {t.system && ` (${t.system})`}
            {logWindow(t) && ` · ${logWindow(t)}`}
          </p>
          {t.stance === "contradicts" && t.note && <p className="panel-danger">{t.note}</p>}
          <dl className="panel-rows">
            <div>
              <dt>Volume</dt>
              <dd className="mono">
                {Math.round(t.cases_per_month).toLocaleString("en-GB")} cases/mo ({t.cases_per_week} a week)
              </dd>
            </div>
            <div>
              <dt>Cases</dt>
              <dd className="mono">
                {t.cases} ({plural(t.events, "event")})
              </dd>
            </div>
            <div>
              <dt>Wait before</dt>
              <dd>{t.wait_before ? spreadText(t.wait_before) : "None recorded (the case starts here)"}</dd>
            </div>
            <div>
              <dt>Work</dt>
              <dd>{t.work ? spreadText(t.work) : "No end times in the log"}</dd>
            </div>
            <div>
              <dt>Rework</dt>
              <dd className="mono">
                {percent(t.rework_share)} ({t.rework_cases} cases)
              </dd>
            </div>
            <div>
              <dt>Variants through it</dt>
              <dd>
                {t.variants} of the top variants, {percent(t.variant_share)} of cases
              </dd>
            </div>
            {t.activities.length > 0 && (
              <div>
                <dt>Recorded as</dt>
                <dd>{t.activities.map((a) => a.activity).join(", ")}</dd>
              </div>
            )}
          </dl>
          {comparison(element, t) && <p className="system-data__compare">{comparison(element, t)}</p>}
          {t.basis === "not_separable" && (
            <p className="inline-note">The log has no end times: working and waiting can&apos;t be told apart.</p>
          )}
        </div>
      ))}
    </PanelSection>
  );
}
