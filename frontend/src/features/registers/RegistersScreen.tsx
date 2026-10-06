import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { EmptyState, ErrorState, SegmentedControl, Skeleton } from "../../components/common";
import {
  AiFlagList,
  BoundaryList,
  ExceptionList,
  CauseList,
  ConstraintGroups,
  ExternalPracticeList,
  KRiskList,
  ThemeList,
} from "../../components/registers";
import { useToast } from "../../components/shell";
import { QuestionsTab, RejectedClaimsTab } from "../../components/tabs";
import { useEngagement } from "../../hooks/useEngagements";
import {
  useCauseLibrary,
  useDecideTheme,
  useExceptions,
  useLaneBoundaries,
  useRegisters,
  useThemes,
  useValidateCause,
  useVersions,
} from "../../hooks/useVersions";
import { currentMap, stepPath } from "../../lib/currentMap";
import { AS_VIEWS, type AsView } from "../../lib/views";
import { saveText } from "../../lib/download";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { questionsFileName, questionsMarkdown } from "../../lib/questions";
import { REGISTERS, registerKey, type CauseEntry, type ThemeStatus, type ValidationResult } from "../../lib/registers";
import { EngagementProblem } from "../engagement/EngagementProblem";

const DONE: Readonly<Record<ValidationResult, string>> = {
  confirmed: "Cause confirmed.",
  refuted: "Cause refuted.",
  pending: "Cause reopened.",
};

/**
 * Registers (PRD §5.4): one switch per register of the map Eric is working on (the draft, else
 * the latest published version), plus the engagement's cause library. Every entry links to its
 * step; nothing here changes the map.
 */
const THEME_DONE: Record<ThemeStatus, string> = {
  accepted: "Theme accepted.",
  dismissed: "Theme dismissed.",
  proposed: "Theme reopened.",
};

export function RegistersScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const versions = useVersions(engagementId);
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const map = currentMap(versions.data ?? []);
  const registers = useRegisters(map?.id ?? null);
  const causes = useCauseLibrary(engagementId);
  const validate = useValidateCause(engagementId);
  const themes = useThemes(engagementId);
  const decide = useDecideTheme(engagementId);
  const chosenRegister = registerKey(params.get("register"));
  const boundaries = useLaneBoundaries(map?.id ?? null);
  const [exceptionsView, setExceptionsView] = useState<AsView>("done");
  const unusual = useExceptions(map?.id ?? null, exceptionsView, chosenRegister === "exceptions");
  const chosen = chosenRegister;

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }

  const base = engagementPath(engagementId);
  const goTo = (elementId: string) => {
    if (map) void navigate(stepPath(base, map, elementId));
  };
  const choose = (value: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.set("register", value);
        return next;
      },
      { replace: true },
    );
  const onValidate = (entry: CauseEntry, result: ValidationResult) =>
    validate.mutate({ causeId: entry.id, result }, { onSuccess: () => toast(DONE[result]) });

  const data = registers.data;
  const title = data && map ? `${map.label}${map.state === "draft" ? "" : " (published)"}` : "";
  const markdown = () =>
    questionsMarkdown(data?.questions ?? [], engagement.data?.process_name || engagement.data?.name || "", map?.label ?? "");
  const failed = versions.isError ? versions.error : registers.isError ? registers.error : null;

  return (
    <main className="screen" aria-labelledby="registers-title">
      <div>
        <h1 id="registers-title">Registers</h1>
        <p className="screen__intro">
          The lists behind the map{title ? ` (${title})` : ""}: knowledge risks, AI flags, constraints, recommended
          practice, questions for your SME, rejected claims, lane boundaries and exceptions and workarounds, and the cause
          library and emerging themes for this engagement.
        </p>
      </div>
      {(versions.isPending || (map !== null && registers.isPending)) && <Skeleton height="200px" />}
      {failed !== null && (
        <ErrorState
          title="The registers couldn't be loaded"
          message={messageOf(failed)}
          details={copyDetailsOf(failed)}
          onRetry={() => {
            void versions.refetch();
            void registers.refetch();
          }}
        />
      )}
      {!versions.isPending && !versions.isError && map === null && (
        <EmptyState
          message="No draft map yet. The registers fill up from the draft map: create one on Draft."
          action={<Link to={engagementPath(engagementId, "draft")}>Go to Draft</Link>}
        />
      )}
      {data && (
        <>
          <SegmentedControl label="Register" options={REGISTERS} value={chosen} onChange={choose} />
          <section aria-label={REGISTERS.find((r) => r.value === chosen)?.label} className="register-panel">
            {chosen === "k_risk" && <KRiskList items={data.k_risk} onGoTo={goTo} />}
            {chosen === "ai_flags" && <AiFlagList items={data.ai_flags} onGoTo={goTo} />}
            {chosen === "constraints" && <ConstraintGroups groups={data.constraints_by_cause} onGoTo={goTo} />}
            {chosen === "external" && <ExternalPracticeList items={data.external_practice} onGoTo={goTo} />}
            {chosen === "questions" && (
              <QuestionsTab
                questions={data.questions}
                onGoTo={goTo}
                onCopy={() => {
                  void navigator.clipboard
                    ?.writeText(markdown())
                    .then(() => toast("Questions copied."))
                    .catch(() => undefined);
                }}
                onDownload={() => saveText(questionsFileName(map?.label ?? ""), markdown())}
              />
            )}
            {chosen === "rejected" && (
              <RejectedClaimsTab
                data={data.rejected_claims}
                onOpenPassage={(claim) =>
                  void navigate(`${engagementPath(engagementId, "sources")}?source=${encodeURIComponent(claim.source_id)}`)
                }
              />
            )}
            {chosen === "causes" && (
              <>
                {causes.isPending && <Skeleton height="120px" />}
                {causes.isError && (
                  <ErrorState
                    title="The cause library couldn't be loaded"
                    message={messageOf(causes.error)}
                    details={copyDetailsOf(causes.error)}
                    onRetry={() => void causes.refetch()}
                  />
                )}
                {causes.data && (
                  <CauseList
                    entries={causes.data}
                    busyId={validate.isPending ? (validate.variables?.causeId ?? null) : null}
                    onGoTo={goTo}
                    onValidate={onValidate}
                  />
                )}
                {validate.isError && (
                  <p className="panel-danger" role="alert">
                    {messageOf(validate.error)}
                  </p>
                )}
              </>
            )}
            {chosen === "themes" && (
              <>
                <p className="tab-intro">
                  Patterns across two or more stories that fit no existing category, proposed by Claude and checked by the
                  app. Accept, rename or dismiss them; they never change the map.
                </p>
                {themes.isPending && <Skeleton height="120px" />}
                {themes.isError && (
                  <ErrorState
                    title="The emerging themes couldn't be loaded"
                    message={messageOf(themes.error)}
                    details={copyDetailsOf(themes.error)}
                    onRetry={() => void themes.refetch()}
                  />
                )}
                {themes.data && (
                  <ThemeList
                    themes={themes.data}
                    busyId={decide.isPending ? (decide.variables?.themeId ?? null) : null}
                    error={
                      decide.isError && decide.variables
                        ? { themeId: decide.variables.themeId, message: messageOf(decide.error) }
                        : null
                    }
                    onDecide={(theme, status, name) =>
                      decide.mutate(
                        name === undefined ? { themeId: theme.id, status } : { themeId: theme.id, status, theme: name },
                        { onSuccess: () => toast(THEME_DONE[status]) },
                      )
                    }
                  />
                )}
              </>
            )}
            {chosen === "exceptions" && (
              <>
                <p className="tab-intro">
                  How much of the process is the usual route and how much is exception handling, rework and workarounds.
                  As done shows what people actually do; compare it with As documented. Nothing here changes the map.
                </p>
                <SegmentedControl label="View" options={AS_VIEWS} value={exceptionsView} onChange={(v) => setExceptionsView(v as AsView)} />
                {unusual.isPending && <Skeleton height="120px" />}
                {unusual.isError && (
                  <ErrorState
                    title="The exceptions couldn't be loaded"
                    message={messageOf(unusual.error)}
                    details={copyDetailsOf(unusual.error)}
                    onRetry={() => void unusual.refetch()}
                  />
                )}
                {unusual.data && <ExceptionList report={unusual.data} onGoTo={goTo} />}
              </>
            )}
            {chosen === "boundaries" && (
              <>
                <p className="tab-intro">
                  Where the interviews say teams share a step or that it falls between them. The map keeps one Responsible
                  (the step&apos;s lane) and lists the others as Consulted; settle each with the teams. Nothing here changes
                  the map.
                </p>
                {boundaries.isPending && <Skeleton height="120px" />}
                {boundaries.isError && (
                  <ErrorState
                    title="The lane boundaries couldn't be loaded"
                    message={messageOf(boundaries.error)}
                    details={copyDetailsOf(boundaries.error)}
                    onRetry={() => void boundaries.refetch()}
                  />
                )}
                {boundaries.data && <BoundaryList items={boundaries.data} onGoTo={goTo} />}
              </>
            )}
          </section>
        </>
      )}
    </main>
  );
}
