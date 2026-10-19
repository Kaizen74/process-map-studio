import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { Card, EmptyState, ErrorState, SegmentedControl, SelectField, Skeleton } from "../../components/common";
import {
  BeliefDumbbells,
  Callouts,
  CaseJourney,
  CodeBadges,
  FixOrKeep,
  Glance,
  MetricTiles,
  PackDownloads,
  RealityLegend,
  RealityStack,
  RealityTable,
  Redline,
  TimeStretch,
} from "../../components/reality";
import { useEngagement } from "../../hooks/useEngagements";
import { useReality } from "../../hooks/useReality";
import { useVersions } from "../../hooks/useVersions";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { formatDate } from "../../lib/format";
import { VIEW_LABELS, VIEW_ORDER, type RealitySnapshot, type ViewId } from "../../lib/reality";
import type { VersionSummary } from "../../lib/reviewTypes";
import { EngagementProblem } from "../engagement/EngagementProblem";
import { DiscrepancyCard } from "./DiscrepancyCard";
import { IntentCard } from "./IntentCard";

const ACTIONS: Readonly<Record<string, { label: string; step: "sources" | "draft" | "system_records" | null }>> = {
  upload_documents: { label: "Add an SOP or manual on Sources", step: "sources" },
  import_log: { label: "Import a system log on System records", step: "system_records" },
  draft: { label: "Create a draft map", step: "draft" },
  add_intent: { label: "Add intent in the Intent card", step: null },
};

/** The version to show: the address's choice, else the current draft, else the latest published. */
function chooseVersion(versions: readonly VersionSummary[], wanted: string | null): VersionSummary | undefined {
  const usable = versions.filter((v) => v.state === "draft" || v.state === "published" || v.state === "superseded");
  return (
    usable.find((v) => v.id === wanted) ??
    usable.find((v) => v.state === "draft") ??
    usable.find((v) => v.state === "published") ??
    usable[0]
  );
}

/**
 * Reality (PRD §5.4, §5.12; P13b, P13c): how far reality is from the manual and the promise, for one
 * version's snapshot. Read-only pictures; every number, word and position comes from the backend.
 */
export function RealityScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const versions = useVersions(engagementId);
  const [params, setParams] = useSearchParams();
  const chosen = chooseVersion(versions.data ?? [], params.get("version"));
  const snapshot = useReality(chosen?.id ?? null);
  const view: ViewId = VIEW_ORDER.find((v) => v === params.get("view")) ?? "rv1";
  const selected = params.get("code");
  const [table, setTable] = useState(false);
  const [showAll, setShowAll] = useState(false);

  const set = (name: string, value: string | null) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (value === null) next.delete(name);
        else next.set(name, value);
        return next;
      },
      { replace: true },
    );
  const select = (code: string) => set("code", selected === code ? null : code);

  // Esc clears the selection (§5.12.6).
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && selected) set("code", null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }
  const failed = versions.isError ? versions.error : snapshot.isError ? snapshot.error : null;
  const usable = (versions.data ?? []).filter((v) => v.state !== "building");

  return (
    <main className="screen reality-screen" aria-labelledby="reality-title">
      <div>
        <h1 id="reality-title">Reality</h1>
        <p className="screen__intro">
          How far the process in practice is from the manual and from what the organisation intends, where the gap
          concentrates and which gaps to fix or keep. Every figure is worked out from your sources; nothing here is
          written by AI.
        </p>
      </div>
      {(versions.isPending || (chosen && snapshot.isPending)) && <Skeleton height="320px" />}
      {failed && (
        <ErrorState
          title="The Reality views couldn't be loaded"
          message={messageOf(failed)}
          details={copyDetailsOf(failed)}
          onRetry={() => void (versions.isError ? versions.refetch() : snapshot.refetch())}
        />
      )}
      {versions.isSuccess && !chosen && (
        <EmptyState
          message="There is no map yet. Create a draft map first: the Reality views compare it with your documents and intent."
          action={<Link to={engagementPath(engagementId, "draft")}>Go to Draft</Link>}
        />
      )}
      {chosen && usable.length > 1 && (
        <div className="reality-version">
          <SelectField
            label="Version"
            value={chosen.id}
            options={usable.map((v) => ({
              value: v.id,
              label:
                v.state === "draft"
                  ? `${v.label} · draft`
                  : `${v.label} · ${v.state === "superseded" ? "superseded" : "published"} ${formatDate(v.published_at ?? "")}`,
            }))}
            onChange={(id) => set("version", id)}
          />
        </div>
      )}
      {snapshot.data && chosen && (
        <RealityBody
          snapshot={snapshot.data}
          version={chosen}
          engagementId={engagementId}
          view={view}
          selected={selected}
          table={table}
          showAll={showAll}
          onView={(v) => set("view", v)}
          onSelect={select}
          onTable={() => setTable((t) => !t)}
          onShowAll={() => setShowAll(true)}
        />
      )}
    </main>
  );
}

interface BodyProps {
  snapshot: RealitySnapshot;
  version: VersionSummary;
  engagementId: string;
  view: ViewId;
  selected: string | null;
  table: boolean;
  showAll: boolean;
  onView: (view: ViewId) => void;
  onSelect: (code: string) => void;
  onTable: () => void;
  onShowAll: () => void;
}

/** The Reality pack (P13d): a published version's views on A3 or 16:9 pages; a draft is explained. */
function PackCard({ version, engagementId }: { version: VersionSummary; engagementId: string }) {
  const frozen = version.state === "published" || version.state === "superseded";
  return (
    <Card title="Reality pack" className="reality-pack-card">
      {frozen ? (
        <>
          <p>All seven views of {version.label}, one per page, to print or save as PDF. Role names only; no quotes.</p>
          <PackDownloads versionId={version.id} versionLabel={version.label} />
        </>
      ) : (
        <p>
          The pack prints a published version, whose figures are frozen. Publish this draft to print it.{" "}
          <Link to={engagementPath(engagementId, "review")}>Go to Review</Link>
        </p>
      )}
    </Card>
  );
}

function RealityBody({ snapshot, version, engagementId, view, selected, table, showAll, onView, onSelect, onTable, onShowAll }: BodyProps) {
  const current = snapshot.views[view];
  const codes = snapshot.codes;
  const action = current.availability.action ? ACTIONS[current.availability.action] : undefined;
  return (
    <div className="reality-layout">
      <div className="reality-main">
        {snapshot.draft && (
          <p className="reality-banner" role="note">
            Draft: figures may change. Publishing the map freezes them.
          </p>
        )}
        <SegmentedControl
          label="Reality view"
          options={VIEW_ORDER.map((v) => ({ value: v, label: VIEW_LABELS[v] }))}
          value={view}
          onChange={onView}
        />
        <section className="reality-view" aria-labelledby="reality-question">
          <h2 id="reality-question" className="reality-view__title">
            {current.title}
          </h2>
          <p className="reality-view__headline">{current.headline}</p>
          {current.availability.message && (
            <p className="inline-note reality-view__availability">
              {current.availability.message}
              {action?.step && (
                <>
                  {" "}
                  <Link to={engagementPath(engagementId, action.step)}>{action.label}</Link>
                </>
              )}
            </p>
          )}
          {view === "rv1" && <MetricTiles tiles={snapshot.tiles} />}
          {view === "rv1" && <Glance view={snapshot.views.rv1} codes={codes} selected={selected} onSelect={onSelect} />}
          {view === "rv2" && <RealityStack view={snapshot.views.rv2} selected={selected} onSelect={onSelect} />}
          {view === "rv3" && (
            <FixOrKeep
              view={snapshot.views.rv3}
              codes={codes}
              selected={selected}
              onSelect={onSelect}
              showAll={showAll}
              onShowAll={onShowAll}
            />
          )}
          {view === "rv4" && <Redline view={snapshot.views.rv4} selected={selected} onSelect={onSelect} />}
          {view === "rv5" && <TimeStretch view={snapshot.views.rv5} selected={selected} onSelect={onSelect} />}
          {view === "rv6" && <BeliefDumbbells view={snapshot.views.rv6} selected={selected} onSelect={onSelect} />}
          {view === "rv7" && <CaseJourney view={snapshot.views.rv7} selected={selected} onSelect={onSelect} />}
          {(view === "rv2" || view === "rv5") && snapshot.columns_note && (
            <p className="inline-note">{snapshot.columns_note}</p>
          )}
          <CodeBadges
            codes={codes.filter((c) => viewCodes(snapshot, view).includes(c.code))}
            selected={selected}
            onSelect={onSelect}
          />
          <Callouts callouts={current.callouts} legend={snapshot.legend} />
          <button type="button" className="btn btn--link" aria-expanded={table} onClick={onTable}>
            {table ? "Hide the table" : "Show as table"}
          </button>
          {table && <RealityTable table={current.table} caption={current.title} />}
          <RealityLegend legend={snapshot.legend} evidence={snapshot.evidence.text} />
        </section>
      </div>
      <aside className="reality-side" aria-label="Intent, discrepancies and the Reality pack">
        <IntentCard engagementId={engagementId} snapshot={snapshot} />
        <DiscrepancyCard engagementId={engagementId} snapshot={snapshot} selected={selected} onSelect={onSelect} />
        <PackCard version={version} engagementId={engagementId} />
      </aside>
    </div>
  );
}

/** The codes a view draws or lists (its badges list). */
function viewCodes(snapshot: RealitySnapshot, view: ViewId): string[] {
  const v = snapshot.views;
  switch (view) {
    case "rv1":
      return v.rv1.glance.routes.flatMap((r) => r.codes);
    case "rv2":
      return [...v.rv2.stack.highlighted, ...v.rv2.stack.listed];
    case "rv3":
      return v.rv3.fix.circles.map((c) => c.code);
    case "rv4":
      return v.rv4.redline.markups.map((m) => m.code);
    case "rv5":
      return v.rv5.time.causes.map((c) => c.code);
    case "rv6":
      return v.rv6.belief.rows.flatMap((r) => (r.code ? [r.code] : []));
    case "rv7":
      return v.rv7.callouts.flatMap((c) => (c.code ? [c.code] : []));
  }
}
