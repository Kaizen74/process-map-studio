import type { GradeKey } from "../../lib/grade";
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import {
  Button,
  Dialog,
  EmptyState,
  ErrorState,
  SelectField,
  Skeleton,
} from "../../components/common";
import {
  BriefEditor,
  DismissForm,
  FindingCard,
  GapStepForm,
  RejectedFindings,
  SourceListItem,
  type DecisionAction,
} from "../../components/gap";
import { useToast } from "../../components/shell";
import {
  useDecideFinding,
  useSetFindingGrade,
  useFinaliseReport,
  useGapJob,
  useGapReport,
  useRunResearch,
  useUpdateBrief,
} from "../../hooks/useGap";
import { useGraph } from "../../hooks/useReview";
import { useRoles } from "../../hooks/useRoles";
import { useVersions } from "../../hooks/useVersions";
import { placesAfter } from "../../lib/addStep";
import { stepPath } from "../../lib/currentMap";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { plural } from "../../lib/format";
import {
  DISPOSITION_LABELS,
  MODE_LABELS,
  NO_FILTERS,
  SECTION_LABELS,
  SEVERITY_LABELS,
  STRENGTH_LABELS,
  bySection,
  exportUrl,
  filterFindings,
  isRunning,
  openItems,
  typeLabel,
  type Brief,
  type GapClass,
  type GapFilters,
  type GapFinding,
  type GapReport,
  type GapStepChoice,
} from "../../lib/gap";
import { StageStepper } from "../draft/StageStepper";

const DONE: Readonly<Record<DecisionAction, string>> = {
  added_question: "Added as a validation question in the draft.",
  added_cause: "Added to the cause library.",
  added_step: "Added as a step in the draft.",
  dismissed: "Finding dismissed.",
};

function Filters({
  report,
  filters,
  onChange,
}: {
  report: GapReport;
  filters: GapFilters;
  onChange: (f: GapFilters) => void;
}) {
  const types = [...new Set(report.findings.map((f) => f.finding_type))];
  const any = { value: "", label: "Any" };
  return (
    <div className="gap-filters" role="group" aria-label="Filter findings">
      <SelectField
        label="Type"
        value={filters.type}
        options={[
          any,
          ...types.map((t) => ({ value: t, label: typeLabel(t) })),
        ]}
        onChange={(type) => onChange({ ...filters, type })}
      />
      <SelectField
        label="Severity"
        value={filters.severity}
        options={[
          any,
          ...(["high", "medium", "low"] as const).map((s) => ({
            value: s,
            label: SEVERITY_LABELS[s],
          })),
        ]}
        onChange={(severity) =>
          onChange({ ...filters, severity: severity as GapFilters["severity"] })
        }
      />
      {report.analysis.mode === "external" && (
        <SelectField
          label="Evidence"
          value={filters.strength}
          options={[
            any,
            ...(["strong", "weak", "dated"] as const).map((s) => ({
              value: s,
              label: STRENGTH_LABELS[s],
            })),
          ]}
          onChange={(strength) =>
            onChange({
              ...filters,
              strength: strength as GapFilters["strength"],
            })
          }
        />
      )}
      <SelectField
        label="Decision"
        value={filters.disposition}
        options={[
          any,
          ...(
            Object.keys(
              DISPOSITION_LABELS,
            ) as (keyof typeof DISPOSITION_LABELS)[]
          ).map((d) => ({
            value: d,
            label: DISPOSITION_LABELS[d],
          })),
        ]}
        onChange={(disposition) =>
          onChange({
            ...filters,
            disposition: disposition as GapFilters["disposition"],
          })
        }
      />
    </div>
  );
}

export interface GapAnalysisViewProps {
  analysisId: string;
  engagementId: string;
  researchEnabled: boolean;
  settingsLink: ReactNode;
}

/**
 * One analysis: its brief (Analysis B, before it runs), its progress while it runs, and then the
 * report in Facts · Interpretation · Recommendation with Eric's decision on every finding.
 */
export function GapAnalysisView({
  analysisId,
  engagementId,
  researchEnabled,
  settingsLink,
}: GapAnalysisViewProps) {
  const report = useGapReport(analysisId, engagementId);
  const data = report.data;
  const running = isRunning(data?.analysis);
  const job = useGapJob(data?.analysis.job_id ?? null, running);
  const versions = useVersions(engagementId);
  const draft = (versions.data ?? []).find((v) => v.state === "draft") ?? null;
  const graph = useGraph(draft?.id ?? null);
  const roles = useRoles(engagementId);
  const decide = useDecideFinding(analysisId, engagementId);
  const grade = useSetFindingGrade(analysisId);
  const finalise = useFinaliseReport(analysisId, engagementId);
  const saveBrief = useUpdateBrief(analysisId);
  const run = useRunResearch(analysisId, data?.analysis.version_id ?? "");
  const navigate = useNavigate();
  const toast = useToast();
  const [filters, setFilters] = useState<GapFilters>(NO_FILTERS);
  const [stepFor, setStepFor] = useState<GapFinding | null>(null);
  const [dismissFor, setDismissFor] = useState<GapFinding | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [classFor, setClassFor] = useState<Record<string, GapClass>>({});

  if (report.isPending) return <Skeleton height="200px" />;
  if (report.isError || !data) {
    return (
      <ErrorState
        title="This analysis couldn't be loaded"
        message={messageOf(report.error)}
        details={copyDetailsOf(report.error)}
        onRetry={() => void report.refetch()}
      />
    );
  }

  const analysis = data.analysis;
  const locked = analysis.status === "finalised";
  const base = engagementPath(engagementId);
  const onMap = (versions.data ?? []).find((v) => v.id === analysis.version_id);
  const goTo = (elementId: string) => {
    if (onMap) void navigate(stepPath(base, onMap, elementId));
  };
  const openSource = (sourceId: string) =>
    void navigate(
      `${engagementPath(engagementId, "sources")}?source=${encodeURIComponent(sourceId)}`,
    );

  // A reality gap's class goes with Eric's decision once he has changed it (§3.12.7).
  const withClass = (finding: GapFinding): { gap_class?: GapClass } => {
    const chosen = classFor[finding.id];
    return chosen ? { gap_class: chosen } : {};
  };
  const send = (
    finding: GapFinding,
    action: DecisionAction,
    extra: { note?: string; step?: GapStepChoice } = {},
  ) =>
    decide.mutate(
      {
        findingId: finding.id,
        decision: { disposition: action, ...withClass(finding), ...extra },
      },
      {
        onSuccess: () => {
          setStepFor(null);
          setDismissFor(null);
          setProblem(null);
          toast(DONE[action]);
        },
        onError: (error) => setProblem(messageOf(error)),
      },
    );
  const onDecide = (finding: GapFinding, action: DecisionAction) => {
    setProblem(null);
    if (action === "added_step") setStepFor(finding);
    else if (action === "dismissed") setDismissFor(finding);
    else send(finding, action);
  };
  const cardProps = {
    mode: analysis.mode,
    locked,
    busy: decide.isPending,
    onGoTo: goTo,
    onOpenSource: openSource,
    onDecide,
    onChooseClass: (finding: GapFinding, gapClass: GapClass) =>
      setClassFor((chosen) => ({ ...chosen, [finding.id]: gapClass })),
    onGrade: (finding: GapFinding, chosen: GradeKey | null) =>
      grade.mutate({ findingId: finding.id, grade: chosen }),
  };

  const saveThen = (brief: Brief, confirmed: boolean, then?: () => void) =>
    saveBrief.mutate(
      { brief, confirmed },
      {
        onSuccess: () => then?.(),
        onError: (error) => setProblem(messageOf(error)),
      },
    );
  const startRun = () =>
    run.mutate(undefined, {
      onSuccess: () => toast("Research started."),
      onError: (error) => setProblem(messageOf(error)),
    });

  const shown = filterFindings(data.findings, filters);
  const open = openItems(data);
  const usage = data.usage;

  return (
    <section className="gap-report" aria-labelledby="gap-report-title">
      <h2 id="gap-report-title">
        {MODE_LABELS[analysis.mode]} · {analysis.version_label}
      </h2>

      {analysis.status === "brief_draft" && data.brief && (
        <BriefEditor
          state={data.brief}
          researchEnabled={researchEnabled}
          saving={saveBrief.isPending}
          running={run.isPending}
          problem={problem}
          onSave={(brief, confirmed) => saveThen(brief, confirmed)}
          onRun={(brief, confirmed) => saveThen(brief, confirmed, startRun)}
          settingsLink={settingsLink}
        />
      )}

      {running && (
        <div className="gap-progress" aria-live="polite">
          <p>
            {analysis.mode === "external"
              ? "Researching with your brief…"
              : "Comparing your documents with practice…"}{" "}
            You can leave this screen; the analysis keeps running.
          </p>
          {job.data && <StageStepper stages={job.data.stages} />}
        </div>
      )}

      {analysis.status === "failed" && (
        <>
          <ErrorState
            title="The analysis didn't finish"
            message={
              analysis.error ||
              "Something went wrong. Nothing on the map was changed."
            }
            details={analysis.job_id ? `job ${analysis.job_id}` : undefined}
          />
          {analysis.mode === "external" && data.brief && (
            <BriefEditor
              state={data.brief}
              researchEnabled={researchEnabled}
              saving={saveBrief.isPending}
              running={run.isPending}
              problem={problem}
              onSave={(brief, confirmed) => saveThen(brief, confirmed)}
              onRun={(brief, confirmed) => saveThen(brief, confirmed, startRun)}
              settingsLink={settingsLink}
            />
          )}
        </>
      )}

      {(analysis.status === "draft_report" || locked) && (
        <>
          <p className="gap__small">
            {usage &&
              `${plural(usage.calls, "AI call")} · ${(usage.input_tokens + usage.output_tokens).toLocaleString()} tokens`}
            {analysis.mode === "external" &&
              ` · ${plural(data.search_count, "web search", "web searches")} used`}
            {locked
              ? " · Finalised: read-only"
              : ` · ${plural(open, "item")} waiting for your decision`}
          </p>
          {analysis.notes.map((note) => (
            <p key={note} className="finding__note">
              {note}
            </p>
          ))}
          {data.findings.length > 0 && (
            <Filters report={data} filters={filters} onChange={setFilters} />
          )}
          {problem && (
            <p className="gap__problem" role="alert">
              {problem}
            </p>
          )}
          {data.findings.length === 0 && data.questions.length === 0 && (
            <EmptyState message="No finding passed every check. The rejected findings below show what was turned down and why." />
          )}
          {bySection(shown).map((group) => (
            <section
              key={group.section}
              className="gap-section"
              aria-labelledby={`gap-${group.section}`}
            >
              <h3 id={`gap-${group.section}`}>
                {SECTION_LABELS[group.section]}
              </h3>
              {group.findings.map((f) => (
                <FindingCard
                  key={f.id}
                  finding={f}
                  chosenClass={classFor[f.id]}
                  {...cardProps}
                />
              ))}
            </section>
          ))}
          {data.findings.length > 0 && shown.length === 0 && (
            <p className="gap__small">No finding matches these filters.</p>
          )}
          {data.questions.length > 0 && (
            <section className="gap-section" aria-labelledby="gap-questions">
              <h3 id="gap-questions">Questions for your SMEs</h3>
              <p className="gap__small">
                Causes the sources don't explain: ask rather than guess.
              </p>
              {data.questions.map((f) => (
                <FindingCard
                  key={f.id}
                  finding={f}
                  chosenClass={classFor[f.id]}
                  {...cardProps}
                />
              ))}
            </section>
          )}
          <RejectedFindings rejected={data.rejected} />
          {data.sources.length > 0 && (
            <details className="rejected-findings">
              <summary>
                Every page the search returned ({data.sources.length})
              </summary>
              <ul className="source-list">
                {data.sources.map((s) => (
                  <SourceListItem key={s.id} source={s} />
                ))}
              </ul>
            </details>
          )}
          <div className="gap-form__actions">
            {!locked && (
              <Button
                variant="primary"
                aria-busy={finalise.isPending || undefined}
                onClick={() =>
                  open > 0
                    ? setProblem(
                        `Decide on every finding first: ${open} still open.`,
                      )
                    : finalise.mutate(undefined, {
                        onSuccess: () => toast("Report finalised."),
                        onError: (error) => setProblem(messageOf(error)),
                      })
                }
              >
                Finalise report
              </Button>
            )}
            {locked ? (
              <a
                className="btn btn--secondary"
                href={exportUrl(analysis.id)}
                download
              >
                Export .md
              </a>
            ) : (
              <p className="gap__small">
                Export .md becomes available once the report is finalised.
              </p>
            )}
          </div>
        </>
      )}

      <Dialog
        open={stepFor !== null}
        title="Add as step"
        description={stepFor ? `From: ${stepFor.title}` : undefined}
        actions={null}
        onClose={() => setStepFor(null)}
      >
        {stepFor &&
          (draft && graph.data ? (
            <GapStepForm
              finding={stepFor}
              roles={roles.data ?? []}
              places={placesAfter(graph.data)}
              saving={decide.isPending}
              problem={problem}
              onSave={(step) => send(stepFor, "added_step", { step })}
              onCancel={() => setStepFor(null)}
            />
          ) : (
            <p>
              {draft
                ? "Loading the draft…"
                : "Reopen this map as a new draft first: questions and steps are added to the draft."}
            </p>
          ))}
      </Dialog>
      <Dialog
        open={dismissFor !== null}
        title="Dismiss finding"
        description={dismissFor?.title}
        actions={null}
        onClose={() => setDismissFor(null)}
      >
        {dismissFor && (
          <DismissForm
            saving={decide.isPending}
            problem={problem}
            onDismiss={(note) => send(dismissFor, "dismissed", { note })}
            onCancel={() => setDismissFor(null)}
          />
        )}
      </Dialog>
    </section>
  );
}
