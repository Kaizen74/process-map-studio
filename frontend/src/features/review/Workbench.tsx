import { useCallback, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import type { ReactNode } from "react";
import { Card, ErrorState, Skeleton } from "../../components/common";
import { MapLegend, MapStage, MapToolbar, WalkthroughStrip, type MapView, type Zoom } from "../../components/map";
import { AllReviewed } from "../../components/panel";
import { useGapAnalyses } from "../../hooks/useGap";
import { useVersionImages } from "../../hooks/useImages";
import { useGraph, useLayout, useReviewStep } from "../../hooks/useReview";
import { engagementPath } from "../../lib/engagementSteps";
import { plural } from "../../lib/format";
import { stepsWithImages, walkthroughCards } from "../../lib/images";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import type { ReviewAction } from "../../api/review";
import type { GapAnalysis } from "../../lib/gap";
import type { Graph } from "../../lib/mapTypes";
import type { RejectedClaim } from "../../lib/reviewTypes";
import { newStepForm, type AddStepForm } from "../../lib/addStep";
import { firstNeedingAttention, nextToReview, openSteps } from "../../lib/review";
import { shortcutFor, stepAlong } from "../../lib/shortcuts";
import { asView, inView, type AsView } from "../../lib/views";
import { AddStepPanel } from "./AddStepPanel";
import { DetailPanel } from "./DetailPanel";
import { EditPanel } from "./EditPanel";
import { HeaderStrip } from "./HeaderStrip";
import { SourcePanel, type OpenPassage } from "./SourcePanel";
import { KeyboardShortcuts } from "./KeyboardShortcuts";
import { RefreshDialog } from "./RefreshDialog";
import { ShortcutsDialog } from "./ShortcutsDialog";
import { TableView } from "./TableView";
import { WorkbenchTabs } from "./WorkbenchTabs";
import { HowToReview } from "./HowToReview";
import { useFitScale } from "./useFitScale";
import { useLens } from "./useLens";
import "./review.css";

const STEPS = new Set(["activity", "decision", "approval"]);
const MAX_STEPS = 25;
const MAX_LANES = 6;

export interface WorkbenchProps {
  engagementId: string;
  versionId: string;
  /** The screen's name (Review, Published), for its heading. */
  title: string;
  /** The banner above the workbench, given the map and the selection. */
  banner: (graph: Graph, selectedId: string | null, select: (id: string | null) => void) => ReactNode;
  /** Shown under the tabs (the Published screen's change log). */
  below?: ReactNode;
}

/** The roles in the combined map's lane order: the RACI matrix is the same in either view. */
function laneOrder(graph: Graph): string[] {
  return graph.roles
    .filter((r) => r.lane_order !== null)
    .sort((a, b) => (a.lane_order ?? 0) - (b.lane_order ?? 0))
    .map((r) => r.id);
}

/** The toolbar's "n open gap findings" chip (PRD §5.7.7 item 11): no map marker is added. */
function openGapChip(analyses: readonly GapAnalysis[], to: string): ReactNode {
  const open = analyses.filter((a) => a.status === "draft_report").reduce((n, a) => n + a.counts.open, 0);
  if (open === 0) return null;
  return (
    <Link className="chip chip--decision gap-chip" to={to}>
      {plural(open, "open gap finding")}
    </Link>
  );
}

/**
 * The review workbench (PRD §5.6-§5.9): header strip, map or table, tabs and the panel, for one
 * version. A draft can be reviewed; a published version is the same view, read-only (§5.9).
 */
export function Workbench({ engagementId, versionId, title, banner, below }: WorkbenchProps) {
  const [params, setParams] = useSearchParams();
  // As done by default (§3.12.11); the view and Show the other view live in the address.
  const shown: AsView = asView(params.get("as"));
  const showOther = params.get("other") === "1";
  const graph = useGraph(versionId);
  const viewGraph = useGraph(versionId, shown); // the header strip's cycle time is per view
  const layout = useLayout(versionId, shown, showOther);
  const pictures = useVersionImages(versionId);
  const analyses = useGapAnalyses(versionId);
  const navigate = useNavigate();
  const gapPath = engagementPath(engagementId, "gap_analysis");
  const selectedId = params.get("step");
  const [lens, setLens] = useLens();
  const [zoom, setZoom] = useState<Zoom>("fit");
  const [mapBox, fit] = useFitScale(layout.data?.canvas.w ?? 0);
  const reviewStep = useReviewStep(versionId ?? "", engagementId);
  // The source viewer replaces the panel's content; it belongs to the step it was opened from
  // (or to no step, opened from a rejected claim) and closes when the selection changes.
  const [viewing, setViewing] = useState<{ step: string | null; card: OpenPassage } | null>(null);
  const openCard = viewing && viewing.step === selectedId ? viewing.card : null;
  // The edit form, like the viewer, belongs to the step it was opened on.
  const [editingId, setEditingId] = useState<string | null>(null);
  const editing = editingId !== null && editingId === selectedId;
  const stopEditing = useCallback(() => setEditingId(null), []);
  // Add missing step replaces the panel content until it is added or cancelled.
  const [adding, setAdding] = useState<AddStepForm | null>(null);
  const stopAdding = useCallback(() => setAdding(null), []);
  const view: MapView = params.get("view") === "table" ? "table" : "map";
  const [helpOpen, setHelpOpen] = useState(false);
  const [refreshOpen, setRefreshOpen] = useState(false);

  function select(id: string | null) {
    setAdding(null);
    setViewing(null);
    const element = id ? graph.data?.elements.find((e) => e.id === id) : undefined;
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (id) next.set("step", id);
        else next.delete("step");
        // A step only in the other view, not drawn here: show its view, so it is never out of reach.
        const view = asView(current.get("as"));
        if (element && !inView(element, view) && current.get("other") !== "1") {
          if (view === "done") next.set("as", "documented");
          else next.delete("as");
        }
        return next;
      },
      { replace: true },
    );
  }

  function setShown(next: AsView) {
    setParams(
      (current) => {
        const params = new URLSearchParams(current);
        if (next === "documented") params.set("as", "documented");
        else params.delete("as");
        return params;
      },
      { replace: true },
    );
  }

  function setShowOther(show: boolean) {
    setParams(
      (current) => {
        const params = new URLSearchParams(current);
        if (show) params.set("other", "1");
        else params.delete("other");
        return params;
      },
      { replace: true },
    );
  }

  const failed = [graph, layout].find((q) => q.isError);
  if (failed) {
    return (
      <main className="screen" aria-labelledby="review-title">
        <h1 id="review-title">{title}</h1>
        <ErrorState
          title="The map couldn't be loaded"
          message={messageOf(failed.error)}
          details={copyDetailsOf(failed.error)}
          onRetry={() => void failed.refetch()}
        />
      </main>
    );
  }

  if (!graph.data || !layout.data) {
    return (
      <main className="screen" aria-labelledby="review-title" aria-busy="true">
        <h1 id="review-title">{title}</h1>
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
  const lanes = drawing.lanes.length;
  // The caption counts what this view draws (ghosted steps belong to the other view).
  const drawn = new Set(drawing.nodes.filter((n) => !n.ghost).map((n) => n.id));
  const viewSteps = steps.filter((e) => drawn.has(e.id)).length;
  const start = firstNeedingAttention(g);
  const editable = g.version.state === "draft";
  const walkthrough = walkthroughCards(g.elements, pictures.data ?? []);

  function act(action: ReviewAction) {
    if (!selected) return;
    const id = selected.id;
    reviewStep.reset();
    reviewStep.mutate(
      { elementId: id, action },
      { onError: () => select(id) }, // back to the step, shown as it was, with the message
    );
    // Auto-advance after Confirm or Reject (PRD §5.7.5); Restore stays on the step.
    if (action !== "restore") select(nextToReview(g, id));
  }

  function setView(next: MapView) {
    setParams(
      (current) => {
        const params = new URLSearchParams(current);
        if (next === "table") params.set("view", "table");
        else params.delete("view");
        return params;
      },
      { replace: true },
    );
  }

  /** Where Add missing step puts the new step: after the selected step, else after the start. */
  function addAfter(): string {
    if (selected && selected.kind !== "end" && selected.review_status !== "rejected") return selected.id;
    return g.elements.find((e) => e.kind === "start")?.id ?? "";
  }

  // The keyboard (PRD §5.8).
  function onShortcut(event: KeyboardEvent) {
    if (helpOpen || refreshOpen || event.defaultPrevented) return;
    // Keys pressed inside a popover or dialog belong to it (the quality card, the More menu).
    if (event.target instanceof Element && event.target.closest('[role="dialog"]')) return;
    const shortcut = shortcutFor(event);
    if (!shortcut) return;
    const busy = adding !== null || editing; // a form is open: only lenses and help
    const step = selected && STEPS.has(selected.kind) ? selected : null;
    switch (shortcut.kind) {
      case "lens":
        setLens(shortcut.lens);
        break;
      case "help":
        setHelpOpen(true);
        break;
      case "close":
        if (openCard) setViewing(null); // the edit and add forms close themselves
        return;
      case "next":
      case "previous":
        if (busy) return;
        select(stepAlong(g.elements.map((e) => e.id), selectedId, shortcut.kind === "next" ? 1 : -1));
        break;
      case "confirm":
      case "reject":
        if (busy || !editable || step?.review_status !== "draft") return;
        act(shortcut.kind);
        break;
      case "edit":
        if (busy || !editable || !step || step.review_status === "rejected") return;
        reviewStep.reset();
        setEditingId(step.id);
        break;
    }
    event.preventDefault();
  }

  function openClaim(claim: RejectedClaim) {
    select(null);
    setViewing({ step: null, card: { ...claim, quote: "" } });
  }

  function addFromClaim(claim: RejectedClaim) {
    const passage = { id: claim.segment_id ?? "", anchor: claim.anchor, source_name: claim.source_name, text: "" };
    setAdding(newStepForm(g, addAfter(), passage));
  }

  function saved(id: string) {
    setEditingId(null);
    select(nextToReview(g, id)); // auto-advance after Save (PRD §5.7.5)
  }

  return (
    <div className="review">
      <KeyboardShortcuts onKey={onShortcut} />
      <ShortcutsDialog open={helpOpen} onClose={() => setHelpOpen(false)} />
      <RefreshDialog
        open={refreshOpen}
        engagementId={engagementId}
        versionId={g.version.id}
        versionLabel={g.version.label}
        kept={steps.filter((e) => e.review_status !== "draft").length}
        onClose={() => setRefreshOpen(false)}
      />
      {banner(g, selected?.id ?? null, select)}
      <div className="review__body">
        <main className="review__main" aria-labelledby="review-title">
          <h1 id="review-title" className="visually-hidden">
            {title}
          </h1>
          <HeaderStrip process={viewGraph.data?.process ?? g.process} />
          <Card className="map-card">
            <MapToolbar
              view={view}
              onView={setView}
              lens={lens}
              onLens={setLens}
              asView={shown}
              onAsView={setShown}
              showOther={showOther}
              onShowOther={setShowOther}
              zoom={zoom}
              onZoom={setZoom}
              steps={viewSteps}
              lanes={lanes}
              phases={drawing.phases.length}
              large={viewSteps > MAX_STEPS || lanes > MAX_LANES}
              onAddStep={editable ? () => setAdding(newStepForm(g, addAfter())) : undefined}
              extra={openGapChip(analyses.data ?? [], `${gapPath}?version=${encodeURIComponent(versionId)}`)}
              onRefresh={editable ? () => setRefreshOpen(true) : undefined}
            />
            {view === "table" ? (
              <TableView
                graph={g}
                versionId={g.version.id}
                engagementId={engagementId}
                selectedId={selected?.id ?? null}
                editable={editable}
                onSelect={select}
                onSaved={(id) => select(nextToReview(g, id))}
                onOpenFullEdit={(id) => {
                  select(id);
                  setEditingId(id);
                }}
                onAddStep={() => setAdding(newStepForm(g, addAfter()))}
              />
            ) : (
              <>
                <div ref={mapBox} className={zoom === "full" ? "map-card__canvas map-card__canvas--scroll" : "map-card__canvas"}>
                  <MapStage
                    graph={g}
                    layout={drawing}
                    lens={lens}
                    view={shown}
                    scale={zoom === "fit" ? fit : 1}
                    selectedId={selected?.id ?? null}
                    onSelect={select}
                    withImages={stepsWithImages(pictures.data ?? [])}
                  />
                </div>
                <MapLegend lens={lens} view={shown} showOther={showOther} />
              </>
            )}
          </Card>
          {walkthrough.length > 0 && (
            <Card className="workbench-card">
              <WalkthroughStrip cards={walkthrough} selectedId={selected?.id ?? null} onSelect={select} />
            </Card>
          )}
          <Card className="workbench-card">
            <WorkbenchTabs
              graph={g}
              versionId={g.version.id}
              engagementId={engagementId}
              laneOrder={laneOrder(g)}
              selectedId={selected?.id ?? null}
              editable={editable}
              onSelect={select}
              onOpenPassage={openClaim}
              onAddFromPassage={addFromClaim}
            />
          </Card>
          {below}
        </main>
        <aside
          className="review__panel"
          aria-label={
            adding
              ? "Add missing step"
              : selected && editing
                ? "Edit step"
                : openCard
                  ? "Source"
                  : selected
                    ? "Step details"
                    : "How to review"
          }
        >
          {adding && versionId ? (
            <AddStepPanel
              graph={g}
              initial={adding}
              versionId={versionId}
              engagementId={engagementId}
              onAdded={(id) => select(id)}
              onCancel={stopAdding}
            />
          ) : selected && editing && versionId ? (
            <EditPanel
              element={selected}
              laneName={roles.get(selected.lane_role_id ?? "") ?? ""}
              phaseName={phases.get(selected.phase_id ?? "") ?? ""}
              roles={g.roles}
              versionId={versionId}
              engagementId={engagementId}
              onSaved={() => saved(selected.id)}
              onCancel={stopEditing}
            />
          ) : openCard ? (
            <SourcePanel
              card={openCard}
              backLabel={selected ? selected.label : "how to review"}
              onBack={() => setViewing(null)}
            />
          ) : selected ? (
            <DetailPanel
              element={selected}
              typicalResponses={g.edges.filter((e) => e.from === selected.id && e.typical).map((e) => e.label)}
              laneName={roles.get(selected.lane_role_id ?? "") ?? ""}
              phaseName={phases.get(selected.phase_id ?? "") ?? ""}
              review={
                editable
                  ? {
                      busy: reviewStep.isPending,
                      error: reviewStep.error,
                      onAction: act,
                      onEdit: () => {
                        reviewStep.reset();
                        setEditingId(selected.id);
                      },
                    }
                  : undefined
              }
              images={{ versionId: g.version.id, engagementId, editable }}
              onOpenEvidence={(card) => setViewing({ step: selected.id, card })}
              onOpenGapReport={(analysisId) =>
                void navigate(`${gapPath}?analysis=${encodeURIComponent(analysisId)}`)
              }
              onAddAfter={
                editable && selected.kind !== "end" && selected.review_status !== "rejected"
                  ? () => setAdding(newStepForm(g, selected.id))
                  : undefined
              }
              onClose={() => select(null)}
            />
          ) : (
            <div className="panel-stack">
              {openSteps(g) === 0 && editable && <AllReviewed />}
              <HowToReview readOnly={!editable} onStart={start && editable ? () => select(start) : null} />
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
