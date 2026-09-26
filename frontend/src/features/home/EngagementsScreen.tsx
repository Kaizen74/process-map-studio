import { useState } from "react";
import { Button, Card, EmptyState, ErrorState, Skeleton } from "../../components/common";
import { useSettings } from "../../hooks/useSettings";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { FirstRunChecklist, type ChecklistStep } from "./FirstRunChecklist";

const NOT_YET = "Creating engagements arrives in the next build phase (P1).";

/** Home: engagements and the first-run checklist (PRD §5.4). Engagements arrive in phase P1. */
export function EngagementsScreen() {
  const settings = useSettings();
  const [explain, setExplain] = useState(false);

  const steps: ChecklistStep[] = [
    {
      title: "Add your Claude API key",
      detail: settings.data?.key_set
        ? `Key saved (ending ${settings.data.key_last4 || "…"}). Test it in Settings any time.`
        : "Paste the key from the Claude Console so the app can draft maps.",
      done: settings.data?.key_set ?? false,
      to: "/settings",
      linkLabel: settings.data?.key_set ? "Open Settings" : "Add your Claude API key",
    },
    {
      title: "Create an engagement",
      detail: "One engagement per process: its scope, roles and lanes. Available from build phase P1.",
      done: false,
    },
    {
      title: "Upload sources",
      detail: "The interview transcript, SOPs and job descriptions. Available from build phase P1.",
      done: false,
    },
  ];

  return (
    <main className="screen" aria-labelledby="home-title">
      <div className="screen__header">
        <div>
          <h1 id="home-title">Engagements</h1>
          <p className="screen__intro">Each engagement maps one process from its sources.</p>
        </div>
        <Button variant="primary" onClick={() => setExplain(true)}>
          New engagement
        </Button>
      </div>

      {settings.isPending && (
        <Card title="Get started">
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
      {settings.isSuccess && <FirstRunChecklist steps={steps} />}

      <EmptyState
        message="No engagements yet. An engagement holds one process: its sources, draft map and published versions."
        action={
          <div className="stack">
            <Button variant="primary" onClick={() => setExplain(true)}>
              New engagement
            </Button>
            {explain && (
              <p className="inline-note" role="status">
                {NOT_YET}
              </p>
            )}
          </div>
        }
      />
    </main>
  );
}
