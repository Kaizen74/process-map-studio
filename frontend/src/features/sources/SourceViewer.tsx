import { useEffect, useId, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { Button, Chip, ErrorState, Skeleton } from "../../components/common";
import type { Segment } from "../../api/types";
import { useSegments, useSource } from "../../hooks/useSources";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { engagementPath } from "../../lib/engagementSteps";
import { plural } from "../../lib/format";
import { coverageText, kindLabel, sourceStatus } from "../../lib/sources";
import { CorrectionEditor } from "./CorrectionEditor";

const INSTRUCTION_LIKE = "Instruction-like text. Treated as data and ignored.";

/** Full-width source viewer (PRD §5.4 Sources, §5.7.8): anchored passages, roles never names. */
export function SourceViewer({ sourceId, onClose }: { sourceId: string; onClose: () => void }) {
  const { engagementId = "" } = useParams();
  const source = useSource(sourceId);
  const [uncitedOnly, setUncitedOnly] = useState(false);
  const segments = useSegments(sourceId, uncitedOnly);
  const titleId = useId();
  const region = useRef<HTMLElement>(null);
  const [correcting, setCorrecting] = useState(false);

  useEffect(() => {
    region.current?.scrollIntoView?.({ block: "start" });
  }, [sourceId]);

  const data = source.data;
  const pages = segments.data?.pages ?? [];
  const passages = pages.flatMap((p) => p.segments);
  const total = pages[0]?.total ?? 0;
  const correctable = data?.kind === "interview_transcript" && data.text_status === "ready";
  const coverage = data?.coverage_pct ?? null;
  // Once coverage is measured, a passage the map doesn't cite says so (interviewer turns aside).
  const uncited = (segment: Segment) => coverage !== null && !segment.cited && segment.speaker_role !== "Interviewer";
  // Passages only another flow's claims or questions cite (DECISIONS 94): not missed, set aside.
  const otherFlow = pages[0]?.other_flow ?? 0;

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
          {correctable && (
            <Button onClick={() => setCorrecting((c) => !c)}>{correcting ? "Done correcting" : "Correct the text"}</Button>
          )}
          <Button onClick={onClose}>Close viewer</Button>
        </div>
      </div>

      {data?.error && <p className="viewer__note">{data.error}</p>}
      {data && data.ocr_pages.length > 0 && (
        <p className="viewer__note">
          {data.ocr_pages.length === 1 ? "Page" : "Pages"} <span className="mono">{data.ocr_pages.join(", ")}</span>{" "}
          {data.ocr_pages.length === 1 ? "has" : "have"} almost no text (probably scanned). Claude reads{" "}
          {data.ocr_pages.length === 1 ? "it" : "them"} when you create the draft map.
        </p>
      )}
      {data && data.suggested_images > 0 && (
        <p className="viewer__note">
          {plural(data.suggested_images, "image")} found in this file {data.suggested_images === 1 ? "is" : "are"} kept
          as {data.suggested_images === 1 ? "a suggestion" : "suggestions"}, offered on the steps that cite the same page
          when you create the draft map.
        </p>
      )}
      {data && !correcting && coverage !== null && (
        <div className="coverage">
          <span className="coverage__bar" aria-hidden="true">
            <span className="coverage__fill" style={{ width: `${Math.min(100, Math.max(0, coverage))}%` }} />
          </span>
          <span className="coverage__text">
            <span className="mono">{coverageText(coverage)}</span> cited by the map
          </span>
          <Button aria-pressed={uncitedOnly} onClick={() => setUncitedOnly((on) => !on)}>
            Show uncited passages
          </Button>
        </div>
      )}
      {data && !correcting && coverage !== null && otherFlow > 0 && (
        <p className="viewer__note">
          {plural(otherFlow, "passage")} in this file {otherFlow === 1 ? "is" : "are"} about another flow, so this
          map leaves {otherFlow === 1 ? "it" : "them"} out.{" "}
          <Link to={`${engagementPath(engagementId, "review")}?tab=outside`}>See them under Outside this flow</Link>
        </p>
      )}
      {data && !correcting && coverage === null && data.text_status === "ready" && (
        <p className="viewer__note">How much of this file the map uses is measured after a draft map is made from it.</p>
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
      {correcting && correctable && <CorrectionEditor sourceId={sourceId} />}
      {!correcting && segments.isPending && !segments.isError && (
        <div className="stack" aria-busy="true">
          <Skeleton height="18px" />
          <Skeleton height="18px" width="80%" />
          <Skeleton height="18px" width="90%" />
        </div>
      )}
      {!correcting && segments.isSuccess && passages.length === 0 && (
        <p className="viewer__empty">
          {uncitedOnly
            ? "Every passage in this file is cited by the map."
            : "No passages yet. They appear here once the file has been read."}
        </p>
      )}
      {!correcting && passages.length > 0 && (
        <ol className="passages" aria-label="Passages">
          {passages.map((segment) => (
            <li key={segment.id} className="passage">
              <span className="passage__anchor mono">{segment.anchor}</span>
              <div className="passage__body">
                {segment.speaker_role && <span className="passage__role">{segment.speaker_role}</span>}
                <p className="passage__text">{segment.text}</p>
                {(segment.instruction_like || segment.corrected || uncited(segment)) && (
                  <div className="passage__tags">
                    {uncited(segment) && (segment.other_flow ? <Chip>Other flow</Chip> : <Chip dashed>Uncited</Chip>)}
                    {segment.instruction_like && <Chip dashed>{INSTRUCTION_LIKE}</Chip>}
                    {segment.corrected && <Chip>Corrected</Chip>}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
      {!correcting && segments.hasNextPage && (
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
