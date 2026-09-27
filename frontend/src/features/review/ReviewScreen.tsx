import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { Card, EmptyState, ErrorState, Skeleton } from "../../components/common";
import { MapLegend, MapStage, MapToolbar, type Zoom } from "../../components/map";
import { RaciMatrix } from "../../components/tabs";
import { VersionBanner } from "../../components/shell";
import { useDraft } from "../../hooks/useDraft";
import { useEngagement } from "../../hooks/useEngagements";
import { useGraph, useLayout } from "../../hooks/useReview";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import type { EvidenceCard } from "../../lib/mapTypes";
import { firstNeedingAttention } from "../../lib/review";
import { EngagementProblem } from "../engagement/EngagementProblem";
import { DetailPanel } from "./DetailPanel";
import { HeaderStrip } from "./HeaderStrip";
import { SourcePanel } from "./SourcePanel";
import { HowToReview } from "./HowToReview";
import { useFitScale } from "./useFitScale";
import { useLens } from "./useLens";
import "./review.css";

const STEPS = new Set(["activity", "decision", "approval"]);
const MAX_STEPS = 25;
const MAX_LANES = 6;

/** Review (PRD §5.6): the draft map with its banner, header strip, lenses and detail panel. */
export function ReviewScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const draft = useDraft(engagementId);
  const versionId = draft.data?.version?.id ?? null;
  const graph = useGraph(versionId);
  const layout = useLayout(versionId);
  const [params, setParams] = useSearchParams();
  const selectedId = params.get("step");
  const [lens, setLens] = useLens();
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [mapBox, fit] = useFitScale(layout.data?.canvas.w ?? 0);
  // The source viewer replaces the panel's content; it belongs to the step it was opened from.
  const [viewing, setViewing] = useState<{ step: string; card: EvidenceCard } | null>(null);
  const openCard = viewing && viewing.step === selectedId ? viewing.card : null;
  useEffect(() => {
    if (!openCard) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setViewing(null); // PRD §5.8: Esc closes the viewer
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openCard]);

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }

  function select(id: string | null) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (id) next.set("step", id);
        else next.delete("step");
        return next;
      },
      { replace: true },
    );
  }

  const failed = [draft, graph, layout].find((q) => q.isError);
  if (failed) {
    return (
      <main className="screen" aria-labelledby="review-title">
        <h1 id="review-title">Review</h1>
        <ErrorState
          title="The map couldn't be loaded"
          message={messageOf(failed.error)}
          details={copyDetailsOf(failed.error)}
          onRetry={() => void failed.refetch()}
        />
      </main>
    );
  }

  if (draft.isSuccess && !versionId) {
    const running = draft.data.job?.status === "queued" || draft.data.job?.status === "running";
    return (
      <main className="screen" aria-labelledby="review-title">
        <h1 id="review-title">Review</h1>
        <EmptyState
          message={
            running
              ? "A draft map is being made. It appears here as soon as it's ready."
              : "There is no draft map to review yet. Create one on the Draft screen."
          }
          action={<Link to={engagementPath(engagementId, "draft")}>Go to Draft</Link>}
        />
      </main>
    );
  }

  if (!graph.data || !layout.data || !draft.data?.version) {
    return (
      <main className="screen" aria-labelledby="review-title" aria-busy="true">
        <h1 id="review-title">Review</h1>
        <Skeleton height="48px" />
        <Skeleton height="96px" />
        <Skeleton height="420px" />
      </main>
    );
  }

  const g = graph.data;
  const drawing = layout.data;
  const steps = g.elements.filter((e) => STEPS.has(e.kind));
  const selected = g.elements.find((e) => e.id === selectedId) ?? null;
  const roles = new Map(g.roles.map((r) => [r.id, r.name]));
  const phases = new Map(g.phases.map((p) => [p.id, p.name]));
  const sources = new Set(g.elements.flatMap((e) => e.evidence.map((ev) => ev.source_id))).size;
  const lanes = drawing.lanes.length;
  const start = firstNeedingAttention(g);

  return (
    <div className="review">
      <VersionBanner
        label={g.version.label}
        sources={sources}
        steps={steps}
        selectedId={selected?.id ?? null}
        onSelect={select}
      />
      <div className="review__body">
        <main className="review__main" aria-labelledby="review-title">
          <h1 id="review-title" className="visually-hidden">
            Review
          </h1>
          <HeaderStrip process={g.process} />
          <Card className="map-card">
            <MapToolbar
              lens={lens}
              onLens={setLens}
              zoom={zoom}
              onZoom={setZoom}
              steps={steps.length}
              lanes={lanes}
              phases={drawing.phases.length}
              large={steps.length > MAX_STEPS || lanes > MAX_LANES}
            />
            <div ref={mapBox} className={zoom === "full" ? "map-card__canvas map-card__canvas--scroll" : "map-card__canvas"}>
              <MapStage
                graph={g}
                layout={drawing}
                lens={lens}
                scale={zoom === "fit" ? fit : 1}
                selectedId={selected?.id ?? null}
                onSelect={select}
              />
            </div>
            <MapLegend lens={lens} />
          </Card>
          <Card title="RACI matrix" description="Questions, rejected claims, audit, merge decisions and lint arrive as tabs in build phase P6.">
            <RaciMatrix
              graph={g}
              laneOrder={drawing.lanes.map((lane) => lane.role_id)}
              selectedId={selected?.id ?? null}
              onSelect={select}
            />
          </Card>
        </main>
        <aside
          className="review__panel"
          aria-label={selected && openCard ? "Source" : selected ? "Step details" : "How to review"}
        >
          {selected && openCard ? (
            <SourcePanel card={openCard} stepLabel={selected.label} onBack={() => setViewing(null)} />
          ) : selected ? (
            <DetailPanel
              element={selected}
              laneName={roles.get(selected.lane_role_id ?? "") ?? ""}
              phaseName={phases.get(selected.phase_id ?? "") ?? ""}
              onOpenEvidence={(card) => setViewing({ step: selected.id, card })}
              onClose={() => select(null)}
            />
          ) : (
            <HowToReview onStart={start ? () => select(start) : null} />
          )}
        </aside>
      </div>
    </div>
  );
}
