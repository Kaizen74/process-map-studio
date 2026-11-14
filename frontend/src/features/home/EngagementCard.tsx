import { Link } from "react-router";
import type { EngagementSummary } from "../../api/types";
import { Button, Chip } from "../../components/common";
import { engagementPath } from "../../lib/engagementSteps";
import { formatDate, plural, sentence } from "../../lib/format";

export interface EngagementCardProps {
  engagement: EngagementSummary;
  onDelete: (engagement: EngagementSummary) => void;
}

/** One engagement on Home (PRD §5.4). The whole card opens the next recommended screen. */
export function EngagementCard({ engagement, onDelete }: EngagementCardProps) {
  const { latest_version: version, review_progress: progress } = engagement;
  const percent = progress.total ? Math.round((progress.reviewed / progress.total) * 100) : 0;
  return (
    <article className="engagement-card">
      <div className="engagement-card__top">
        <h2 className="engagement-card__title">
          <Link to={engagementPath(engagement.id)} className="engagement-card__link">
            {engagement.name}
          </Link>
          {engagement.country && <span className="engagement-card__country"> · {engagement.country}</span>}
        </h2>
        {version ? (
          <Chip tone={version.state === "published" ? "good" : "neutral"} mono>
            {sentence(version.state)} {version.label}
          </Chip>
        ) : (
          <Chip dashed>No draft yet</Chip>
        )}
      </div>
      {engagement.process_name && engagement.process_name !== engagement.name && (
        <p className="engagement-card__process">{engagement.process_name}</p>
      )}
      {progress.total > 0 ? (
        <div className="engagement-card__progress">
          <div className="progress-bar" aria-hidden="true">
            <div className="progress-bar__fill" style={{ width: `${percent}%` }} />
          </div>
          <span className="engagement-card__meta">
            <span className="mono">{progress.reviewed}</span> of <span className="mono">{progress.total}</span>{" "}
            reviewed
          </span>
        </div>
      ) : (
        <span className="engagement-card__meta">Nothing to review until the first draft.</span>
      )}
      <div className="engagement-card__footer">
        <span className="engagement-card__meta">
          {plural(engagement.sources_count, "source")} · last updated{" "}
          <span className="mono">{formatDate(engagement.updated_at)}</span>
        </span>
        <Button
          variant="danger"
          className="engagement-card__delete"
          aria-label={`Delete ${engagement.name}`}
          onClick={() => onDelete(engagement)}
        >
          Delete
        </Button>
      </div>
    </article>
  );
}
