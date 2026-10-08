import type { ReactNode } from "react";
import {
  causeLabel,
  DISPOSITION_LABELS,
  GAP_CLASS_LABELS,
  STRENGTH_LABELS,
  type Disposition,
  type GapClass,
  type GapEvidence,
  type GapFinding,
  type GapMode,
  type GapSource,
  type Severity,
  SEVERITY_LABELS,
  SYSTEM_STANCE_LABELS,
  tierLabel,
  typeLabel,
} from "../../lib/gap";
import type { EvidenceCard as EvidenceCardData } from "../../lib/mapTypes";
import { Button, Chip, SelectField } from "../common";
import { EvidenceCard } from "../panel";
import "./gap.css";

export type DecisionAction = Exclude<Disposition, "open">;

/** Severity as a shape and a word (never colour alone): ▲ high, ◆ medium, ○ low. */
export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (!severity) return null;
  const shape =
    severity === "high" ? (
      <path
        d="M6 1.5 L10.5 10.5 L1.5 10.5 Z"
        className="severity__shape severity__shape--high"
      />
    ) : severity === "medium" ? (
      <path
        d="M6 1.5 L10.5 6 L6 10.5 L1.5 6 Z"
        className="severity__shape severity__shape--medium"
      />
    ) : (
      <circle
        cx="6"
        cy="6"
        r="4.5"
        className="severity__shape severity__shape--low"
      />
    );
  return (
    <span className={`severity severity--${severity}`}>
      <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
        {shape}
      </svg>
      {SEVERITY_LABELS[severity]} severity
    </span>
  );
}

function domainOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

/** One page the web search returned: title, domain, tier, date and the words it cites. */
export function SourceCard({ evidence }: { evidence: GapEvidence }) {
  const domain = domainOf(evidence.url);
  return (
    <div className="source-card">
      <p className="source-card__title">{evidence.source_name || domain}</p>
      <p className="source-card__meta">
        <span className="mono">{domain}</span> ·{" "}
        <Chip>{tierLabel(evidence.tier)}</Chip> ·{" "}
        {evidence.page_age || "Date not given"}
      </p>
      {evidence.quote && (
        <blockquote className="source-card__quote">
          “{evidence.quote}”
        </blockquote>
      )}
      <a
        href={evidence.url}
        target="_blank"
        rel="noopener noreferrer"
        className="source-card__open"
      >
        Open source
        <span className="visually-hidden"> (opens in a new tab)</span>
      </a>
    </div>
  );
}

/** A system log behind a finding: its name, window and what it records (R6). No quotes. */
export function SystemRecordCard({ evidence }: { evidence: GapEvidence }) {
  return (
    <div className="source-card">
      <p className="source-card__title">{evidence.source_name}</p>
      <p className="source-card__meta">
        System log{evidence.anchor && <> · {evidence.anchor}</>} ·{" "}
        {SYSTEM_STANCE_LABELS[evidence.stance]}
      </p>
    </div>
  );
}

/** A page from the source list of an external report (returned or only cited). */
export function SourceListItem({ source }: { source: GapSource }) {
  return (
    <li className="source-list__item">
      <a href={source.url} target="_blank" rel="noopener noreferrer">
        {source.title || source.domain}
      </a>{" "}
      <span className="source-card__meta">
        · {tierLabel(source.tier)} · {source.page_age || "date not given"}
        {!source.returned_in_results &&
          " · cited but not returned by the search"}
      </span>
    </li>
  );
}

function asEvidenceCard(e: GapEvidence): EvidenceCardData {
  return {
    segment_id: e.segment_id,
    source_id: e.source_id,
    source_name: e.source_name,
    source_kind: e.source_kind as EvidenceCardData["source_kind"],
    stance: e.stance,
    anchor: e.anchor,
    verified: Boolean(e.segment_id),
    quote: e.quote,
    note: "",
  };
}

const VERIFIER: Readonly<Record<GapFinding["verifier_verdict"], string>> = {
  supported: "Independent check: supported",
  partial: "Independent check: partly supported (needs check)",
  not_supported: "Independent check: not supported",
  not_run: "Independent check: not run",
};

export interface FindingCardProps {
  finding: GapFinding;
  mode: GapMode;
  /** A finalised report can't change. */
  locked: boolean;
  busy?: boolean;
  onGoTo: (elementId: string) => void;
  onOpenSource: (sourceId: string) => void;
  onDecide: (finding: GapFinding, action: DecisionAction) => void;
  /** A reality gap's class as Eric has chosen it so far (the proposed one until he changes it). */
  chosenClass?: GapClass | undefined;
  onChooseClass?: (finding: GapFinding, gapClass: GapClass) => void;
}

const CLASS_OPTIONS = (Object.keys(GAP_CLASS_LABELS) as GapClass[]).map(
  (value) => ({
    value,
    label: GAP_CLASS_LABELS[value],
  }),
);

/** A reality gap's class with the SME's reason in their own words (§3.12.7). */
function GapClassLine({ finding: f }: { finding: GapFinding }) {
  if (!f.gap_class) return null;
  const state = f.disposition === "open" ? "proposed" : "set by you";
  return (
    <Section title="Gap class">
      <p>
        {GAP_CLASS_LABELS[f.gap_class]} · {state}
        {f.cause_type && (
          <> · cause: {causeLabel(f.cause_type).toLowerCase()}</>
        )}
      </p>
      {f.stated_reason ? (
        <p>
          Reason the SME gave: <q>{f.stated_reason}</q>
        </p>
      ) : (
        <p>
          No reason was stated, so the class is left for you and a question asks
          why.
        </p>
      )}
    </Section>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="finding__section">
      <p className="finding__label">{title}</p>
      {children}
    </div>
  );
}

/**
 * One finding or SME question (PRD §5.4 Gap analysis): type, severity, title and text, the
 * steps it is about, its evidence (both sides for documents vs practice; source cards for
 * external practice), the checks it passed, and Eric's decision.
 */
export function FindingCard({
  finding: f,
  mode,
  locked,
  busy = false,
  onGoTo,
  onOpenSource,
  onDecide,
  chosenClass,
  onChooseClass,
}: FindingCardProps) {
  const quoted = f.evidence.filter(
    (e) => e.side !== "external" && e.side !== "system",
  );
  const external = f.evidence.filter((e) => e.side === "external");
  const system = f.evidence.filter((e) => e.side === "system");
  const isQuestion = Boolean(f.question);
  // While a decision saves, further clicks wait (buttons stay enabled: constraint on the UI).
  const decide = (action: DecisionAction) => {
    if (!busy) onDecide(f, action);
  };
  return (
    <article
      className={`finding${f.disposition === "open" ? " finding--open" : ""}`}
      aria-label={f.title}
    >
      <header className="finding__head">
        <Chip>
          {isQuestion ? "Question for your SMEs" : typeLabel(f.finding_type)}
        </Chip>
        <SeverityBadge severity={f.severity} />
        {f.provenance && (
          <Chip mono title="Provenance">
            {f.provenance}
          </Chip>
        )}
      </header>
      <h3 className="finding__title">{f.title}</h3>
      <p>{f.text}</p>
      {f.elements.length > 0 && (
        <p className="finding__steps">
          {f.elements.map((e) => (
            <button
              key={e.id}
              type="button"
              className="btn btn--link"
              onClick={() => onGoTo(e.id)}
            >
              Open {e.label || "the step"} on the map
            </button>
          ))}
        </p>
      )}
      {mode === "external" && f.comparison && (
        <p className="finding__meta">
          {f.comparison === "absent"
            ? "Absent from the current map"
            : "Done differently on the current map"}
        </p>
      )}
      {f.basis && (
        <Section title="Basis">
          <p>{f.basis}</p>
        </Section>
      )}
      <GapClassLine finding={f} />
      {quoted.length > 0 && (
        <Section title="Evidence">
          <div className="finding__evidence">
            {quoted.map((e, n) => (
              <EvidenceCard
                key={`${e.source_id}-${e.segment_id ?? "silent"}-${n}`}
                card={asEvidenceCard(e)}
                onOpen={(card) => onOpenSource(card.source_id)}
              />
            ))}
          </div>
        </Section>
      )}
      {system.length > 0 && (
        <Section title="System records">
          <div className="finding__evidence">
            {system.map((e) => (
              <SystemRecordCard key={`${e.source_id}-${e.stance}`} evidence={e} />
            ))}
          </div>
        </Section>
      )}
      {external.length > 0 && (
        <Section title="Sources">
          <div className="finding__evidence">
            {external.map((e) => (
              <SourceCard key={e.citation_id} evidence={e} />
            ))}
          </div>
        </Section>
      )}
      {!isQuestion && (
        <p className="finding__meta">
          {mode === "external" && (
            <>{STRENGTH_LABELS[f.evidence_strength]} · </>
          )}
          {VERIFIER[f.verifier_verdict]}
        </p>
      )}
      {f.notes.map((note) => (
        <p key={note} className="finding__note">
          {note}
        </p>
      ))}
      {f.disposition !== "open" ? (
        <p className="finding__decision">
          Decision: {DISPOSITION_LABELS[f.disposition]}
          {f.disposition_note && ` (${f.disposition_note})`}
        </p>
      ) : locked ? null : (
        <div
          className="finding__actions"
          role="group"
          aria-label={`Decide on “${f.title}”`}
          aria-busy={busy || undefined}
        >
          {f.gap_class && onChooseClass && (
            <SelectField
              label="Gap class to keep"
              value={chosenClass ?? f.gap_class}
              options={CLASS_OPTIONS}
              onChange={(value) => onChooseClass(f, value as GapClass)}
            />
          )}
          <Button onClick={() => decide("added_question")}>
            Add as validation question
          </Button>
          {mode === "internal" && f.elements.length > 0 && (
            <Button onClick={() => decide("added_cause")}>
              Add to cause library
            </Button>
          )}
          <Button onClick={() => decide("added_step")}>Add as step</Button>
          <Button onClick={() => decide("dismissed")}>Dismiss</Button>
        </div>
      )}
    </article>
  );
}
