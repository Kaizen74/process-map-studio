import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { Button, Card, EmptyState, ErrorState, SelectField, Skeleton } from "../../components/common";
import { PublishedBanner, useToast } from "../../components/shell";
import { useEngagement } from "../../hooks/useEngagements";
import { useReopen, useVersion, useVersions } from "../../hooks/useVersions";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { formatDate } from "../../lib/format";
import type { ChangeEntry, VersionSummary } from "../../lib/reviewTypes";
import { EngagementProblem } from "../engagement/EngagementProblem";
import { Workbench } from "../review/Workbench";
import "../review/review.css";
import "./published.css";

const CHANGE_WORDS: Readonly<Record<string, string>> = {
  confirmed: "Confirmed",
  edited: "Edited",
  rejected: "Rejected",
  added: "Added",
};

function ChangeLog({ versionId }: { versionId: string }) {
  const version = useVersion(versionId);
  if (version.isError) {
    return (
      <ErrorState
        title="The change log couldn't be loaded"
        message={messageOf(version.error)}
        details={copyDetailsOf(version.error)}
        onRetry={() => void version.refetch()}
      />
    );
  }
  if (!version.data) return <Skeleton height="80px" />;
  const log: ChangeEntry[] = version.data.change_log;
  if (log.length === 0) return <p className="tab-empty">No steps were changed while this version was the draft.</p>;
  return (
    <ul className="change-log">
      {log.map((entry) => (
        <li key={entry.stable_key}>
          <span className={`change-log__change change-log__change--${entry.change}`}>
            {CHANGE_WORDS[entry.change] ?? entry.change}
          </span>
          <span>{entry.step}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Published (PRD §5.4, §5.9): a published version in the workbench, read-only, with a version
 * picker (superseded versions labelled), its change log and Reopen as new draft.
 */
export function PublishedScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const versions = useVersions(engagementId);
  const reopen = useReopen(engagementId);
  const [params, setParams] = useSearchParams();
  const toast = useToast();
  const navigate = useNavigate();

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }
  if (versions.isError) {
    return (
      <main className="screen" aria-labelledby="published-title">
        <h1 id="published-title">Published</h1>
        <ErrorState
          title="The published versions couldn't be loaded"
          message={messageOf(versions.error)}
          details={copyDetailsOf(versions.error)}
          onRetry={() => void versions.refetch()}
        />
      </main>
    );
  }
  if (!versions.data) {
    return (
      <main className="screen" aria-labelledby="published-title" aria-busy="true">
        <h1 id="published-title">Published</h1>
        <Skeleton height="48px" />
        <Skeleton height="420px" />
      </main>
    );
  }
  const published = versions.data.filter((v) => v.state === "published" || v.state === "superseded");
  if (published.length === 0) {
    return (
      <main className="screen" aria-labelledby="published-title">
        <h1 id="published-title">Published</h1>
        <EmptyState
          message="Nothing published yet. Review and publish from the Review screen."
          action={<Link to={engagementPath(engagementId, "review")}>Go to Review</Link>}
        />
      </main>
    );
  }
  const draft = versions.data.find((v) => v.state === "draft") ?? null;
  const chosen: VersionSummary =
    published.find((v) => v.id === params.get("version")) ??
    published.find((v) => v.state === "published") ??
    (published[0] as VersionSummary);

  function choose(id: string) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.set("version", id);
        next.delete("step");
        return next;
      },
      { replace: true },
    );
  }

  function reopenChosen() {
    reopen.reset();
    reopen.mutate(chosen.id, {
      onSuccess: (created) => {
        toast(`Reopened as ${created.label}. Every reviewed step stays locked.`);
        void navigate(engagementPath(engagementId, "review"));
      },
    });
  }

  const actions = (
    <>
      <SelectField
        label="Version"
        value={chosen.id}
        options={published.map((v) => ({
          value: v.id,
          label: `${v.label} · ${v.state === "superseded" ? "superseded" : "published"} ${formatDate(v.published_at ?? "")}`,
        }))}
        onChange={choose}
      />
      {chosen.state === "published" &&
        (draft ? (
          <Link to={engagementPath(engagementId, "review")}>Go to the draft ({draft.label})</Link>
        ) : (
          <Button variant="primary" onClick={reopenChosen}>
            {reopen.isPending ? "Reopening…" : "Reopen as new draft"}
          </Button>
        ))}
      {reopen.error != null && (
        <p className="field__error" role="alert">
          {messageOf(reopen.error)}
        </p>
      )}
    </>
  );

  return (
    <Workbench
      key={chosen.id}
      engagementId={engagementId}
      versionId={chosen.id}
      title="Published"
      banner={() => (
        <PublishedBanner
          label={chosen.label}
          state={chosen.state}
          publishedBy={chosen.published_by ?? ""}
          publishedOn={formatDate(chosen.published_at ?? "")}
          actions={actions}
        />
      )}
      below={
        <Card title="Changes in this version" description="What was confirmed, edited, rejected or added while it was the draft.">
          <ChangeLog versionId={chosen.id} />
        </Card>
      }
    />
  );
}
