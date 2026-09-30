import { useState } from "react";
import type { EngagementSummary } from "../../api/types";
import { Button, Card, EmptyState, ErrorState, Skeleton } from "../../components/common";
import { TemplateList } from "../../components/interview";
import { useEngagements } from "../../hooks/useEngagements";
import { useSettings } from "../../hooks/useSettings";
import { useTemplatePlans } from "../../hooks/useTemplates";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { QUESTION_ID_TIP } from "../../lib/templates";
import { DeleteEngagementDialog } from "./DeleteEngagementDialog";
import { EngagementCard } from "./EngagementCard";
import { FirstRunChecklist, type ChecklistStep } from "./FirstRunChecklist";
import { NewEngagementDialog } from "./NewEngagementDialog";
import "./home.css";

/** The standard interview templates, available before any engagement exists (PRD v1.10 §5.4). */
function InterviewTemplatesCard() {
  const plans = useTemplatePlans();
  return (
    <Card
      title="Interview templates"
      description="The same questions, question IDs and minute plan for every interviewer. No engagement needed."
    >
      {plans.isPending && <Skeleton height="96px" />}
      {plans.isError && (
        <ErrorState
          title="The interview templates couldn't be loaded"
          message={messageOf(plans.error)}
          details={copyDetailsOf(plans.error)}
          onRetry={() => void plans.refetch()}
        />
      )}
      {plans.data && <TemplateList templates={plans.data} />}
      <p className="home-templates__tip">{QUESTION_ID_TIP}</p>
    </Card>
  );
}

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
      <InterviewTemplatesCard />

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
