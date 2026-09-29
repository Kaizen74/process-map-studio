import { useId, useState, type FormEvent, type ReactNode } from "react";
import {
  domainPolicy,
  linesToList,
  removeHit,
  runBlocker,
  type Brief,
  type BriefState,
  type DomainPolicy,
} from "../../lib/gap";
import {
  Button,
  CheckboxField,
  ChipField,
  SegmentedControl,
  TextAreaField,
  TextField,
} from "../common";
import "./gap.css";

export interface BriefEditorProps {
  state: BriefState;
  /** Web research is switched on in Settings. */
  researchEnabled: boolean;
  saving: boolean;
  running: boolean;
  problem: string | null;
  /** Save (and scan again). */
  onSave: (brief: Brief, confirmed: boolean) => void;
  /** Save, then run the research. */
  onRun: (brief: Brief, confirmed: boolean) => void;
  settingsLink: ReactNode;
}

const POLICIES: readonly { value: DomainPolicy; label: string }[] = [
  { value: "none", label: "Any site" },
  { value: "allowed", label: "Only these sites" },
  { value: "blocked", label: "Not these sites" },
];

/**
 * The research brief (PRD §3.11.2 step 1, §5.4): the generic process, industries, steps and
 * questions, and the source policy. The confidentiality scan lists every hit with Remove; only
 * this brief is ever sent to web search, and only once Eric ticks that it holds nothing
 * confidential and the scan is clean.
 */
export function BriefEditor({
  state,
  researchEnabled,
  saving,
  running,
  problem,
  onSave,
  onRun,
  settingsLink,
}: BriefEditorProps) {
  const [brief, setBrief] = useState<Brief>(state.brief);
  const [confirmed, setConfirmed] = useState(state.confirmed);
  const [steps, setSteps] = useState(state.brief.steps.join("\n"));
  const [questions, setQuestions] = useState(state.brief.questions.join("\n"));
  const [policy, setPolicy] = useState<DomainPolicy>(domainPolicy(state.brief));
  const [domains, setDomains] = useState(
    [...state.brief.allowed_domains, ...state.brief.blocked_domains].join("\n"),
  );
  const [blocked, setBlocked] = useState<string | null>(null);
  const rangeId = useId();

  const current = (): Brief => {
    const list = policy === "none" ? [] : linesToList(domains);
    return {
      ...brief,
      steps: linesToList(steps),
      questions: linesToList(questions),
      allowed_domains: policy === "allowed" ? list : [],
      blocked_domains: policy === "blocked" ? list : [],
    };
  };
  const dirty = JSON.stringify(current()) !== JSON.stringify(state.brief);

  const remove = (hit: string) => {
    const next = removeHit(current(), hit);
    setBrief(next);
    setSteps(next.steps.join("\n"));
    setQuestions(next.questions.join("\n"));
    onSave(next, confirmed);
  };

  function save(event: FormEvent) {
    event.preventDefault();
    if (!saving) onSave(current(), confirmed);
  }

  function run() {
    const reason = runBlocker({ ...state, confirmed }, researchEnabled, dirty);
    setBlocked(reason);
    if (!reason && !running) onRun(current(), confirmed);
  }

  const hits = state.scan.hits;
  return (
    <form className="gap-form brief" onSubmit={save} aria-label="Research brief">
      <p className="gap-form__intro">
        Only this brief is sent to web search. Keep it generic: no company, client, site, system or people names, and no
        times or thresholds from your map.
      </p>
      <TextField
        label="Process (generic name)"
        value={brief.process_name}
        onChange={(process_name) => setBrief({ ...brief, process_name })}
      />
      <TextField label="Industry" value={brief.industry} onChange={(industry) => setBrief({ ...brief, industry })} />
      <ChipField
        label="Adjacent industries"
        values={brief.adjacent_industries}
        onChange={(adjacent_industries) => setBrief({ ...brief, adjacent_industries })}
      />
      <TextField
        label="Region focus (optional)"
        value={brief.region}
        onChange={(region) => setBrief({ ...brief, region })}
      />
      <TextAreaField label="Steps (one per line)" value={steps} onChange={setSteps} />
      <TextAreaField label="Research questions (one per line)" value={questions} onChange={setQuestions} />
      <div className="field">
        <label htmlFor={rangeId} className="field__label">
          Most searches: {brief.max_searches}
        </label>
        <input
          id={rangeId}
          type="range"
          min={3}
          max={20}
          value={brief.max_searches}
          aria-valuetext={`${brief.max_searches} searches`}
          onChange={(event) => setBrief({ ...brief, max_searches: Number(event.target.value) })}
        />
        <p className="field__help">Each search is billed by Anthropic.</p>
      </div>
      <SegmentedControl label="Sources" options={POLICIES} value={policy} onChange={setPolicy} />
      {policy !== "none" && (
        <TextAreaField
          label={policy === "allowed" ? "Only search these sites (one per line)" : "Never search these sites (one per line)"}
          value={domains}
          onChange={setDomains}
          help="For example iso.org. You can list allowed sites or blocked sites, not both."
        />
      )}
      <TextField
        label="Sources no older than (years)"
        value={String(brief.recency_years)}
        onChange={(value) => setBrief({ ...brief, recency_years: Number(value.replace(/\D/g, "")) || 0 })}
      />

      <section className="scan" aria-labelledby="scan-title" aria-live="polite">
        <h3 id="scan-title" className="finding__label">
          Confidentiality check
        </h3>
        {dirty ? (
          <p className="finding__meta">You have changes: save the brief to check it again.</p>
        ) : hits.length === 0 ? (
          <p className="finding__meta">No names, confidential terms, map numbers or copied passages found.</p>
        ) : (
          <ul className="scan__hits">
            {hits.map((hit) => (
              <li key={`${hit.reason}-${hit.text}`} className="scan__hit">
                <mark className="scan__text">{hit.text}</mark>
                <span className="finding__meta">{hit.reason}</span>
                <Button variant="link" onClick={() => remove(hit.text)}>
                  Remove<span className="visually-hidden"> “{hit.text}”</span>
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <CheckboxField
        label="This brief contains no confidential information"
        checked={confirmed}
        onChange={setConfirmed}
      />
      {!researchEnabled && (
        <p className="finding__meta">Web research is switched off. {settingsLink}</p>
      )}
      {(blocked ?? problem) && (
        <p className="gap-form__problem" role="alert">
          {blocked ?? problem}
        </p>
      )}
      <div className="gap-form__actions">
        <Button type="submit" aria-busy={saving || undefined}>
          {saving ? "Saving…" : "Save and check"}
        </Button>
        <Button variant="primary" onClick={run} aria-busy={running || undefined}>
          {running ? "Starting…" : "Run research"}
        </Button>
      </div>
    </form>
  );
}
