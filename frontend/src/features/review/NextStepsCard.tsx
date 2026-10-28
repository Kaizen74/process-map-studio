import { useState } from "react";
import type { Graph } from "../../api/types";
import {
  Button,
  Card,
  Dialog,
  ErrorState,
  Skeleton,
} from "../../components/common";
import { NextStepsList } from "../../components/quality";
import { useToast } from "../../components/shell";
import {
  useAcceptRemaining,
  useDiscardSuggestions,
  useNextSteps,
} from "../../hooks/useReview";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { exportUrl } from "../../lib/exports";
import { plural } from "../../lib/format";
import { nextToReview } from "../../lib/review";
import type { NextStep } from "../../lib/reviewTypes";

export interface NextStepsCardProps {
  graph: Graph;
  engagementId: string;
  /** Open a step (the map scrolls to it and its panel opens). */
  onSelect: (elementId: string) => void;
}

const SHOWN = 3;
const WHOLE_MAP = "";

/**
 * "What to do next" on a draft's Review screen (2026-10-28, Eric: "not sure what I need to do
 * when"): at most three things, in order, each with one button; and the whole draft map to
 * download before anything is reviewed ("see the whole picture at any one time").
 */
export function NextStepsCard({
  graph,
  engagementId,
  onSelect,
}: NextStepsCardProps) {
  const versionId = graph.version.id;
  const next = useNextSteps(versionId);
  const accept = useAcceptRemaining(versionId, engagementId);
  const discard = useDiscardSuggestions(versionId, engagementId);
  const toast = useToast();
  const [accepting, setAccepting] = useState<NextStep | null>(null);
  const [scope, setScope] = useState(WHOLE_MAP);
  const [discarding, setDiscarding] = useState<NextStep | null>(null);

  const waiting = (phaseId: string) =>
    graph.elements.filter(
      (e) =>
        e.kind !== "start" &&
        e.kind !== "end" &&
        e.review_status === "draft" &&
        (!phaseId || e.phase_id === phaseId),
    ).length;

  function confirmAccept() {
    accept.mutate(scope || undefined, {
      onSuccess: (result) => {
        setAccepting(null);
        const left = result.skipped.length
          ? ` ${plural(result.skipped.length, "step")} still need you: ${result.skipped.map((s) => s.label).join(", ")}.`
          : "";
        toast(`Accepted ${plural(result.accepted, "step")} as drafted.${left}`);
      },
    });
  }

  function confirmDiscard() {
    discard.mutate(undefined, {
      onSuccess: (result) => {
        setDiscarding(null);
        toast(`Discarded ${plural(result.discarded, "suggested picture")}.`);
      },
    });
  }

  function actions(step: NextStep) {
    if (step.key === "review_steps") {
      const first = nextToReview(graph, "");
      return (
        <>
          {first && (
            <Button onClick={() => onSelect(first)}>
              Review the next step
            </Button>
          )}
          {step.bulk > 0 && (
            <Button
              onClick={() => {
                accept.reset();
                setScope(WHOLE_MAP);
                setAccepting(step);
              }}
            >
              Accept {plural(step.bulk, "step")} as drafted…
            </Button>
          )}
        </>
      );
    }
    if (step.key === "pictures") {
      return (
        <Button
          onClick={() => {
            discard.reset();
            setDiscarding(step);
          }}
        >
          Discard all {step.count} suggested…
        </Button>
      );
    }
    if (step.key === "merges")
      return (
        <p className="next-steps__detail">
          The Merge decisions tab below lists them.
        </p>
      );
    if (step.key === "publish")
      return (
        <p className="next-steps__detail">
          Use Publish at the top of the screen.
        </p>
      );
    return null;
  }

  const download = (
    <a
      className="btn btn--secondary"
      href={exportUrl(versionId, "html")}
      download
    >
      Download draft map
    </a>
  );
  return (
    <Card
      className="next-steps-card"
      title="What to do next"
      description="The draft map is complete as drafted; nothing is published until every step is reviewed."
      actions={download}
    >
      {next.isPending && <Skeleton height="96px" />}
      {next.isError && (
        <ErrorState
          title="What's left couldn't be worked out"
          message={messageOf(next.error)}
          details={copyDetailsOf(next.error)}
          onRetry={() => void next.refetch()}
        />
      )}
      {next.data && (
        <NextStepsList
          steps={next.data.steps}
          limit={SHOWN}
          onSelect={onSelect}
          actions={actions}
        />
      )}

      <Dialog
        open={accepting !== null}
        title="Accept steps as drafted?"
        description="They are confirmed as Claude drafted them and locked against refreshing the draft, as if you confirmed each one. Steps with a problem to fix or only partly supported evidence stay for you."
        onClose={() => setAccepting(null)}
        actions={
          <>
            <Button onClick={() => setAccepting(null)}>Cancel</Button>
            <Button variant="primary" onClick={confirmAccept}>
              {accept.isPending ? "Accepting…" : "Accept"}
            </Button>
          </>
        }
      >
        <fieldset className="next-steps__scope">
          <legend>Which steps</legend>
          <label>
            <input
              type="radio"
              name="accept-scope"
              checked={scope === WHOLE_MAP}
              onChange={() => setScope(WHOLE_MAP)}
            />
            The whole map ({plural(waiting(WHOLE_MAP), "step")} waiting)
          </label>
          {graph.phases
            .filter((p) => waiting(p.id) > 0)
            .map((p) => (
              <label key={p.id}>
                <input
                  type="radio"
                  name="accept-scope"
                  checked={scope === p.id}
                  onChange={() => setScope(p.id)}
                />
                {p.name} ({plural(waiting(p.id), "step")} waiting)
              </label>
            ))}
        </fieldset>
        {accept.isError && (
          <p className="field__error" role="alert">
            {messageOf(accept.error)}
          </p>
        )}
      </Dialog>

      <Dialog
        open={discarding !== null}
        title={`Discard ${plural(discarding?.count ?? 0, "suggested picture")}?`}
        description="Pictures found in your PDFs that you haven't kept. You can still add a picture to any step yourself."
        onClose={() => setDiscarding(null)}
        actions={
          <>
            <Button onClick={() => setDiscarding(null)}>Cancel</Button>
            <Button variant="danger" onClick={confirmDiscard}>
              {discard.isPending ? "Discarding…" : "Discard all"}
            </Button>
          </>
        }
      >
        {discard.isError && (
          <p className="field__error" role="alert">
            {messageOf(discard.error)}
          </p>
        )}
      </Dialog>
    </Card>
  );
}
