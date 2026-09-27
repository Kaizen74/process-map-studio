import type { ReactNode } from "react";
import type { ElementDetail, RaciDetail } from "../../lib/mapTypes";
import { AI_BASES, MECHANISMS, signed, words } from "../../lib/panelText";

function Section({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="panel-section" aria-label={title}>
      <h3 className="panel-section__title">
        {title}
        {note && <span className="panel-section__note"> · {note}</span>}
      </h3>
      {children}
    </section>
  );
}

function Rows({ rows }: { rows: [string, string][] }) {
  const shown = rows.filter(([, value]) => value);
  return (
    <dl className="panel-rows">
      {shown.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Section 2: one line per term of the computed confidence, and the total (PRD §5.7.7, G7). */
export function ConfidenceBreakdown({ element }: { element: ElementDetail }) {
  if (element.confidence === null) return null;
  return (
    <Section title="How confidence was computed">
      <dl className="panel-rows panel-rows--numbers">
        {element.confidence_breakdown.map((term, i) => (
          <div key={i}>
            <dt>{term.label}</dt>
            <dd className="mono">{signed(term.delta)}</dd>
          </div>
        ))}
        <div className="panel-rows__total">
          <dt>Confidence</dt>
          <dd className="mono">{element.confidence.toFixed(2)}</dd>
        </div>
      </dl>
    </Section>
  );
}

function competing(entries: RaciDetail[]): string {
  const sides = entries.map((r) => {
    const cited = [...new Set(r.sources.map((s) => `${s.source_name} ${s.anchor}`.trim()))];
    return cited.length ? `${r.role_name} (${cited.join(", ")})` : r.role_name;
  });
  return `Accountability is contested: ${sides.join(" vs ")}.`;
}

/** Section 3: role → letter; a contested A shows as `A?` with the sources on each side. */
export function RoleAccountability({ element }: { element: ElementDetail }) {
  if (element.raci.length === 0) return null;
  const contested = element.raci.filter((r) => r.letter === "A" && r.contested);
  return (
    <Section title="Role and accountability">
      <dl className="panel-rows">
        {element.raci.map((r, i) => {
          const disputed = r.letter === "A" && r.contested;
          return (
            <div key={i}>
              <dt>{r.role_name}</dt>
              <dd className={disputed ? "mono raci-letter raci-letter--contested" : "mono raci-letter"}>
                {disputed ? "A?" : r.letter}
              </dd>
            </div>
          );
        })}
      </dl>
      {contested.length > 0 && <p className="panel-danger">{competing(contested)}</p>}
    </Section>
  );
}

/** Section 4: for decisions and approvals. */
export function DecisionRights({ element }: { element: ElementDetail }) {
  if (element.kind !== "decision" && element.kind !== "approval") return null;
  const { mechanism, rule_or_threshold: rule, escalation } = element.decision;
  return (
    <Section title="Decision rights and mechanism">
      <Rows
        rows={[
          ["Mechanism", MECHANISMS[mechanism] ?? words(mechanism)],
          ["Decider", element.decider_role_name],
          ["Rule or threshold", rule],
          ["Escalation", escalation],
        ]}
      />
    </Section>
  );
}

/** Section 5: handoff and time side by side. */
export function HandoffTime({ element }: { element: ElementDetail }) {
  const { handoff, time } = element;
  const hasHandoff = Boolean(handoff.in || handoff.out);
  const timed = element.kind === "activity" || element.kind === "approval";
  const hasTime = time.work_min !== null || time.wait_min !== null || Boolean(time.text) || element.complexity;
  if (!hasHandoff && !hasTime && !timed) return null;
  return (
    <div className="panel-pair">
      {hasHandoff && (
        <Section title="Handoff">
          <Rows
            rows={[
              ["In", handoff.in],
              ["Out", handoff.out],
            ]}
          />
        </Section>
      )}
      {(hasTime || timed) && (
        <Section title="Time">
          {hasTime ? (
            <Rows
              rows={[
                ["Work", time.work_min !== null ? `~${time.work_min} min` : ""],
                ["Wait", time.wait_min !== null ? `${time.wait_min} min` : ""],
                ["Window", time.text],
                ["Complexity", element.complexity ?? ""],
              ]}
            />
          ) : (
            <p className="panel-danger">No time stated</p>
          )}
        </Section>
      )}
    </div>
  );
}

export function Kpi({ element }: { element: ElementDetail }) {
  if (!element.kpi) return null;
  return (
    <Section title="KPI">
      <p>{element.kpi}</p>
    </Section>
  );
}

/** Section 7: coral dot for key ones, text, and "cause type · provenance". */
export function ConstraintList({ element }: { element: ElementDetail }) {
  if (element.constraints.length === 0) return null;
  return (
    <Section title="Key challenges and constraints">
      <ul className="constraint-list">
        {element.constraints.map((c, i) => (
          <li key={i}>
            <span className={c.is_key ? "constraint-dot" : "constraint-dot constraint-dot--plain"} aria-hidden="true" />
            <span>
              {c.is_key && <span className="visually-hidden">Key constraint: </span>}
              {c.text}
              <span className="constraint-list__meta">
                {[c.cause_type ? words(c.cause_type) : "", `provenance ${c.provenance}`].filter(Boolean).join(" · ")}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function KnowledgeRisk({ element }: { element: ElementDetail }) {
  if (!element.k_risk) return null;
  return (
    <Section title="Knowledge risk">
      <p>{element.k_risk}</p>
    </Section>
  );
}

/** Section 9: the fixed five-field block. */
export function AiFlag({ element }: { element: ElementDetail }) {
  const flag = element.ai_flag;
  if (!flag) return null;
  return (
    <Section title="AI flag">
      <dl className="panel-rows ai-flag">
        {(
          [
            ["Component", words(flag.component)],
            ["Input", flag.input],
            ["Output", flag.output],
            ["Handoff", flag.handoff],
            ["Basis", AI_BASES[flag.basis] ?? words(flag.basis)],
          ] as const
        ).map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}

export { Section as PanelSection };
