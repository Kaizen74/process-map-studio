import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import {
  Button,
  Card,
  Chip,
  EmptyState,
  ErrorState,
  GradeControl,
  SelectField,
  Skeleton,
  TextField,
} from "../../components/common";
import { useEngagement } from "../../hooks/useEngagements";
import {
  useCandidates,
  useComparison,
  useComparisons,
  useDecideDifference,
  useRefreshComparison,
  useSetPair,
  useStartComparison,
  useSuggestPairs,
} from "../../hooks/useComparisons";
import { comparisonExportUrl } from "../../api/comparisons";
import {
  PAIR_LABELS,
  REASON_HELP,
  REASON_LABELS,
  STATUS_LABELS,
  TOPIC_LABELS,
  type ComparedStep,
  type Comparison,
  type Difference,
  type ReasonClass,
} from "../../lib/comparisons";
import { engagementPath } from "../../lib/engagementSteps";
import { messageOf } from "../../lib/errors";
import type { GradeKey } from "../../lib/grade";
import { EngagementProblem } from "../engagement/EngagementProblem";
import "./compare.css";

/**
 * Compare countries (PRD §3.19; DECISIONS 98): two published maps of the same process in two
 * countries. Eric chooses the reference and the other country, confirms the step pairs, and classes
 * each difference the rules find. The app never says why two countries differ: the reason is his.
 */
export function CompareScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const candidates = useCandidates(engagementId);
  const existing = useComparisons(engagementId);
  const [params, setParams] = useSearchParams();
  const comparisonId = params.get("comparison");

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }
  return (
    <main className="screen" aria-labelledby="compare-title">
      <div>
        <h1 id="compare-title">Compare countries</h1>
        <p className="screen__intro">
          Two published maps of the same process in two countries, step by step. Confirm which steps are the same
          work, then class each difference: Required, Chosen, Inherited or Not known yet. The reason is always
          yours; nothing here changes either map.
        </p>
      </div>
      {(candidates.isPending || existing.isPending) && <Skeleton height="120px" />}
      {candidates.isError && (
        <ErrorState
          title="The maps to compare couldn't be loaded"
          message={messageOf(candidates.error)}
          onRetry={() => void candidates.refetch()}
        />
      )}
      {engagement.data && candidates.data && (
        <Chooser
          engagementId={engagementId}
          here={{ id: engagementId, name: engagement.data.name, country: engagement.data.country ?? "" }}
          candidates={candidates.data}
          onOpen={(id) => setParams({ comparison: id })}
        />
      )}
      {existing.data && existing.data.length > 0 && (
        <Card title="Comparisons of this map">
          <ul className="compare-list">
            {existing.data.map((c) => (
              <li key={c.id}>
                <span>
                  {c.reference.country} {c.reference.version_label} (reference) and {c.other.country}{" "}
                  {c.other.version_label}: {c.differences.open} not classed yet, {c.differences.classed} classed,{" "}
                  {c.differences.kept} kept
                </span>{" "}
                <Button onClick={() => setParams({ comparison: c.id })}>
                  Open <span className="visually-hidden">the comparison with {c.reference.country}</span>
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {comparisonId && <ComparisonPanel id={comparisonId} />}
    </main>
  );
}

function Chooser({
  engagementId,
  here,
  candidates,
  onOpen,
}: {
  engagementId: string;
  here: { id: string; name: string; country: string };
  candidates: { engagement_id: string; name: string; country: string; why: string; published_label: string | null }[];
  onOpen: (id: string) => void;
}) {
  const start = useStartComparison(engagementId);
  const published = candidates.filter((c) => c.published_label);
  const [reference, setReference] = useState(published[0]?.engagement_id ?? "");
  const [thisIsOther, setThisIsOther] = useState(true);
  if (candidates.length === 0) {
    return (
      <EmptyState
        message="No other country maps this process yet. Start one from Setup with Map this process in another country, or from the other country's Capability Compass hand-off. Maps of different processes are never compared."
        action={<Link to={engagementPath(engagementId, "setup")}>Go to Setup</Link>}
      />
    );
  }
  const unpublished = candidates.filter((c) => !c.published_label);
  const label = (c: { name: string; country: string }) => (c.country ? `${c.country} · ${c.name}` : c.name);
  const chosen = published.find((c) => c.engagement_id === reference);
  return (
    <Card title="Choose the two maps" description="Only published versions are compared; the latest of each is used.">
      {published.length > 0 ? (
        <form
          className="setup-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (!chosen || start.isPending) return;
            const body = thisIsOther
              ? { reference_engagement_id: chosen.engagement_id, other_engagement_id: here.id }
              : { reference_engagement_id: here.id, other_engagement_id: chosen.engagement_id };
            start.mutate(body, { onSuccess: (view) => onOpen(view.id) });
          }}
        >
          <SelectField
            label="Compare with"
            value={reference}
            options={published.map((c) => ({ value: c.engagement_id, label: `${label(c)} (${c.why})` }))}
            onChange={setReference}
          />
          <SelectField
            label="Reference country"
            value={thisIsOther ? "them" : "us"}
            options={[
              { value: "them", label: chosen ? label(chosen) : "The other map" },
              { value: "us", label: label(here) },
            ]}
            onChange={(v) => setThisIsOther(v === "them")}
            help="The map the other country is compared with. Differences are reported back by the other country."
          />
          {start.isError && (
            <p className="field__error" role="alert">
              {messageOf(start.error)}
            </p>
          )}
          <div>
            <Button variant="primary" type="submit">
              {start.isPending ? "Comparing…" : "Compare"}
            </Button>
          </div>
        </form>
      ) : (
        <p className="field__help">None of the maps of this process in another country is published yet.</p>
      )}
      {unpublished.length > 0 && (
        <p className="field__help">
          Not published yet, so not offered: {unpublished.map(label).join("; ")}. Drafts are never compared.
        </p>
      )}
    </Card>
  );
}

function ComparisonPanel({ id }: { id: string }) {
  const comparison = useComparison(id);
  const refresh = useRefreshComparison(id);
  if (comparison.isPending) return <Skeleton height="240px" />;
  if (comparison.isError) {
    return (
      <ErrorState
        title="The comparison couldn't be loaded"
        message={messageOf(comparison.error)}
        onRetry={() => void comparison.refetch()}
      />
    );
  }
  const c = comparison.data;
  const newer = [c.reference, c.other].filter((s) => s.newer_version_label);
  return (
    <>
      <Card
        title={`${c.reference.country} and ${c.other.country}`}
        description={`${c.reference.country} ${c.reference.version_label} is the reference; ${c.other.country} ${c.other.version_label} is compared with it (${c.same_process}).`}
      >
        {newer.length > 0 && (
          <div className="compare-note" role="note">
            <p>
              A newer version exists:{" "}
              {newer.map((s) => `${s.country} ${s.newer_version_label}`).join(" and ")}. Refresh to compare it; your
              pairs and classes are kept.
            </p>
            <Button onClick={() => refresh.mutate(undefined)}>{refresh.isPending ? "Refreshing…" : "Refresh"}</Button>
          </div>
        )}
        <p className="compare-counts">
          <span className="mono">{c.counts.open}</span> not classed yet · <span className="mono">{c.counts.classed}</span>{" "}
          classed · <span className="mono">{c.counts.kept}</span> kept ·{" "}
          <span className="mono">{c.counts.dismissed}</span> dismissed
        </p>
        <p className="compare-downloads">
          <a className="btn btn--secondary" href={comparisonExportUrl(c.id, "a3")} download>
            Download printable pages (A3)
          </a>{" "}
          <a className="btn btn--secondary" href={comparisonExportUrl(c.id, "slide")} download>
            Download printable pages (16:9)
          </a>
        </p>
      </Card>
      <PairsCard comparison={c} />
      <DifferencesCard comparison={c} />
    </>
  );
}

/**
 * A step with its code and the country that numbered it ("Arden S-05 Legal review of terms"): each
 * country numbers its own steps, so the same code can name different steps (Eric, 2026-11-13).
 */
function stepName(s: ComparedStep | undefined, country: string): string {
  if (!s) return "";
  return s.code ? `${country} ${s.code} ${s.label}` : `${country}: ${s.label}`;
}

function PairsCard({ comparison: c }: { comparison: Comparison }) {
  const setPair = useSetPair(c.id);
  const suggest = useSuggestPairs(c.id);
  const ref = new Map(c.steps.reference.map((s) => [s.key, s]));
  const other = new Map(c.steps.other.map((s) => [s.key, s]));
  const used = new Set(c.pairs.flatMap((p) => [p.reference_key, p.other_key]).filter(Boolean) as string[]);
  const loneRef = c.steps.reference.filter((s) => !used.has(s.key));
  const loneOther = c.steps.other.filter((s) => !used.has(s.key));
  const R = c.reference.country;
  const O = c.other.country;
  const send = (reference_key: string | null, other_key: string | null, decision: "confirmed" | "only_reference" | "only_other" | "clear") =>
    setPair.mutate({ reference_key, other_key, decision });
  return (
    <Card
      title="Step pairs"
      description="Proposed by fixed rules, each with its reason. Confirm the pairs that are the same work, choose another step, or mark a step as only in one country."
    >
      <div>
        <Button onClick={suggest.start}>{suggest.running ? "Claude is suggesting…" : "Ask Claude to suggest pairs"}</Button>
        <p className="field__help">Claude may only pair steps already on the two maps, and nothing is applied until you confirm.</p>
        {suggest.outcome && (
          <p className={suggest.outcome.failed ? "field__error" : "field__help"} role="status">
            {suggest.outcome.message}
          </p>
        )}
        {suggest.error && (
          <p className="field__error" role="alert">
            {messageOf(suggest.error)}
          </p>
        )}
      </div>
      {setPair.isError && (
        <p className="field__error" role="alert">
          {messageOf(setPair.error)}
        </p>
      )}
      <table className="compare-table">
        <caption className="visually-hidden">Step pairs between {R} and {O}</caption>
        <thead>
          <tr>
            <th scope="col">{R}</th>
            <th scope="col">{O}</th>
            <th scope="col">Status</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {c.pairs.map((p) => {
            const r = p.reference_key ? ref.get(p.reference_key) : undefined;
            const o = p.other_key ? other.get(p.other_key) : undefined;
            const name = r ? stepName(r, R) : stepName(o, O);
            const open = p.status === "proposed" || p.status === "suggested";
            return (
              <tr key={`${p.reference_key ?? ""}|${p.other_key ?? ""}`}>
                <td>{r ? stepName(r, R) : <span className="compare-none">Not in {R}</span>}</td>
                <td>{o ? stepName(o, O) : <span className="compare-none">Not in {O}</span>}</td>
                <td>
                  <Chip dashed={p.status === "proposed" || p.status === "suggested"}>{PAIR_LABELS[p.status]}</Chip>
                  {p.why && <span className="compare-why">{p.why}</span>}
                </td>
                <td className="compare-actions">
                  {open && (
                    <Button onClick={() => send(p.reference_key, p.other_key, "confirmed")}>
                      Confirm <span className="visually-hidden">the pair for {name}</span>
                    </Button>
                  )}
                  {/* Once decided, only Clear and Choose another step (Eric, 2026-11-13). */}
                  {open && r && (
                    <Button onClick={() => send(r.key, null, "only_reference")}>
                      Only in {R} <span className="visually-hidden">: {stepName(r, R)}</span>
                    </Button>
                  )}
                  {open && o && (
                    <Button onClick={() => send(null, o.key, "only_other")}>
                      Only in {O} <span className="visually-hidden">: {stepName(o, O)}</span>
                    </Button>
                  )}
                  {!open && (
                    <Button variant="link" onClick={() => send(p.reference_key, p.other_key, "clear")}>
                      Clear <span className="visually-hidden">the decision for {name}</span>
                    </Button>
                  )}
                  {r && (
                    <ChooseAnother
                      label={`Pair ${stepName(r, R)} with`}
                      steps={c.steps.other}
                      country={O}
                      onChoose={(key) => send(r.key, key, "confirmed")}
                    />
                  )}
                </td>
              </tr>
            );
          })}
          {loneRef.map((s) => (
            <tr key={`r-${s.key}`}>
              <td>{stepName(s, R)}</td>
              <td>
                <span className="compare-none">Not paired</span>
              </td>
              <td>
                <Chip dashed>Undecided</Chip>
              </td>
              <td className="compare-actions">
                <Button onClick={() => send(s.key, null, "only_reference")}>
                  Only in {R} <span className="visually-hidden">: {stepName(s, R)}</span>
                </Button>
                <ChooseAnother
                  label={`Pair ${stepName(s, R)} with`}
                  steps={c.steps.other}
                  country={O}
                  onChoose={(key) => send(s.key, key, "confirmed")}
                />
              </td>
            </tr>
          ))}
          {loneOther.map((s) => (
            <tr key={`o-${s.key}`}>
              <td>
                <span className="compare-none">Not paired</span>
              </td>
              <td>{stepName(s, O)}</td>
              <td>
                <Chip dashed>Undecided</Chip>
              </td>
              <td className="compare-actions">
                <Button onClick={() => send(null, s.key, "only_other")}>
                  Only in {O} <span className="visually-hidden">: {stepName(s, O)}</span>
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function ChooseAnother({
  label,
  steps,
  country,
  onChoose,
}: {
  label: string;
  steps: ComparedStep[];
  country: string;
  onChoose: (key: string) => void;
}) {
  const [value, setValue] = useState("");
  return (
    <span className="compare-choose">
      <SelectField
        label={label}
        value={value}
        options={[{ value: "", label: "Choose another step…" }, ...steps.map((s) => ({ value: s.key, label: stepName(s, country) }))]}
        onChange={(key) => {
          setValue("");
          if (key) onChoose(key);
        }}
      />
    </span>
  );
}

function DifferencesCard({ comparison: c }: { comparison: Comparison }) {
  if (c.differences.length === 0 && c.no_longer_found.length === 0) {
    return (
      <Card title="Differences">
        <p className="field__help">
          No difference yet. Differences appear once you confirm a pair or mark a step as only in one country.
        </p>
      </Card>
    );
  }
  return (
    <Card
      title="Differences"
      description={`Each one line, with both values. A difference gets its code (V1, V2 …) when you class or keep it; it is sent back to Capability Compass by ${c.other.country}.`}
    >
      <ul className="difference-list">
        {c.differences.map((d) => (
          <DifferenceRow key={d.key} comparisonId={c.id} difference={d} />
        ))}
      </ul>
      {c.no_longer_found.length > 0 && (
        <>
          <h3 className="compare-subhead">No longer found</h3>
          <p className="field__help">Classed or kept before, but the current pairs no longer show them. They are not sent back.</p>
          <ul className="difference-list">
            {c.no_longer_found.map((d) => (
              <li key={d.key} className="difference">
                {d.code && <span className="mono">{d.code} </span>}
                {d.title}
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}

const REASONS: ReasonClass[] = ["required", "chosen", "inherited", "unknown"];

function DifferenceRow({ comparisonId, difference: d }: { comparisonId: string; difference: Difference }) {
  const decide = useDecideDifference(comparisonId);
  const [open, setOpen] = useState<"class" | "dismiss" | null>(null);
  const [reason, setReason] = useState<ReasonClass>(d.reason_class ?? "required");
  const [line, setLine] = useState(d.reason_note);
  const [note, setNote] = useState("");
  const act = (body: Parameters<typeof decide.mutate>[0]["body"]) =>
    decide.mutate({ key: d.key, body }, { onSuccess: () => setOpen(null) });
  const grade = (chosen: GradeKey | null) =>
    act({ action: d.status === "classed" ? "class" : "keep", grade: chosen, ...(d.reason_class ? { reason_class: d.reason_class, reason_note: d.reason_note } : {}) });
  return (
    <li className={`difference difference--${d.status}`}>
      <p className="difference__title">
        {d.code && <span className="mono">{d.code} </span>}
        {d.title}
      </p>
      <p className="difference__meta">
        {d.topic && <span>{TOPIC_LABELS[d.topic]}</span>}
        {d.figure && <span>{d.figure}</span>}
        <span>{STATUS_LABELS[d.status]}</span>
        {d.reason_class && (
          <span>
            Reason: {REASON_LABELS[d.reason_class]}
            {d.reason_note ? ` (${d.reason_note})` : ""}
          </span>
        )}
        {d.note && <span>Note: {d.note}</span>}
      </p>
      <span className="difference__grade">
        <GradeControl
          grade={d.grade}
          subject={d.code ?? d.title}
          onChange={d.status === "classed" || d.status === "kept" ? grade : undefined}
        />
        <span className="field__help">{d.grade_reason}</span>
      </span>
      {decide.isError && (
        <p className="field__error" role="alert">
          {messageOf(decide.error)}
        </p>
      )}
      {open === null && (
        <span className="compare-actions">
          {d.status !== "dismissed" && (
            <Button onClick={() => setOpen("class")}>
              {d.status === "classed" ? "Change the reason" : "Class"} <span className="visually-hidden">{d.title}</span>
            </Button>
          )}
          {d.status === "open" && (
            <Button onClick={() => act({ action: "keep" })}>
              Keep without a reason <span className="visually-hidden">{d.title}</span>
            </Button>
          )}
          {d.status !== "dismissed" && (
            <Button variant="link" onClick={() => setOpen("dismiss")}>
              Not a real difference <span className="visually-hidden">{d.title}</span>
            </Button>
          )}
          {d.status === "dismissed" && (
            <Button onClick={() => act({ action: "reopen" })}>
              Reopen <span className="visually-hidden">{d.title}</span>
            </Button>
          )}
        </span>
      )}
      {open === "class" && (
        <form
          className="compare-form"
          onSubmit={(e) => {
            e.preventDefault();
            act({ action: "class", reason_class: reason, reason_note: line });
          }}
        >
          <fieldset className="role-picks">
            <legend>Why do the two countries differ here?</legend>
            {REASONS.map((r) => (
              <label key={r} className="radio-row">
                <input type="radio" name={`reason-${d.key}`} checked={reason === r} onChange={() => setReason(r)} />
                {REASON_LABELS[r]}: {REASON_HELP[r]}
              </label>
            ))}
          </fieldset>
          <TextField label="One line of reason" value={line} onChange={setLine} help="Name roles, never people." />
          <span className="compare-actions">
            <Button variant="primary" type="submit">
              Save the reason
            </Button>
            <Button onClick={() => setOpen(null)}>Cancel</Button>
          </span>
        </form>
      )}
      {open === "dismiss" && (
        <form
          className="compare-form"
          onSubmit={(e) => {
            e.preventDefault();
            act({ action: "dismiss", note });
          }}
        >
          <TextField label="Why isn't this a real difference?" value={note} onChange={setNote} />
          <span className="compare-actions">
            <Button variant="primary" type="submit">
              Dismiss
            </Button>
            <Button onClick={() => setOpen(null)}>Cancel</Button>
          </span>
        </form>
      )}
    </li>
  );
}
