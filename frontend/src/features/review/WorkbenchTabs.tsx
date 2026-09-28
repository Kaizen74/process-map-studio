import { useState, type ReactNode } from "react";
import { ErrorState, Skeleton } from "../../components/common";
import { useToast } from "../../components/shell";
import {
  AuditTab,
  LintTab,
  MergeTab,
  QuestionsTab,
  RaciMatrix,
  RejectedClaimsTab,
  TabBar,
} from "../../components/tabs";
import { useRejectedClaims } from "../../hooks/useDraft";
import {
  useAudit,
  useDecideMerge,
  useLint,
  useMergeProposals,
  useQuestions,
  useSetQuestionStatus,
} from "../../hooks/useReview";
import { saveText } from "../../lib/download";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import type { Graph } from "../../lib/mapTypes";
import { questionsFileName, questionsMarkdown } from "../../lib/questions";
import type { RejectedClaim } from "../../lib/reviewTypes";

type TabId = "raci" | "questions" | "rejected" | "audit" | "merges" | "lint";

export interface WorkbenchTabsProps {
  graph: Graph;
  versionId: string;
  engagementId: string;
  laneOrder: readonly string[];
  selectedId: string | null;
  editable: boolean;
  onSelect: (elementId: string) => void;
  onOpenPassage: (claim: RejectedClaim) => void;
  onAddFromPassage: (claim: RejectedClaim) => void;
}

/** Loading and error states shared by every tab (PRD §5.3). */
function Loaded<T>({
  query,
  what,
  children,
}: {
  query: { data: T | undefined; isError: boolean; error: unknown; refetch: () => unknown };
  what: string;
  children: (data: T) => ReactNode;
}) {
  if (query.isError) {
    return (
      <ErrorState
        title={`The ${what} couldn't be loaded`}
        message={messageOf(query.error)}
        details={copyDetailsOf(query.error)}
        onRetry={() => void query.refetch()}
      />
    );
  }
  if (query.data === undefined) return <Skeleton height="120px" />;
  return <>{children(query.data)}</>;
}

/** The workbench tabs under the map (PRD §5.7.10). */
export function WorkbenchTabs({
  graph,
  versionId,
  engagementId,
  laneOrder,
  selectedId,
  editable,
  onSelect,
  onOpenPassage,
  onAddFromPassage,
}: WorkbenchTabsProps) {
  const [tab, setTab] = useState<TabId>("raci");
  const toast = useToast();
  const questions = useQuestions(versionId);
  const rejected = useRejectedClaims(versionId);
  const audit = useAudit(versionId);
  const merges = useMergeProposals(versionId);
  const lint = useLint(versionId);
  const setStatus = useSetQuestionStatus(versionId, engagementId);
  const decide = useDecideMerge(versionId, engagementId);

  const open = questions.data?.filter((q) => q.status === "open").length;
  const waiting = merges.data?.filter((m) => m.decision === "pending").length;
  const checks = lint.data ? lint.data.failures.length + lint.data.warnings.length : undefined;
  const count = (label: string, n: number | undefined, suffix = "") =>
    n === undefined ? label : `${label} (${n}${suffix})`;
  const tabs: { id: TabId; label: string }[] = [
    { id: "raci", label: "RACI matrix" },
    { id: "questions", label: count("Validation questions", open, " open") },
    { id: "rejected", label: count("Rejected claims", rejected.data?.total) },
    { id: "audit", label: "Audit log" },
    // A published version hides Merge and Map checks (PRD §5.9): nothing there can change.
    ...(editable
      ? [
          { id: "merges" as const, label: count("Merge decisions", waiting, " waiting") },
          { id: "lint" as const, label: count("Map checks", checks) },
        ]
      : []),
  ];
  const shown = tabs.some((t) => t.id === tab) ? tab : "raci";

  const markdown = () => questionsMarkdown(questions.data ?? [], graph.process.name, graph.version.label);

  async function copyAll() {
    try {
      await navigator.clipboard.writeText(markdown());
      toast("Questions copied. Paste them into your notes for the session.");
    } catch {
      toast("The questions couldn't be copied. Use Download .md instead.");
    }
  }

  return (
    <TabBar label="Review workbench" tabs={tabs} active={shown} onChange={setTab}>
      {shown === "raci" && <RaciMatrix graph={graph} laneOrder={laneOrder} selectedId={selectedId} onSelect={onSelect} />}
      {shown === "questions" && (
        <Loaded query={questions} what="questions">
          {(data) => (
            <>
              <QuestionsTab
                questions={data}
                onStatus={
                  editable ? (questionId, status) => setStatus.mutate({ questionId, status }) : undefined
                }
                onGoTo={onSelect}
                onCopy={() => void copyAll()}
                onDownload={() => saveText(questionsFileName(graph.version.label), markdown())}
              />
              {setStatus.error != null && (
                <p className="field__error" role="alert">
                  {messageOf(setStatus.error)}
                </p>
              )}
            </>
          )}
        </Loaded>
      )}
      {shown === "rejected" && (
        <Loaded query={rejected} what="rejected claims">
          {(data) => (
            <RejectedClaimsTab
              data={data}
              onOpenPassage={onOpenPassage}
              onAddStep={editable ? onAddFromPassage : undefined}
            />
          )}
        </Loaded>
      )}
      {shown === "audit" && <Loaded query={audit} what="audit log">{(data) => <AuditTab entries={data} />}</Loaded>}
      {shown === "merges" && (
        <Loaded query={merges} what="merge decisions">
          {(data) => (
            <>
              <MergeTab
                proposals={data}
                busyId={decide.isPending ? (decide.variables?.proposalId ?? null) : null}
                onDecide={
                  editable
                    ? (proposalId, decision) => {
                        decide.reset();
                        decide.mutate({ proposalId, decision });
                      }
                    : undefined
                }
                onGoTo={onSelect}
              />
              {decide.error != null && (
                <p className="field__error" role="alert">
                  {messageOf(decide.error)}
                </p>
              )}
            </>
          )}
        </Loaded>
      )}
      {shown === "lint" && <Loaded query={lint} what="map checks">{(data) => <LintTab report={data} onGoTo={onSelect} />}</Loaded>}
    </TabBar>
  );
}
