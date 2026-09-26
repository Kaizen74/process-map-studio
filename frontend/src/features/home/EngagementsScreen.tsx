import { useState } from "react";
import type { EngagementSummary } from "../../api/types";
import { Button, Card, EmptyState, ErrorState, Skeleton } from "../../components/common";
import { useEngagements } from "../../hooks/useEngagements";
import { useSettings } from "../../hooks/useSettings";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { DeleteEngagementDialog } from "./DeleteEngagementDialog";
import { EngagementCard } from "./EngagementCard";
import { FirstRunChecklist, type ChecklistStep } from "./FirstRunChecklist";
import { NewEngagementDialog } from "./NewEngagementDialog";
import "./home.css";

/** Home: engagement cards and, on first run, the three-step checklist (PRD §5.4). */
export function EngagementsScreen() {
  const settings = useSettings();
  const engagements = useEngagements();
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<EngagementSummary | null>(null);

  const list = engagements.data ?? [];
  const keySet = settings.data?.key_set ?? false;
  const withSources = list.find((e) => e.sources_count > 0);
  const firstRun = settings.isSuccess && engagements.isSuccess && (!keySet || list.length === 0);

  const steps: ChecklistStep[] = [
    {
      title: "Add your Claude API key",
      detail: keySet
        ? `Key saved (ending ${settings.data?.key_last4 || "…"}). Test it in Settings any time.`
        : "Paste the key from the Claude Console so the app can draft maps.",
      done: keySet,
      to: "/settings",
      linkLabel: keySet ? "Open Settings" : "Add your Claude API key",
    },
    {
      title: "Create an engagement",
      detail: "One engagement per process: its scope, roles and lanes.",
      done: list.length > 0,
    },
    {
      title: "Upload sources",
      detail: "The interview transcript, SOPs and job descriptions.",
      done: withSources !== undefined,
      ...(list[0] && !withSources
        ? { to: engagementPath(list[0].id, "sources"), linkLabel: "Upload sources" }
        : {}),
    },
  ];

  const newButton = (
    <Button variant="primary" onClick={() => setCreating(true)}>
      New engagement
    </Button>
  );
  const loading = settings.isPending || engagements.isPending;

  return (
    <main className="screen" aria-labelledby="home-title">
      <div className="screen__header">
        <div>
          <h1 id="home-title">Engagements</h1>
          <p className="screen__intro">Each engagement maps one process from its sources.</p>
        </div>
        {list.length > 0 && newButton}
      </div>

      {loading && (
        <Card title="Loading your engagements">
          <div className="stack" aria-busy="true">
            <Skeleton height="16px" width="60%" />
            <Skeleton height="16px" width="70%" />
            <Skeleton height="16px" width="50%" />
          </div>
        </Card>
      )}
      {settings.isError && (
        <ErrorState
          title="Your settings couldn't be loaded"
          message={messageOf(settings.error)}
          details={copyDetailsOf(settings.error)}
          onRetry={() => void settings.refetch()}
        />
      )}
      {engagements.isError && (
        <ErrorState
          title="Your engagements couldn't be loaded"
          message={messageOf(engagements.error)}
          details={copyDetailsOf(engagements.error)}
          onRetry={() => void engagements.refetch()}
        />
      )}
      {firstRun && <FirstRunChecklist steps={steps} />}

      {engagements.isSuccess && list.length === 0 && (
        <EmptyState
          message="No engagements yet. An engagement holds one process: its sources, draft map and published versions."
          action={newButton}
        />
      )}
      {list.length > 0 && (
        <ul className="engagement-grid" aria-label="Your engagements">
          {list.map((engagement) => (
            <li key={engagement.id}>
              <EngagementCard engagement={engagement} onDelete={setDeleting} />
            </li>
          ))}
        </ul>
      )}

      <NewEngagementDialog open={creating} onClose={() => setCreating(false)} />
      <DeleteEngagementDialog engagement={deleting} onClose={() => setDeleting(null)} />
    </main>
  );
}
