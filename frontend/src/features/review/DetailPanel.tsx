import {
  AiFlag,
  ConfidenceBreakdown,
  ConstraintList,
  DecisionRights,
  EvidenceCard,
  HandoffTime,
  KnowledgeRisk,
  Kpi,
  PanelHeader,
  PanelSection,
  ReviewActions,
  RoleAccountability,
} from "../../components/panel";
import { ErrorState, Skeleton } from "../../components/common";
import { useElement } from "../../hooks/useReview";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import type { EvidenceCard as Card, GraphElement } from "../../lib/mapTypes";
import type { ReviewAction } from "../../api/review";
import { ImagesSection } from "./ImagesSection";

export interface DetailPanelProps {
  element: GraphElement;
  laneName: string;
  phaseName: string;
  /** Review actions; omitted where the version can't change. */
  review?:
    | {
        busy: boolean;
        error: unknown;
        onAction: (action: ReviewAction) => void;
        onEdit: () => void;
      }
    | undefined;
  /** Section 10, pictures: always shown on a step; changed only where the version is a draft. */
  images: { versionId: string; engagementId: string; editable: boolean };
  onOpenEvidence: (card: Card) => void;
  /** Add missing step after this one; omitted where it can't be (the end, a rejected step, not a draft). */
  onAddAfter?: (() => void) | undefined;
  onClose: () => void;
}

const STEPS = new Set(["activity", "decision", "approval"]);

/** The selected step with its review actions (PRD §5.7.5, §5.7.7). */
export function DetailPanel({
  element,
  laneName,
  phaseName,
  review,
  images,
  onOpenEvidence,
  onAddAfter,
  onClose,
}: DetailPanelProps) {
  const detail = useElement(element.id);
  const step = STEPS.has(element.kind);
  return (
    <div className="panel-stack">
      <PanelHeader element={element} laneName={laneName} phaseName={phaseName} />
      {!step && (
        <p className="inline-note">
          {element.kind === "start" ? "Where the process starts" : "Where the process ends"}, from the engagement's
          scope. It has no evidence of its own.
        </p>
      )}
      {step && review && (
        <ReviewActions
          status={element.review_status}
          needsCheck={element.needs_check}
          busy={review.busy}
          onConfirm={() => review.onAction("confirm")}
          onReject={() => review.onAction("reject")}
          onRestore={() => review.onAction("restore")}
          onEdit={review.onEdit}
        />
      )}
      {step && review?.error != null && (
        <p className="panel-danger" role="alert">
          {messageOf(review.error)} The step is shown as it was.
        </p>
      )}
      {step && detail.isPending && (
        <div className="stack" aria-busy="true" style={{ width: "100%" }}>
          <Skeleton height="96px" />
          <Skeleton height="96px" />
        </div>
      )}
      {step && detail.isError && (
        <ErrorState
          title="The step's details couldn't be loaded"
          message={messageOf(detail.error)}
          details={copyDetailsOf(detail.error)}
          onRetry={() => void detail.refetch()}
        />
      )}
      {step && detail.data && (
        <>
          {detail.data.provenance === "R" ? (
            <PanelSection title="External reference">
              <p>{detail.data.r_reference || "No reference recorded."}</p>
            </PanelSection>
          ) : (
            <PanelSection title="Evidence" note="opens at the exact passage">
              <ul className="evidence-list">
                {detail.data.evidence.map((card, i) => (
                  <li key={`${card.source_id}-${card.segment_id ?? "silent"}-${i}`}>
                    <EvidenceCard card={card} onOpen={onOpenEvidence} />
                  </li>
                ))}
              </ul>
            </PanelSection>
          )}
          <ConfidenceBreakdown element={detail.data} />
          <RoleAccountability element={detail.data} />
          <DecisionRights element={detail.data} />
          <HandoffTime element={detail.data} />
          <Kpi element={detail.data} />
          <ConstraintList element={detail.data} />
          <KnowledgeRisk element={detail.data} />
          <AiFlag element={detail.data} />
        </>
      )}
      {step && (
        <ImagesSection
          elementId={element.id}
          versionId={images.versionId}
          engagementId={images.engagementId}
          editable={images.editable}
        />
      )}
      {onAddAfter && (
        <button type="button" className="btn btn--link" onClick={onAddAfter}>
          Add a missing step after this one
        </button>
      )}
      <button type="button" className="btn btn--link" onClick={onClose}>
        Close details
      </button>
    </div>
  );
}
