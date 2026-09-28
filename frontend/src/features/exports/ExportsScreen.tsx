import { Link, useParams, useSearchParams } from "react-router";
import { Card, EmptyState, ErrorState, SelectField, Skeleton } from "../../components/common";
import { CheckGlyph } from "../../components/quality";
import { useEngagement } from "../../hooks/useEngagements";
import { useVersion, useVersions } from "../../hooks/useVersions";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { EXCLUDED, EXPORTS, exportUrl } from "../../lib/exports";
import { formatDate } from "../../lib/format";
import { greenCount } from "../../lib/quality";
import type { VersionSummary } from "../../lib/reviewTypes";
import { EngagementProblem } from "../engagement/EngagementProblem";
import "./exports.css";

function CardStatus({ versionId }: { versionId: string }) {
  const version = useVersion(versionId);
  const card = version.data?.quality_card ?? null;
  if (!card) return <span className="export-card__status">Quality card: not recorded</span>;
  const { green, total } = greenCount(card);
  return (
    <span className="export-card__status">
      <CheckGlyph status={card.all_green ? "pass" : "fail"} /> Quality card: {green} of {total} green
    </span>
  );
}

/**
 * Exports (PRD §5.4): the four exports of a published version with a green quality card, what
 * each leaves out, and Download. Gap analysis reports join in phase P10.
 */
export function ExportsScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const versions = useVersions(engagementId);
  const [params, setParams] = useSearchParams();

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }
  const published = (versions.data ?? []).filter((v) => v.state === "published" || v.state === "superseded");
  const chosen: VersionSummary | undefined =
    published.find((v) => v.id === params.get("version")) ?? published.find((v) => v.state === "published") ?? published[0];

  return (
    <main className="screen" aria-labelledby="exports-title">
      <div>
        <h1 id="exports-title">Exports</h1>
        <p className="screen__intro">
          Download a published version to share it. Every export uses role names only and leaves out images, verbatim
          quotes and names.
        </p>
      </div>
      {versions.isPending && <Skeleton height="160px" />}
      {versions.isError && (
        <ErrorState
          title="The published versions couldn't be loaded"
          message={messageOf(versions.error)}
          details={copyDetailsOf(versions.error)}
          onRetry={() => void versions.refetch()}
        />
      )}
      {versions.isSuccess && !chosen && (
        <EmptyState
          message="Publish a version with a green quality card first. Exports are made from published versions only."
          action={<Link to={engagementPath(engagementId, "review")}>Go to Review</Link>}
        />
      )}
      {chosen && (
        <>
          <div className="exports__version">
            <SelectField
              label="Version"
              value={chosen.id}
              options={published.map((v) => ({
                value: v.id,
                label: `${v.label} · ${v.state === "superseded" ? "superseded" : "published"} ${formatDate(v.published_at ?? "")}`,
              }))}
              onChange={(id) =>
                setParams(
                  (current) => {
                    const next = new URLSearchParams(current);
                    next.set("version", id);
                    return next;
                  },
                  { replace: true },
                )
              }
            />
          </div>
          <div className="exports__grid">
            {EXPORTS.map((kind) => (
              <Card key={kind.format} title={kind.title} className="export-card">
                <p>{kind.description}</p>
                <p className="export-card__excluded">{EXCLUDED}</p>
                <CardStatus versionId={chosen.id} />
                <a className="btn btn--primary export-card__download" href={exportUrl(chosen.id, kind.format)} download>
                  Download{" "}
                  <span className="visually-hidden">
                    {kind.title} of {chosen.label}
                  </span>
                </a>
              </Card>
            ))}
            <Card title="Gap analysis reports" className="export-card">
              <p>Finalised gap analysis reports, each as a Markdown file.</p>
              <p className="export-card__excluded">No finalised reports yet. Gap analysis arrives in build phase P10.</p>
            </Card>
          </div>
        </>
      )}
    </main>
  );
}
