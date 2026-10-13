import { Link, useParams, useSearchParams } from "react-router";
import { Button, Card, Chip, EmptyState, ErrorState, SelectField, Skeleton } from "../../components/common";
import { useToast } from "../../components/shell";
import { useEngagement } from "../../hooks/useEngagements";
import { useGapAnalyses, useStartExternal, useStartInternal } from "../../hooks/useGap";
import { useSettings } from "../../hooks/useSettings";
import { useVersions } from "../../hooks/useVersions";
import { currentMap } from "../../lib/currentMap";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { formatDateTime, plural } from "../../lib/format";
import { MODE_LABELS, STATUS_LABELS, type GapAnalysis } from "../../lib/gap";
import { EngagementProblem } from "../engagement/EngagementProblem";
import { GapAnalysisView } from "./GapAnalysisView";
import "./gap.css";

function HistoryRow({ analysis, chosen, onOpen }: { analysis: GapAnalysis; chosen: boolean; onOpen: () => void }) {
  const c = analysis.counts;
  return (
    <li className={`gap-history__row${chosen ? " gap-history__row--chosen" : ""}`}>
      <button type="button" className="gap-history__open" onClick={onOpen} aria-current={chosen || undefined}>
        <span className="gap-history__mode">{MODE_LABELS[analysis.mode]}</span>
        <span className="gap-history__meta">
          {formatDateTime(analysis.created_at)} · {analysis.version_label} · {STATUS_LABELS[analysis.status]}
          {(analysis.status === "draft_report" || analysis.status === "finalised") &&
            ` · ${plural(c.kept, "finding")}, ${c.open} open, ${c.rejected} rejected`}
        </span>
      </button>
    </li>
  );
}

/**
 * Gap analysis (PRD §5.4, optional): documents vs practice, and external best practice from an
 * approved brief. Advisory: nothing changes the map unless Eric decides so on a finding.
 */
export function GapScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const versions = useVersions(engagementId);
  const settings = useSettings();
  const [params, setParams] = useSearchParams();
  const toast = useToast();

  const maps = (versions.data ?? []).filter((v) => v.state !== "building");
  const map = maps.find((v) => v.id === params.get("version")) ?? currentMap(versions.data ?? []);
  const analyses = useGapAnalyses(map?.id ?? null);
  const startInternal = useStartInternal(map?.id ?? "");
  const startExternal = useStartExternal(map?.id ?? "");
  const chosenId = params.get("analysis");

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }

  const set = (changes: Record<string, string | null>) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        for (const [key, value] of Object.entries(changes)) {
          if (value) next.set(key, value);
          else next.delete(key);
        }
        return next;
      },
      { replace: true },
    );
  const researchOn = settings.data?.web_research_enabled ?? false;
  // R10 (decision A): on by default; switched off, the screen says so and keeps every analysis.
  const gapOn = settings.data?.gap_analysis_enabled !== false;
  const settingsLink = <Link to="/settings">Turn it on in Settings</Link>;

  const runInternal = () =>
    startInternal.mutate(undefined, {
      onSuccess: (started) => {
        toast("Documents-vs-practice analysis started.");
        set({ analysis: started.analysis_id });
      },
    });
  const prepareBrief = () =>
    startExternal.mutate(undefined, { onSuccess: (view) => set({ analysis: view.analysis.id }) });
  const startProblem = startInternal.error ?? startExternal.error;

  return (
    <main className="screen" aria-labelledby="gap-title">
      <div>
        <h1 id="gap-title">
          Gap analysis <Chip>Optional</Chip>
        </h1>
        <p className="screen__intro">
          A second opinion on your map. Each finding comes with its evidence or sources, and nothing changes on the map
          unless you decide so.
        </p>
      </div>
      {settings.isSuccess && !settings.data.gap_analysis_enabled && (
        <EmptyState
          message="Gap analysis is switched off. Switch it on under Optional modules in Settings to compare this map with your sources or with published practice. Earlier analyses are kept."
          action={<Link to="/settings">Go to Settings</Link>}
        />
      )}
      {gapOn && versions.isPending && <Skeleton height="160px" />}
      {gapOn && versions.isError && (
        <ErrorState
          title="The maps couldn't be loaded"
          message={messageOf(versions.error)}
          details={copyDetailsOf(versions.error)}
          onRetry={() => void versions.refetch()}
        />
      )}
      {gapOn && versions.isSuccess && !map && (
        <EmptyState
          message="Make a draft map first. A gap analysis compares a map with your sources or with published practice."
          action={<Link to={engagementPath(engagementId, "draft")}>Go to Draft</Link>}
        />
      )}
      {gapOn && map && (
        <>
          {maps.length > 1 && (
            <div className="gap__version">
              <SelectField
                label="Map"
                value={map.id}
                options={maps.map((v) => ({ value: v.id, label: `${v.label} · ${v.state}` }))}
                onChange={(id) => set({ version: id, analysis: null })}
              />
            </div>
          )}
          <div className="gap__cards">
            <Card title="Documents vs practice">
              <p>Where what your SMEs describe differs from the SOPs, job descriptions and manuals, and why.</p>
              <p className="gap__small">Uses only your uploaded sources. About 2 AI calls.</p>
              <Button variant="primary" onClick={runInternal} aria-busy={startInternal.isPending || undefined}>
                Run analysis
              </Button>
            </Card>
            <Card title="External best practice">
              <p>What comparable processes in your industry and adjacent industries include or do differently.</p>
              <p className="gap__small">
                Sends only the research brief you approve to web search. Web research is{" "}
                <strong>{researchOn ? "on" : "off"}</strong>.{!researchOn && <> {settingsLink}.</>}
              </p>
              <Button onClick={prepareBrief} aria-busy={startExternal.isPending || undefined}>
                Prepare research brief
              </Button>
            </Card>
          </div>
          {startProblem && (
            <p className="gap__problem" role="alert">
              {messageOf(startProblem)}
            </p>
          )}

          <section aria-labelledby="gap-history-title">
            <h2 id="gap-history-title">Analyses of {map.label}</h2>
            {analyses.isPending && <Skeleton height="60px" />}
            {analyses.isError && (
              <ErrorState
                title="The analyses couldn't be loaded"
                message={messageOf(analyses.error)}
                details={copyDetailsOf(analyses.error)}
                onRetry={() => void analyses.refetch()}
              />
            )}
            {analyses.isSuccess && analyses.data.length === 0 && (
              <p className="gap__small">No analyses of this map yet. Start one above.</p>
            )}
            {analyses.isSuccess && analyses.data.length > 0 && (
              <ul className="gap-history">
                {analyses.data.map((a) => (
                  <HistoryRow key={a.id} analysis={a} chosen={a.id === chosenId} onOpen={() => set({ analysis: a.id })} />
                ))}
              </ul>
            )}
          </section>

          {chosenId && (
            <GapAnalysisView
              key={chosenId}
              analysisId={chosenId}
              engagementId={engagementId}
              researchEnabled={researchOn}
              settingsLink={settingsLink}
            />
          )}
        </>
      )}
    </main>
  );
}
