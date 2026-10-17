import { useState } from "react";
import { Link } from "react-router";
import { Button, Card, EmptyState, ErrorState, Skeleton } from "../../components/common";
import { useToast } from "../../components/shell";
import { LogAlignmentTable } from "../../components/system";
import { useGraph } from "../../hooks/useReview";
import { useAlignment, useSaveAlignment, useSuggestAlignment, useSuggestJob } from "../../hooks/useSystemRecords";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import type { AlignmentDecision, EventLog } from "../../lib/systemRecords";

const NOT_STEPS = new Set(["start", "end"]);

/** Claude's pass for the activities the app couldn't match (PRD §3.13.4; `SR_align`). */
function AskClaude({ logId, waiting }: { logId: string; waiting: number }) {
  const start = useSuggestAlignment(logId);
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useSuggestJob(logId, jobId);
  const running = jobId !== null && job.data?.status !== "done" && job.data?.status !== "failed";
  return (
    <Card
      title="Ask Claude"
      description="For activities the app couldn't match, Claude suggests a step. It sees only the activity names with their volumes and most frequent role, and your map's steps: no events, case IDs or user IDs. About 1 AI call."
    >
      <div className="system-ask">
        <div>
          <Button
            onClick={() =>
              start.mutate(undefined, { onSuccess: (started) => setJobId(started.job_id) })
            }
            aria-busy={start.isPending || running || undefined}
          >
            {running ? "Asking Claude…" : "Ask Claude for suggestions"}
          </Button>
        </div>
        {waiting === 0 && !jobId && <p className="system-ask__note">Every row has a decision; Claude only looks at undecided activities.</p>}
        {job.data?.status === "done" && (
          <p role="status">{job.data.message} Suggestions are proposals: confirm or change each one.</p>
        )}
        {job.data?.status === "failed" && (
          <p className="danger-note" role="alert">
            {job.data.error || "Claude's suggestions couldn't be made."}
          </p>
        )}
        {start.isError && (
          <p className="danger-note" role="alert">
            {messageOf(start.error)}
          </p>
        )}
      </div>
    </Card>
  );
}

/** The alignment tab of an imported log: Eric matches each system activity to a map step. */
export function LogMatching({ engagementId, log }: { engagementId: string; log: EventLog }) {
  const alignment = useAlignment(log.id);
  const graph = useGraph(alignment.data?.version_id ?? null);
  const save = useSaveAlignment(log.id);
  const toast = useToast();

  if (alignment.isPending) return <Skeleton height="160px" />;
  if (alignment.isError) {
    const noMap = (alignment.error as { code?: string }).code === "NO_MAP";
    return noMap ? (
      <EmptyState
        message={messageOf(alignment.error)}
        action={<Link to={engagementPath(engagementId, "draft")}>Go to Draft</Link>}
      />
    ) : (
      <ErrorState
        title="The matching couldn't be loaded"
        message={messageOf(alignment.error)}
        details={copyDetailsOf(alignment.error)}
        onRetry={() => void alignment.refetch()}
      />
    );
  }

  const steps = (graph.data?.elements ?? [])
    .filter((e) => !NOT_STEPS.has(e.kind) && e.review_status !== "rejected")
    .map((e) => ({ id: e.id, label: e.label }));
  const decide = (decision: AlignmentDecision) =>
    save.mutate([decision], { onSuccess: () => toast("Decision saved. The map uses confirmed matches only.") });

  return (
    <div className="system-matching">
      <p className="system-matching__intro">
        Match each activity the system records to the step on your map that it belongs to. Nothing changes the map until
        you confirm it; confirmed matches show the order the system records and support the steps it records.
      </p>
      {save.isError && (
        <p className="danger-note" role="alert">
          {messageOf(save.error)}
        </p>
      )}
      <LogAlignmentTable alignment={alignment.data} steps={steps} onDecide={decide} />
      <AskClaude logId={log.id} waiting={alignment.data.summary.waiting} />
    </div>
  );
}
