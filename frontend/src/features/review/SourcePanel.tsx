import { ErrorState, Skeleton } from "../../components/common";
import { SourceViewer } from "../../components/panel";
import { useSegmentsAround } from "../../hooks/useReview";
import { useSource } from "../../hooks/useSources";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import type { EvidenceCard } from "../../lib/mapTypes";
import { SOURCE_KINDS } from "../../lib/panelText";

export interface SourcePanelProps {
  card: EvidenceCard;
  stepLabel: string;
  onBack: () => void;
}

/** The evidence card's source, opened at its passage in the panel (PRD §5.7.8). */
export function SourcePanel({ card, stepLabel, onBack }: SourcePanelProps) {
  const source = useSource(card.source_id);
  const page = useSegmentsAround(card.source_id, card.segment_id);
  const failed = source.isError ? source : page.isError ? page : null;
  if (failed) {
    return (
      <div className="panel-stack">
        <button type="button" className="btn btn--link" onClick={onBack}>
          ← Back to {stepLabel}
        </button>
        <ErrorState
          title="This source couldn't be opened"
          message={messageOf(failed.error)}
          details={copyDetailsOf(failed.error)}
          onRetry={() => void failed.refetch()}
        />
      </div>
    );
  }
  if (!source.data || !page.data) {
    return (
      <div className="stack" aria-busy="true">
        <Skeleton height="48px" />
        <Skeleton height="160px" />
      </div>
    );
  }
  const s = source.data;
  const meta = [s.format, s.version_date && `version ${s.version_date}`, s.controlled_copy && "controlled copy"]
    .filter(Boolean)
    .join(" · ");
  return (
    <SourceViewer
      kind={SOURCE_KINDS[s.kind] ?? "Document"}
      name={card.source_name}
      meta={meta}
      passages={page.data.segments}
      targetId={card.segment_id ?? ""}
      quote={card.quote}
      backLabel={stepLabel}
      onBack={onBack}
    />
  );
}
