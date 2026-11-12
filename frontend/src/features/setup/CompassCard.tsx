import type { CompassLink } from "../../api/types";
import { Card, Chip } from "../../components/common";
import { plural } from "../../lib/format";

/**
 * The Capability Compass hand-off this engagement started from (DECISIONS 95): its IDs exactly as
 * received, so findings can point back, and how many suggested probes came with it.
 */
export function CompassCard({ link }: { link: CompassLink }) {
  return (
    <Card
      title="Capability Compass"
      description="This engagement started from a hand-off. Its IDs are kept exactly as received, so findings can point back."
    >
      <dl className="compass-ids">
        <div>
          <dt>Pilot</dt>
          <dd className="mono">
            {link.key}:{link.pilot_ref}
          </dd>
        </div>
        <div>
          <dt>Cluster</dt>
          <dd>
            <span className="mono">
              {link.key}:{link.cluster_ref}
            </span>{" "}
            {link.cluster_name}
          </dd>
        </div>
        <div>
          <dt>Cells</dt>
          <dd className="compass-ids__cells">
            {link.cell_refs.length === 0
              ? "None listed"
              : link.cell_refs.map((ref) => (
                  <Chip key={ref}>
                    <span className="mono">{ref}</span>
                  </Chip>
                ))}
          </dd>
        </div>
      </dl>
      <p className="field__help">
        {plural(link.interview_prompts.length, "suggested interview probe")} came with it. They are prompts, not
        evidence: they are offered when you build an interview guide and never become a step or a claim.
      </p>
      {!link.ready && (
        <p className="field__help" role="note">
          Capability Compass marked this hand-off as not ready when it was exported.
        </p>
      )}
    </Card>
  );
}
