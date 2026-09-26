import { Link } from "react-router";
import { Card, ErrorState, Skeleton } from "../../components/common";
import { useRejectedClaims } from "../../hooks/useDraft";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { plural } from "../../lib/format";

/** Rejected claims (PRD §3.8 G12, §5.4): claims that failed a check and never reach the map. */
export function RejectedClaimsList({ engagementId, versionId }: { engagementId: string; versionId: string }) {
  const rejected = useRejectedClaims(versionId);
  const data = rejected.data;
  return (
    <Card title={data ? `Rejected claims (${data.total})` : "Rejected claims"}>
      {rejected.isPending && <Skeleton height="60px" />}
      {rejected.isError && (
        <ErrorState
          title="The rejected claims couldn't be loaded"
          message={messageOf(rejected.error)}
          details={copyDetailsOf(rejected.error)}
          onRetry={() => void rejected.refetch()}
        />
      )}
      {data && (
        <>
          <p className="rejected__intro">
            {data.total === 0
              ? "No claims were rejected. Every claim Claude made was found in your documents."
              : `${plural(data.total, "claim")} failed a check and will never appear on the map.`}{" "}
            {plural(data.scrub_count, "name")} replaced by roles;{" "}
            {plural(data.instruction_like_count, "instruction-like passage")} treated as data and ignored.
          </p>
          {data.items.length > 0 && (
            <ul className="rejected">
              {data.items.map((item) => (
                <li key={item.id} className="rejected__item">
                  <p className="rejected__claim">
                    <s>{item.claim_text}</s>
                  </p>
                  <p className="rejected__reason">{item.reason}</p>
                  <p className="rejected__meta">
                    <span className="mono">
                      {item.guardrail} · {item.stage}
                    </span>{" "}
                    · {item.source_name}
                    {item.anchor && (
                      <>
                        {" "}
                        · <span className="mono">{item.anchor}</span>
                      </>
                    )}{" "}
                    ·{" "}
                    {item.passage_available ? (
                      <Link to={`/engagements/${encodeURIComponent(engagementId)}/sources?source=${encodeURIComponent(item.source_id)}`}>
                        Open source
                      </Link>
                    ) : (
                      <span>Passage missing</span>
                    )}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  );
}
