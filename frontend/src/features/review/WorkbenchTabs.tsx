import { useEffect, useRef, useState, type ReactNode } from "react";
import { ErrorState, Skeleton } from "../../components/common";
import { useToast } from "../../components/shell";
import {
  AuditTab,
  LintTab,
  MergeTab,
  OutsideFlowTab,
  QuestionsTab,
  RaciMatrix,
  RejectedClaimsTab,
  TabBar,
  VariantsTab,
} from "../../components/tabs";
import { useOutsideFlow, useRejectedClaims } from "../../hooks/useDraft";
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
import { questionsFileName, questionsMarkdown, validationPackUrl } from "../../lib/questions";
import type { PassageClaim } from "../../lib/reviewTypes";
import type { HiddenWorkItem, LogVariants, SystemVariants } from "../../lib/systemRecords";

type TabId = "raci" | "questions" | "rejected" | "outside" | "audit" | "merges" | "lint" | "variants";

export interface WorkbenchTabsProps {
  graph: Graph;
  versionId: string;
  engagementId: string;
  laneOrder: readonly string[];
  selectedId: string | null;
  editable: boolean;
  onSelect: (elementId: string) => void;
  onOpenPassage: (claim: PassageClaim) => void;
  onAddFromPassage: (claim: PassageClaim) => void;
  /** System records (R8): the Variants tab, shown when a log is imported and the module is on. */
  variants?: SystemVariants | undefined;
  /** Add as step from hidden work; omitted where the version can't change. */
  onAddHidden?: ((item: HiddenWorkItem, log: LogVariants) => void) | undefined;
  /** The tab the address asks for (`?tab=outside` from the Draft screen, DECISIONS 85). */
  initialTab?: string | null | undefined;
}

const TAB_IDS: readonly TabId[] = ["raci", "questions", "rejected", "outside", "audit", "merges", "lint", "variants"];

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
  variants,
  onAddHidden,
  initialTab,
}: WorkbenchTabsProps) {
  const asked = TAB_IDS.find((id) => id === initialTab);
  const [tab, setTab] = useState<TabId>(asked ?? "raci");
  const toast = useToast();
  const questions = useQuestions(versionId);
  const rejected = useRejectedClaims(versionId);
  const outside = useOutsideFlow(versionId);
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
    // DECISIONS 81: shown only when drafting set claims about another flow aside.
    ...(outside.data && outside.data.total > 0
      ? [{ id: "outside" as const, label: count("Outside this flow", outside.data.total) }]
      : []),
    { id: "audit", label: "Audit log" },
    // A published version hides Merge and Map checks (PRD §5.9): nothing there can change.
    ...(editable
      ? [
          { id: "merges" as const, label: count("Merge decisions", waiting, " waiting") },
          { id: "lint" as const, label: count("Map checks", checks) },
        ]
      : []),
    ...(variants && variants.logs.length > 0 ? [{ id: "variants" as const, label: "Variants" }] : []),
  ];
  const shown = tabs.some((t) => t.id === tab) ? tab : "raci";
  // Arriving for a tab (from the Draft screen): bring it into view once it is there.
  const box = useRef<HTMLDivElement>(null);
  const arrived = useRef(false);
  useEffect(() => {
    if (asked && shown === asked && !arrived.current) {
      arrived.current = true;
      box.current?.scrollIntoView?.({ block: "start" });
    }
  }, [asked, shown]);

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
    <div ref={box}>
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
                  packUrl={validationPackUrl(graph.version.id)}
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
        {shown === "outside" && (
          <Loaded query={outside} what="claims about other flows">
            {(data) => (
              <OutsideFlowTab data={data} onOpenPassage={onOpenPassage} onAddStep={editable ? onAddFromPassage : undefined} />
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
        {shown === "variants" && variants && (
          <VariantsTab data={variants} onSelect={onSelect} onAddHidden={editable ? onAddHidden : undefined} />
        )}
      </TabBar>
    </div>
  );
}
