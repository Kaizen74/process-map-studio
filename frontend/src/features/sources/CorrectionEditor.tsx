import { useState } from "react";
import type { Segment } from "../../api/types";
import { Button, Chip, ErrorState, Skeleton, TextAreaField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useCorrectSegment, useRawSegments } from "../../hooks/useSources";
import { copyDetailsOf, messageOf } from "../../lib/errors";

const BAD_TEXT = "Please keep the passage between 1 and 5,000 characters.";

function PassageEditor({
  segment,
  sourceId,
  onDone,
}: {
  segment: Segment;
  sourceId: string;
  onDone: () => void;
}) {
  const [text, setText] = useState(segment.text);
  const [error, setError] = useState<string | null>(null);
  const save = useCorrectSegment(sourceId);
  const toast = useToast();

  function onSave() {
    const clean = text.trim();
    if (!clean || clean.length > 5000) {
      setError(BAD_TEXT);
      return;
    }
    save.mutate(
      { id: segment.id, text: clean },
      {
        onSuccess: () => {
          toast("Passage corrected.");
          onDone();
        },
        onError: (e) => setError(messageOf(e)),
      },
    );
  }

  return (
    <div className="stack">
      <TextAreaField
        label={`Text of passage ${segment.anchor}`}
        value={text}
        onChange={setText}
        error={error}
        rows={4}
      />
      <div className="setup-form__actions">
        <Button variant="primary" onClick={onSave}>
          {save.isPending ? "Saving…" : "Save correction"}
        </Button>
        <Button onClick={onDone}>Cancel</Button>
      </div>
    </div>
  );
}

/**
 * Transcript correction editor (PRD §5.4, §3.8 G10): the passages exactly as stored, with speaker
 * labels. One of the three owner-only places where names are shown.
 */
export function CorrectionEditor({ sourceId }: { sourceId: string }) {
  const raw = useRawSegments(sourceId, true);
  const [editing, setEditing] = useState<string | null>(null);
  const passages = (raw.data?.pages ?? []).flatMap((p) => p.segments);

  if (raw.isError) {
    return (
      <ErrorState
        title="The passages couldn't be loaded for correcting"
        message={messageOf(raw.error)}
        details={copyDetailsOf(raw.error)}
        onRetry={() => void raw.refetch()}
      />
    );
  }
  if (raw.isPending) {
    return (
      <div className="stack" aria-busy="true">
        <Skeleton height="18px" />
        <Skeleton height="18px" width="80%" />
      </div>
    );
  }
  return (
    <div data-owner-only="correction-editor" className="stack">
      <p className="viewer__note">
        Fix words the transcript got wrong. Your corrections are kept if the file is read again. Names shown here
        are hidden everywhere else.
      </p>
      <ol className="passages" aria-label="Passages to correct">
        {passages.map((segment) => (
          <li key={segment.id} className="passage">
            <span className="passage__anchor mono">{segment.anchor}</span>
            <div className="passage__body">
              {segment.speaker_label && <span className="passage__role">{segment.speaker_label}</span>}
              {editing === segment.id ? (
                <PassageEditor segment={segment} sourceId={sourceId} onDone={() => setEditing(null)} />
              ) : (
                <div className="passage__row">
                  <p className="passage__text">{segment.text}</p>
                  {segment.corrected && <Chip>Corrected</Chip>}
                  <Button
                    variant="link"
                    aria-label={`Correct passage ${segment.anchor}`}
                    onClick={() => setEditing(segment.id)}
                  >
                    Correct
                  </Button>
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
      {raw.hasNextPage && (
        <Button onClick={() => void raw.fetchNextPage()}>
          {raw.isFetchingNextPage ? "Loading…" : "Show more passages"}
        </Button>
      )}
    </div>
  );
}
