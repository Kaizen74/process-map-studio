import { useState } from "react";
import { DIMENSIONS, followUpLine, type CoverageReport } from "../../lib/coverage";
import { INTERVIEW_TYPE_LABELS, profileName, type Profile } from "../../lib/interview";
import { Button, SelectField, StateGlyph } from "../common";
import "./interview.css";

// The Coverage tab (PRD §5.4, §3.12.8; criteria 50, 68; C5d): one row per dimension with a
// covered / thin / missing glyph (shape and text, never colour alone) and its evidence count, the
// ready-to-ask follow-up questions, and the actions. Presentational: the screen does the work.

export interface CoverageViewProps {
  report: CoverageReport;
  mapLabel: string;
  /** Interviewees a Follow-up guide can build on. */
  interviewees: readonly Profile[];
  creating: boolean;
  notice?: { message: string; failed: boolean } | null | undefined;
  onCopy: () => void;
  onDownload: () => void;
  onCreateFollowUp: (earlier: Profile) => void;
}

export function CoverageView({
  report,
  mapLabel,
  interviewees,
  creating,
  notice,
  onCopy,
  onDownload,
  onCreateFollowUp,
}: CoverageViewProps) {
  const [earlierId, setEarlierId] = useState(interviewees[0]?.id ?? "");
  const earlier = interviewees.find((p) => p.id === earlierId);
  const asks = report.follow_up_questions.length + report.probes.length;
  return (
    <div className="coverage">
      <table className="coverage__table">
        <caption className="coverage__caption">What the interviews covered ({mapLabel})</caption>
        <thead>
          <tr>
            <th scope="col">Dimension</th>
            <th scope="col">Coverage</th>
            <th scope="col">Evidence</th>
            <th scope="col">What it is made of</th>
          </tr>
        </thead>
        <tbody>
          {DIMENSIONS.filter((d) => report.dimensions[d.key]).map((d) => {
            const dim = report.dimensions[d.key];
            if (!dim) return null;
            return (
              <tr key={d.key}>
                <th scope="row">{d.label}</th>
                <td>
                  <StateGlyph state={dim.status} />
                </td>
                <td className="mono">{dim.evidence_count}</td>
                <td>{dim.note}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <section className="coverage__asks" aria-labelledby="coverage-asks-title">
        <h3 id="coverage-asks-title" className="guide-editor__title">
          Follow-up questions ({asks})
        </h3>
        <p className="interview-tip">Ready to ask in a 20–30 minute Follow-up interview, word for word from the question bank.</p>
        {report.follow_up_questions.length > 0 && (
          <ul className="coverage__list" aria-label="Questions for thin or missing dimensions">
            {report.follow_up_questions.map((q, i) => (
              <li key={`${q.question_id}-${i}`}>{followUpLine(q)}</li>
            ))}
          </ul>
        )}
        {report.probes.length > 0 && (
          <ul className="coverage__list" aria-label="In the interviewee's own words">
            {report.probes.map((p, i) => (
              <li key={`${p.source_id}-${i}`}>
                {followUpLine(p)}
                {p.speaker_role && <span className="guide-editor__meta"> · ask the {p.speaker_role}</span>}
              </li>
            ))}
          </ul>
        )}
        {asks === 0 && <p className="interview-note">Nothing left to ask: every dimension is covered.</p>}
        <div className="profile-form__actions">
          <Button onClick={onCopy}>Copy</Button>
          <Button onClick={onDownload}>Download .md</Button>
        </div>
      </section>
      <section className="coverage__asks" aria-labelledby="coverage-follow-up-title">
        <h3 id="coverage-follow-up-title" className="guide-editor__title">
          Follow-up guide
        </h3>
        {interviewees.length === 0 ? (
          <p className="interview-note">
            To make a Follow-up guide, first add the interviewee on the Guide tab (a role or a group, never a name).
          </p>
        ) : (
          <>
            <p className="interview-tip">
              A 30-minute Follow-up guide built from this report, the open validation questions and the &quot;not
              described&quot; gaps, for someone you have already interviewed.
            </p>
            <SelectField
              label="Follow up with"
              value={earlierId}
              options={interviewees.map((p) => ({
                value: p.id,
                label: `${profileName(p)} (${INTERVIEW_TYPE_LABELS[p.interview_type]})`,
              }))}
              onChange={setEarlierId}
            />
            <div className="profile-form__actions">
              <Button
                variant="primary"
                aria-busy={creating}
                onClick={() => {
                  if (earlier && !creating) onCreateFollowUp(earlier);
                }}
              >
                {creating ? "Making the Follow-up guide…" : "Create Follow-up guide"}
              </Button>
            </div>
          </>
        )}
        {notice && (
          <p className={notice.failed ? "panel-danger" : "guide-editor__meta"} role={notice.failed ? "alert" : "status"}>
            {notice.message}
          </p>
        )}
      </section>
    </div>
  );
}
