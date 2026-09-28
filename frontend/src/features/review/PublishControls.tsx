import { useState } from "react";
import { useNavigate } from "react-router";
import { Button, ErrorState, Popover, Skeleton } from "../../components/common";
import { BlockerList, QualityCardView } from "../../components/quality";
import { useToast } from "../../components/shell";
import { usePublish, useQualityCard } from "../../hooks/useVersions";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { blockersOf, greenCount } from "../../lib/quality";
import type { PublishBlocker } from "../../lib/reviewTypes";

export interface PublishControlsProps {
  versionId: string;
  engagementId: string;
  /** Go to a blocker's step (closes the popover). */
  onSelect: (elementId: string) => void;
}

/**
 * The banner's quality card button ("n of 9 green", PRD §5.7.1) with its popover (§5.7.9), and
 * Publish. A refused publish opens the same popover as "Publish blocked", listing what to fix.
 */
export function PublishControls({ versionId, engagementId, onSelect }: PublishControlsProps) {
  const card = useQualityCard(versionId);
  const publish = usePublish(versionId, engagementId);
  const toast = useToast();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [blockers, setBlockers] = useState<PublishBlocker[] | null>(null);
  const count = card.data ? greenCount(card.data) : null;

  function close() {
    setOpen(false);
    setBlockers(null);
  }

  function tryPublish() {
    publish.reset();
    publish.mutate(undefined, {
      onSuccess: (version) => {
        toast(`Published as ${version.label}. It can no longer change; reopen it to make a new draft.`);
        void navigate(engagementPath(engagementId, "published"));
      },
      onError: (error) => {
        const found = blockersOf(error);
        if (found) {
          setBlockers(found);
          setOpen(true);
        }
      },
    });
  }

  const otherError = publish.error != null && blockersOf(publish.error) === null ? publish.error : null;
  return (
    <>
      <div className="popover-anchor">
        <Button aria-expanded={open} onClick={() => (open ? close() : setOpen(true))}>
          <span
            className={count && count.green === count.total ? "quality-button__dot quality-button__dot--green" : "quality-button__dot"}
            aria-hidden="true"
          />
          {count ? (
            <>
              Quality card: <span className="mono">{count.green}</span> of <span className="mono">{count.total}</span>{" "}
              green
            </>
          ) : (
            "Quality card"
          )}
        </Button>
        <Popover open={open} title={blockers ? "Publish blocked" : "Quality card"} align="end" onClose={close}>
          {blockers && (
            <BlockerList
              blockers={blockers}
              onSelect={(id) => {
                close();
                onSelect(id);
              }}
            />
          )}
          {card.isPending && <Skeleton height="200px" />}
          {card.isError && (
            <ErrorState
              title="The quality card couldn't be worked out"
              message={messageOf(card.error)}
              details={copyDetailsOf(card.error)}
              onRetry={() => void card.refetch()}
            />
          )}
          {card.data && <QualityCardView card={card.data} />}
        </Popover>
      </div>
      <Button variant="primary" onClick={tryPublish}>
        {publish.isPending ? "Publishing…" : "Publish"}
      </Button>
      {otherError != null && (
        <p className="field__error" role="alert">
          {messageOf(otherError)}
        </p>
      )}
    </>
  );
}
