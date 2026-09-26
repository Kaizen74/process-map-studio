import { Card, ErrorState, Skeleton } from "../../components/common";
import { useAiUsage } from "../../hooks/useSettings";
import { AI_CALL_STATUS, aiStageName, durationLabel, groupDigits } from "../../lib/draft";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { formatDateTime, plural } from "../../lib/format";

/** AI usage (PRD §3.4 item 4, §5.4 Settings): one row per call; usage only, never text. */
export function UsageCard() {
  const usage = useAiUsage();
  const data = usage.data;
  return (
    <Card
      title="AI usage"
      className="settings-grid__wide"
      description="Every call the app has made to Claude. Only the stage, model, tokens and time are kept, never your documents."
    >
      {usage.isPending && <Skeleton height="60px" />}
      {usage.isError && (
        <ErrorState
          title="AI usage couldn't be loaded"
          message={messageOf(usage.error)}
          details={copyDetailsOf(usage.error)}
          onRetry={() => void usage.refetch()}
        />
      )}
      {data && data.items.length === 0 && (
        <p className="usage__empty">No AI calls yet. They appear here once you create a draft map.</p>
      )}
      {data && data.items.length > 0 && (
        <>
          <p className="usage__totals">
            All time: {plural(data.totals.calls, "call")} ·{" "}
            <span className="mono">{groupDigits(data.totals.input_tokens)}</span> input tokens ·{" "}
            <span className="mono">{groupDigits(data.totals.output_tokens)}</span> output tokens
          </p>
          <div className="usage__scroll">
            <table className="usage">
              <caption className="visually-hidden">The most recent AI calls, newest first</caption>
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Stage</th>
                  <th scope="col">Model</th>
                  <th scope="col" className="usage__num">
                    Input tokens
                  </th>
                  <th scope="col" className="usage__num">
                    Output tokens
                  </th>
                  <th scope="col" className="usage__num">
                    Time
                  </th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((row) => (
                  <tr key={row.id}>
                    <td className="mono">{formatDateTime(row.created_at)}</td>
                    <td>{aiStageName(row.stage_id)}</td>
                    <td className="mono">{row.model}</td>
                    <td className="mono usage__num">{groupDigits(row.input_tokens)}</td>
                    <td className="mono usage__num">{groupDigits(row.output_tokens)}</td>
                    <td className="mono usage__num">{durationLabel(row.duration_ms)}</td>
                    <td>{AI_CALL_STATUS[row.status] ?? row.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {data.totals.calls > data.items.length && (
            <p className="usage__empty">Showing the {data.items.length} most recent calls.</p>
          )}
        </>
      )}
    </Card>
  );
}
