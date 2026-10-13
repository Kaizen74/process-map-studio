import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { EmptyState, ErrorState, SegmentedControl, Skeleton } from "../../components/common";
import {
  AiFlagList,
  AssumptionsForm,
  BoundaryList,
  ExceptionList,
  GlossaryList,
  PreserveImproveList,
  StoryList,
  CauseList,
  ConstraintGroups,
  ExternalPracticeList,
  KRiskList,
  RoleCostsForm,
  ThemeList,
  ValueRegister,
} from "../../components/registers";
import { useToast } from "../../components/shell";
import { QuestionsTab, RejectedClaimsTab } from "../../components/tabs";
import { useEngagement } from "../../hooks/useEngagements";
import { useGraph } from "../../hooks/useReview";
import { useSettings } from "../../hooks/useSettings";
import {
  useAssumptions,
  useDispositions,
  useRoleCosts,
  useSetAssumptions,
  useSetRoleCosts,
  useValue,
} from "../../hooks/useValue";
import {
  useCauseLibrary,
  useCapabilityNotes,
  useDecideTheme,
  useExceptions,
  useGlossary,
  useLaneBoundaries,
  useRegisters,
  useStories,
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
import { registerKey, registerOptions, type CauseEntry, type ThemeStatus, type ValidationResult } from "../../lib/registers";
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
  // Disposition and value (R10c) joins the list only while the value module is on (decision A).
  const settings = useSettings();
  const valueOn = settings.data?.value_enabled === true;
  const options = registerOptions(valueOn);
  const chosenRegister = registerKey(params.get("register"), options);
  const boundaries = useLaneBoundaries(map?.id ?? null);
  const [exceptionsView, setExceptionsView] = useState<AsView>("done");
  // Stories, Glossary, Preserve / Improve (P9u): fetched when shown; their steps come by label,
  // so the map's own graph says which are on it and where Go to leads.
  const sense = ["stories", "glossary", "preserve"].includes(chosenRegister);
  const stories = useStories(map?.id ?? null, chosenRegister === "stories");
  const glossary = useGlossary(map?.id ?? null, chosenRegister === "glossary");
  const notes = useCapabilityNotes(map?.id ?? null, chosenRegister === "preserve");
  const mapGraph = useGraph(sense ? (map?.id ?? null) : null);
  const unusual = useExceptions(map?.id ?? null, exceptionsView, chosenRegister === "exceptions");
  const chosen = chosenRegister;
  const showValue = chosen === "value";
  const [valueView, setValueView] = useState<AsView>("done");
  const value = useValue(map?.id ?? null, valueView, showValue);
  const dispositions = useDispositions(map?.id ?? null, showValue);
  const roleCosts = useRoleCosts(engagementId, showValue);
  const assumptions = useAssumptions(engagementId, showValue);
  const saveCosts = useSetRoleCosts(engagementId);
  const saveAssumptions = useSetAssumptions(engagementId);

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
  const stepIds = new Map((mapGraph.data?.elements ?? []).filter((e) => e.review_status !== "rejected").map((e) => [e.label, e.id]));
  const links = {
    onMap: new Set(stepIds.keys()),
    onGoTo: (label: string) => {
      const id = stepIds.get(label);
      if (id) goTo(id);
    },
  };
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
          practice, questions for your SME, rejected claims, stories, glossary, Preserve / Improve, lane boundaries and
          exceptions and workarounds, and the cause library and emerging themes for this engagement
          {valueOn ? ", and disposition and value" : ""}.
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
          <SegmentedControl label="Register" options={options} value={chosen} onChange={choose} />
          <section aria-label={options.find((r) => r.value === chosen)?.label} className="register-panel">
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
            {chosen === "stories" && (
              <SenseRegister
                intro="What happened in real cases, good and bad, in the interviewees' own words. A story told only once is kept and marked; nothing here changes the map."
                query={stories}
                what="stories"
                render={(data) => <StoryList stories={data} links={links} />}
              />
            )}
            {chosen === "glossary" && (
              <SenseRegister
                intro="The interviewees' own terms, in the order first heard, with what each means in plain words."
                query={glossary}
                what="glossary"
                render={(data) => <GlossaryList entries={data} links={links} />}
              />
            )}
            {chosen === "preserve" && (
              <SenseRegister
                intro="What interviewees say works well (to preserve) and what gets in the way (to improve), by capability dimension. Nothing here changes the map."
                query={notes}
                what="strengths and weaknesses"
                render={(data) => <PreserveImproveList notes={data} links={links} />}
              />
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
            {showValue && (
              <>
                <p className="tab-intro">
                  Indicative hours and cost per step and phase, each with where it comes from, and what each disposition
                  could release. Worked out by the app from measured figures, the SMEs&apos; estimates and your own
                  figures; never per person. Nothing here changes the map.
                </p>
                <SegmentedControl label="View" options={AS_VIEWS} value={valueView} onChange={(v) => setValueView(v as AsView)} />
                {(value.isPending || dispositions.isPending) && <Skeleton height="120px" />}
                {(value.isError || dispositions.isError) && (
                  <ErrorState
                    title="The figures couldn't be loaded"
                    message={messageOf(value.error ?? dispositions.error)}
                    details={copyDetailsOf(value.error ?? dispositions.error)}
                    onRetry={() => {
                      void value.refetch();
                      void dispositions.refetch();
                    }}
                  />
                )}
                {value.data && dispositions.data && (
                  <ValueRegister report={value.data} dispositions={dispositions.data} onGoTo={goTo} />
                )}
                <h2 className="register-heading">Role costs</h2>
                {roleCosts.isPending && <Skeleton height="80px" />}
                {roleCosts.isError && (
                  <ErrorState
                    title="The role costs couldn't be loaded"
                    message={messageOf(roleCosts.error)}
                    details={copyDetailsOf(roleCosts.error)}
                    onRetry={() => void roleCosts.refetch()}
                  />
                )}
                {roleCosts.data && (
                  <RoleCostsForm
                    key={roleCosts.dataUpdatedAt}
                    costs={roleCosts.data}
                    busy={saveCosts.isPending}
                    error={saveCosts.isError ? messageOf(saveCosts.error) : null}
                    onSave={(rows) => saveCosts.mutate(rows, { onSuccess: () => toast("Role costs saved.") })}
                  />
                )}
                <h2 className="register-heading">Assumptions</h2>
                {assumptions.isPending && <Skeleton height="80px" />}
                {assumptions.isError && (
                  <ErrorState
                    title="The assumptions couldn't be loaded"
                    message={messageOf(assumptions.error)}
                    details={copyDetailsOf(assumptions.error)}
                    onRetry={() => void assumptions.refetch()}
                  />
                )}
                {assumptions.data && (
                  <AssumptionsForm
                    key={assumptions.dataUpdatedAt}
                    assumptions={assumptions.data}
                    busy={saveAssumptions.isPending}
                    error={saveAssumptions.isError ? messageOf(saveAssumptions.error) : null}
                    onSave={(rows) =>
                      saveAssumptions.mutate(rows, { onSuccess: () => toast("Assumptions saved.") })
                    }
                  />
                )}
              </>
            )}
          </section>
        </>
      )}
    </main>
  );
}

/** One of the interview lists (P9u): the intro, then loading, the error with Try again, or the list. */
function SenseRegister<T>({
  intro,
  query,
  what,
  render,
}: {
  intro: string;
  query: { isPending: boolean; isError: boolean; error: unknown; data: T | undefined; refetch: () => unknown };
  what: string;
  render: (data: T) => ReactNode;
}) {
  return (
    <>
      <p className="tab-intro">{intro}</p>
      {query.isPending && <Skeleton height="120px" />}
      {query.isError && (
        <ErrorState
          title={`The ${what} couldn't be loaded`}
          message={messageOf(query.error)}
          details={copyDetailsOf(query.error)}
          onRetry={() => void query.refetch()}
        />
      )}
      {query.data !== undefined && render(query.data)}
    </>
  );
}
