import { useEffect, useRef, type ReactNode } from "react";
import { quoteRange } from "../../lib/quote";
import { Button, Chip } from "../common";

export interface ViewerPassage {
  id: string;
  anchor: string;
  speaker_role: string | null;
  text: string;
  instruction_like: boolean;
}

export interface SourceViewerProps {
  kind: string;
  name: string;
  /** Mono file facts: format, version date, controlled copy. */
  meta: string;
  passages: readonly ViewerPassage[];
  targetId: string;
  quote: string;
  backLabel: string;
  onBack: () => void;
  /** Pick mode (Add missing step): a "Use this passage" button on each passage. */
  onPick?: ((passage: ViewerPassage) => void) | undefined;
  pickedIds?: readonly string[] | undefined;
  /** Below the passages, e.g. "Show more passages". */
  footer?: ReactNode;
}

const INSTRUCTION_LIKE = "Instruction-like text. Treated as data and ignored.";

function Highlighted({ text, quote }: { text: string; quote: string }) {
  const range = quoteRange(text, quote);
  if (!range) return <>{text}</>;
  const [start, end] = range;
  return (
    <>
      {text.slice(0, start)}
      <mark className="viewer-quote">{text.slice(start, end)}</mark>
      {text.slice(end)}
    </>
  );
}

/** The nearest ancestor that scrolls (the panel), so only it moves, never the whole page. */
function scroller(element: HTMLElement): HTMLElement | null {
  for (let parent = element.parentElement; parent; parent = parent.parentElement) {
    const { overflowY } = getComputedStyle(parent);
    if (overflowY === "auto" || overflowY === "scroll") return parent;
  }
  return null;
}

/**
 * A source opened at one passage, inside the detail panel (PRD §5.7.8): the target passage is
 * framed, the exact quote highlighted, and the panel scrolls to it with its own scrollTop.
 */
export function SourceViewer({
  kind,
  name,
  meta,
  passages,
  targetId,
  quote,
  backLabel,
  onBack,
  onPick,
  pickedIds = [],
  footer,
}: SourceViewerProps) {
  const target = useRef<HTMLLIElement>(null);
  useEffect(() => {
    const element = target.current;
    const box = element ? scroller(element) : null;
    if (!element || !box) return;
    box.scrollTop += element.getBoundingClientRect().top - box.getBoundingClientRect().top - 16;
  }, [targetId]);

  return (
    <section className="panel-viewer" aria-labelledby="panel-viewer-title">
      <button type="button" className="btn btn--link" onClick={onBack}>
        ← Back to {backLabel}
      </button>
      <header className="panel-viewer__header">
        <p className="panel-header__overline">{kind}</p>
        <h2 id="panel-viewer-title" className="panel-viewer__title">
          {name}
        </h2>
        <p className="panel-viewer__meta mono">{meta}</p>
      </header>
      <ol className="viewer-passages" aria-label="Passages">
        {passages.map((p) => {
          const isTarget = p.id === targetId;
          return (
            <li
              key={p.id}
              ref={isTarget ? target : undefined}
              className={isTarget ? "viewer-passage viewer-passage--target" : "viewer-passage"}
              aria-current={isTarget ? "true" : undefined}
            >
              <span className="viewer-passage__anchor mono">{p.anchor}</span>
              <div>
                {p.speaker_role && <span className="viewer-passage__role">{p.speaker_role}</span>}
                <p>{isTarget ? <Highlighted text={p.text} quote={quote} /> : p.text}</p>
                {p.instruction_like && <Chip dashed>{INSTRUCTION_LIKE}</Chip>}
                {onPick &&
                  (pickedIds.includes(p.id) ? (
                    <p className="viewer-passage__picked">Picked for the new step</p>
                  ) : (
                    <Button onClick={() => onPick(p)} aria-label={`Use this passage, ${p.anchor}`}>
                      Use this passage
                    </Button>
                  ))}
              </div>
            </li>
          );
        })}
      </ol>
      {footer}
      <p className="panel-viewer__footer">
        Speaker names are replaced by roles. Quotes stay in the app and never appear in exports.
      </p>
    </section>
  );
}
