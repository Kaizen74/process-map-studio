import { useState } from "react";
import { Link, useParams } from "react-router";
import type { DraftState, Job, Readiness } from "../../api/types";
import { Button, Card, Chip, ErrorState, Skeleton } from "../../components/common";
import { useDraft, useStartDraft } from "../../hooks/useDraft";
import { useEngagement, useReadiness } from "../../hooks/useEngagements";
import { draftChecklist, groupDigits } from "../../lib/draft";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { plural } from "../../lib/format";
import { EngagementProblem } from "../engagement/EngagementProblem";
import { RejectedClaimsList } from "./RejectedClaimsList";
import { StageStepper } from "./StageStepper";
import "./draft.css";

function Checklist({ engagementId, readiness }: { engagementId: string; readiness: Readiness }) {
  const items = draftChecklist(readiness);
  return (
    <Card
      title="Before drafting"
      description={`${items.filter((i) => i.done).length} of ${items.length} ready.`}
    >
      <ul className="draft-checklist">
        {items.map((item) => (
          <li key={item.key} className="draft-checklist__item">
            <span>{item.label}</span>
            <span className="draft-checklist__status">
              {!item.done && (
                <Link to={item.to === "settings" ? "/settings" : engagementPath(engagementId, "sources")}>
                  {item.action}
                </Link>
              )}
              {item.done ? <Chip tone="good">Done</Chip> : <Chip dashed>To do</Chip>}
            </span>
          </li>
        ))}
      </ul>
      {readiness.missing.length > 0 && (
        <div className="draft-missing">
          <p>
            <strong>Still needed:</strong>
          </p>
          <ul>
            {readiness.missing.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

function Counters({ job }: { job: Job }) {
  return (
    <dl className="draft-counters" aria-live="polite">
      <div>
        <dt>Claims verified</dt>
        <dd className="mono">{job.claims.verified}</dd>
      </div>
      <div>
        <dt>Rejected</dt>
        <dd className="mono">{job.claims.rejected}</dd>
      </div>
      <div>
        <dt>Tokens used so far</dt>
        <dd className="mono">
          {groupDigits((job.usage?.input_tokens ?? 0) + (job.usage?.output_tokens ?? 0))}
        </dd>
      </div>
    </dl>
  );
}

function Progress({ job }: { job: Job }) {
  const pct = Math.round(job.progress * 100);
  return (
    <div className="draft-progress">
      <p className="draft-progress__label" role="status">
        {job.status === "queued" ? "Waiting to start…" : `${job.stage || "Starting"}…`}
      </p>
      <div
        className="draft-progress__bar"
        role="progressbar"
        aria-label="Drafting progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
      >
        <span className="draft-progress__fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Summary({ state }: { state: DraftState }) {
  const { version, summary } = state;
  if (!version || !summary) return null;
  return (
    <Card title={`Draft ${version.label}`} description="What Claude found in your sources, after every check.">
      <dl className="draft-summary">
        <div>
          <dt>Claims verified</dt>
          <dd className="mono">{summary.verified}</dd>
        </div>
        <div>
          <dt>Rejected claims</dt>
          <dd className="mono">{summary.rejected}</dd>
        </div>
        <div>
          <dt>Open questions</dt>
          <dd className="mono">{summary.open_questions}</dd>
        </div>
      </dl>
      <p className="draft-note">
        Comparing sources and building the map arrive in build phase P4. Then the verified claims become
        steps you review here.
      </p>
    </Card>
  );
}

/** Draft (PRD §5.4): readiness checklist, Create draft map, stage stepper and live counters. */
export function DraftScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const readiness = useReadiness(engagementId);
  const draft = useDraft(engagementId);
  const start = useStartDraft(engagementId);
  const [startError, setStartError] = useState<unknown>(null);

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }

  const state = draft.data;
  const job = state?.job ?? null;
  const running = job?.status === "queued" || job?.status === "running";
  const failed = job?.status === "failed";
  const hasDraft = Boolean(state?.version);

  function create() {
    setStartError(null);
    start.mutate(undefined, { onError: setStartError });
  }

  return (
    <main className="screen" aria-labelledby="draft-title">
      <div>
        <h1 id="draft-title">Draft</h1>
        <p className="screen__intro">
          Claude reads every source and drafts the claims the map is built from. Every quote, number and role is
          checked against your documents; anything that fails is set aside and never reaches the map.
        </p>
      </div>

      {(draft.isPending || readiness.isPending) && (
        <div className="stack" aria-busy="true">
          <Skeleton height="120px" />
          <Skeleton height="48px" />
        </div>
      )}
      {draft.isError && (
        <ErrorState
          title="The draft couldn't be loaded"
          message={messageOf(draft.error)}
          details={copyDetailsOf(draft.error)}
          onRetry={() => void draft.refetch()}
        />
      )}

      {!running && readiness.data && <Checklist engagementId={engagementId} readiness={readiness.data} />}

      {!running && !failed && draft.isSuccess && (
        <div className="draft-start">
          <Button variant="primary" onClick={create}>
            {start.isPending ? "Starting…" : hasDraft ? "Draft again from sources" : "Create draft map"}
          </Button>
          <p className="draft-note">
            {hasDraft
              ? "Replaces this draft. Nothing has been reviewed yet, so nothing you've done is lost."
              : "Takes a few minutes. You can leave this screen; drafting carries on."}
          </p>
        </div>
      )}
      {startError !== null && (
        <p className="field__error" role="alert">
          {messageOf(startError)}
        </p>
      )}

      {job && (running || failed) && (
        <Card title={running ? "Drafting" : "Drafting stopped"}>
          <div className="stack">
            {running && <Progress job={job} />}
            <StageStepper stages={job.stages} />
            <Counters job={job} />
          </div>
        </Card>
      )}
      {job && failed && (
        <ErrorState
          title="The draft couldn't be finished"
          message={job.error}
          details={`draft job · ${job.id}`}
          onRetry={create}
        />
      )}

      {!running && state && <Summary state={state} />}
      {!running && state?.version && (
        <RejectedClaimsList engagementId={engagementId} versionId={state.version.id} />
      )}
      {!running && state?.summary && state.summary.scrubbed > 0 && (
        <p className="draft-note">
          {plural(state.summary.scrubbed, "name")} in Claude's answers {state.summary.scrubbed === 1 ? "was" : "were"}{" "}
          replaced by roles.
        </p>
      )}
    </main>
  );
}
