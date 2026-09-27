import { ErrorState, Skeleton } from "../../components/common";
import { SourceViewer } from "../../components/panel";
import { useSegmentsAround } from "../../hooks/useReview";
import { useSource } from "../../hooks/useSources";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { SOURCE_KINDS } from "../../lib/panelText";

/** The passage to open: from an evidence card or a rejected claim. */
export interface OpenPassage {
  source_id: string;
  source_name: string;
  segment_id: string | null;
  quote: string;
}

export interface SourcePanelProps {
  card: OpenPassage;
  /** What "← Back to …" returns to. */
  backLabel: string;
  onBack: () => void;
}

/** A source opened at one passage in the panel (PRD §5.7.8). */
export function SourcePanel({ card, backLabel, onBack }: SourcePanelProps) {
  const source = useSource(card.source_id);
  const page = useSegmentsAround(card.source_id, card.segment_id);
  const failed = source.isError ? source : page.isError ? page : null;
  if (failed) {
    return (
      <div className="panel-stack">
        <button type="button" className="btn btn--link" onClick={onBack}>
          ← Back to {backLabel}
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
      backLabel={backLabel}
      onBack={onBack}
    />
  );
}
