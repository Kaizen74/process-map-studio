import type { SourceBreakdown } from "../../api/types";
import { plural } from "../../lib/format";

/**
 * DECISIONS 114: what each source gave the draft, so a document that produced little is visible
 * at once: the claims found in it, how many passed the checks, were rejected (and the main
 * reasons) or were set aside as another flow, and the steps built from it.
 */
export function SourceBreakdownTable({
  sources,
}: {
  sources: readonly SourceBreakdown[];
}) {
  if (sources.length === 0) return null;
  return (
    <div className="registry draft-sources">
      <table className="registry__table">
        <caption>What each source gave this draft</caption>
        <thead>
          <tr>
            <th scope="col">Source</th>
            <th scope="col">Claims found</th>
            <th scope="col">Passed the checks</th>
            <th scope="col">Rejected</th>
            <th scope="col">Other flow</th>
            <th scope="col">Steps built from it</th>
          </tr>
        </thead>
        <tbody>
          {sources.map((s) => (
            <tr key={s.source_id}>
              <th scope="row">{s.filename}</th>
              <td className="mono">{s.found}</td>
              <td className="mono">{s.verified}</td>
              <td>
                <span className="mono">{s.rejected}</span>
                {s.reasons.length > 0 && (
                  <span className="draft-sources__reasons">
                    {" "}
                    ({s.reasons.map((r) => `${r.count} ${r.reason}`).join("; ")}
                    )
                  </span>
                )}
              </td>
              <td className="mono">{s.outside_flow}</td>
              <td className="mono">{s.steps}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {sources.some((s) => s.found > 0 && s.steps === 0) && (
        <p className="draft-note">
          {plural(
            sources.filter((s) => s.found > 0 && s.steps === 0).length,
            "source",
          )}{" "}
          gave claims but no step of this map is built from them yet: they may
          be about another flow, or every claim was rejected. The rejected
          claims below say why.
        </p>
      )}
    </div>
  );
}
