import { useEffect, useId, useRef } from "react";
import { Button, Chip, ErrorState, Skeleton } from "../../components/common";
import { useSegments, useSource } from "../../hooks/useSources";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { plural } from "../../lib/format";
import { kindLabel, sourceStatus } from "../../lib/sources";

/** Full-width source viewer (PRD §5.4 Sources, §5.7.8): anchored passages, roles never names. */
export function SourceViewer({ sourceId, onClose }: { sourceId: string; onClose: () => void }) {
  const source = useSource(sourceId);
  const segments = useSegments(sourceId);
  const titleId = useId();
  const region = useRef<HTMLElement>(null);

  useEffect(() => {
    region.current?.scrollIntoView?.({ block: "start" });
  }, [sourceId]);

  const data = source.data;
  const pages = segments.data?.pages ?? [];
  const passages = pages.flatMap((p) => p.segments);
  const total = pages[0]?.total ?? 0;

  return (
    <section ref={region} className="viewer" aria-labelledby={titleId}>
      <div className="viewer__header">
        <div>
          <h2 id={titleId} className="viewer__title">
            {data?.filename ?? "Source"}
          </h2>
          {data && (
            <p className="viewer__meta">
              {kindLabel(data.kind)} · <span className="mono">{data.format}</span> ·{" "}
              {plural(data.segment_count, "passage")}
            </p>
          )}
        </div>
        <div className="viewer__actions">
          {data && (
            <Chip tone={sourceStatus(data).tone} dashed={sourceStatus(data).dashed}>
              {sourceStatus(data).label}
            </Chip>
          )}
          <Button onClick={onClose}>Close viewer</Button>
        </div>
      </div>

      {data?.error && <p className="viewer__note">{data.error}</p>}
      {data && data.ocr_pages.length > 0 && (
        <p className="viewer__note">
          {data.ocr_pages.length === 1 ? "Page" : "Pages"} <span className="mono">{data.ocr_pages.join(", ")}</span>{" "}
          {data.ocr_pages.length === 1 ? "has" : "have"} almost no text (probably scanned). They will be read by OCR
          from build phase P3.
        </p>
      )}
      {data && data.suggested_images > 0 && (
        <p className="viewer__note">
          {plural(data.suggested_images, "image")} found in this file {data.suggested_images === 1 ? "is" : "are"} kept
          as {data.suggested_images === 1 ? "a suggestion" : "suggestions"}. You will review images in build phase P8.
        </p>
      )}

      {(source.isError || segments.isError) && (
        <ErrorState
          title="This source couldn't be shown"
          message={messageOf(source.error ?? segments.error)}
          details={copyDetailsOf(source.error ?? segments.error)}
          onRetry={() => {
            void source.refetch();
            void segments.refetch();
          }}
        />
      )}
      {segments.isPending && !segments.isError && (
        <div className="stack" aria-busy="true">
          <Skeleton height="18px" />
          <Skeleton height="18px" width="80%" />
          <Skeleton height="18px" width="90%" />
        </div>
      )}
      {segments.isSuccess && passages.length === 0 && (
        <p className="viewer__empty">No passages yet. They appear here once the file has been read.</p>
      )}
      {passages.length > 0 && (
        <ol className="passages" aria-label="Passages">
          {passages.map((segment) => (
            <li key={segment.id} className="passage">
              <span className="passage__anchor mono">{segment.anchor}</span>
              <div className="passage__body">
                {segment.speaker_role && <span className="passage__role">{segment.speaker_role}</span>}
                <p className="passage__text">{segment.text}</p>
              </div>
            </li>
          ))}
        </ol>
      )}
      {segments.hasNextPage && (
        <Button onClick={() => void segments.fetchNextPage()}>
          {segments.isFetchingNextPage ? "Loading…" : `Show more passages (${passages.length} of ${total} shown)`}
        </Button>
      )}
      <p className="viewer__footer">
        Speaker names are replaced by roles. Quotes stay in the app and never appear in exports.
      </p>
    </section>
  );
}
