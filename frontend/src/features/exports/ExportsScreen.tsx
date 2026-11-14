import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import {
  Card,
  CheckboxField,
  EmptyState,
  ErrorState,
  SelectField,
  SignalMeter,
  Skeleton,
} from "../../components/common";
import { CheckGlyph } from "../../components/quality";
import { PackDownloads } from "../../components/reality";
import { useComparisons } from "../../hooks/useComparisons";
import { useEngagement } from "../../hooks/useEngagements";
import { useGapAnalyses } from "../../hooks/useGap";
import { useSettings } from "../../hooks/useSettings";
import { useVersion, useVersions } from "../../hooks/useVersions";
import { engagementPath } from "../../lib/engagementSteps";
import { referenceNote } from "../../lib/comparisons";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import type { CompassLink } from "../../api/types";
import { EXCLUDED, EXPORTS, PACK_EXCLUDED, RETURN_EXCLUDED, compassReturnUrl, exportUrl } from "../../lib/exports";
import { formatDate } from "../../lib/format";
import { MODE_LABELS, exportUrl as gapExportUrl } from "../../lib/gap";
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

/** The fifth card (PRD §5.4 Exports): this version's finalised gap analysis reports. */
function GapReportsCard({ versionId, versionLabel, engagementId }: { versionId: string; versionLabel: string; engagementId: string }) {
  const analyses = useGapAnalyses(versionId);
  const finalised = (analyses.data ?? []).filter((a) => a.status === "finalised");
  return (
    <Card title="Gap analysis reports" className="export-card">
      <p>Finalised gap analysis reports, each as a Markdown file: facts, interpretation and recommendation.</p>
      <p className="export-card__excluded">Role names only; no passage quotes or names.</p>
      {analyses.isError && <p className="export-card__excluded">{messageOf(analyses.error)}</p>}
      {analyses.isSuccess && finalised.length === 0 && (
        <p>
          No finalised reports for {versionLabel} yet.{" "}
          <Link to={engagementPath(engagementId, "gap_analysis")}>Go to Gap analysis</Link>
        </p>
      )}
      {finalised.length > 0 && (
        <ul className="export-card__reports">
          {finalised.map((a) => (
            <li key={a.id}>
              {MODE_LABELS[a.mode]} · finalised {formatDate(a.finalised_at ?? "")}{" "}
              <a className="btn btn--secondary" href={gapExportUrl(a.id)} download>
                Download .md<span className="visually-hidden"> {MODE_LABELS[a.mode]} report of {versionLabel}</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/**
 * The Capability Compass return file (DECISIONS 97), offered for an engagement that started from
 * a hand-off: what the published map found, under the hand-off's key, as JSON for the other apps
 * and as the same content in readable text. Eric may add the cells the findings bear on.
 */
function CompassReturnCard({
  engagementId,
  versionId,
  versionLabel,
  link,
}: {
  engagementId: string;
  versionId: string;
  versionLabel: string;
  link: CompassLink;
}) {
  const [cells, setCells] = useState<string[]>([]);
  const comparisons = useComparisons(engagementId);
  const asReference = referenceNote(engagementId, comparisons.data ?? []);
  const toggle = (cell: string, on: boolean) =>
    setCells((chosen) => (on ? [...chosen.filter((c) => c !== cell), cell] : chosen.filter((c) => c !== cell)));
  const chosen = link.cell_refs.filter((c) => cells.includes(c)); // in the hand-off's order
  const relates = [link.pilot_ref, link.cluster_ref, ...chosen];
  return (
    <Card title="Capability Compass return file" className="export-card">
      <p>
        What this version found, under engagement key <span className="mono">{link.key}</span>: each step with its
        work type, each discrepancy with its figure, each intent statement, the knowledge risks and your verdicts on
        what is being tested, each with its grade. When this country was compared with another on Compare countries,
        the differences you classed or kept are added, with your reasons.
      </p>
      {asReference && <p>{asReference}</p>}
      <p className="export-card__excluded">{RETURN_EXCLUDED}</p>
      <p>
        Relates to: <span className="mono">{relates.join(", ")}</span>
      </p>
      {link.cell_refs.length > 0 && (
        <fieldset className="export-card__cells">
          <legend>Add the cells these findings bear on</legend>
          {link.cell_refs.map((cell) => (
            <CheckboxField key={cell} label={cell} checked={cells.includes(cell)} onChange={(on) => toggle(cell, on)} />
          ))}
        </fieldset>
      )}
      <p className="export-card__downloads">
        <a
          className="btn btn--primary"
          href={compassReturnUrl(versionId, "json", chosen)}
          download
        >
          Download JSON <span className="visually-hidden">return file of {versionLabel}</span>
        </a>{" "}
        <a
          className="btn btn--secondary"
          href={compassReturnUrl(versionId, "md", chosen)}
          download
        >
          Download readable text <span className="visually-hidden">return file of {versionLabel}</span>
        </a>
      </p>
    </Card>
  );
}

/** The Reality pack (PRD §3.18.6, §7.4; P13d), offered while the Reality views are switched on. */
function RealityPackCard({ versionId, versionLabel }: { versionId: string; versionLabel: string }) {
  return (
    <Card title="Reality pack (.html)" className="export-card">
      <p>
        The seven Reality views of this version, one per page, for printing or saving as PDF: A3 landscape or 16:9
        slides. One file that opens in any browser, offline.
      </p>
      <p className="export-card__excluded">{PACK_EXCLUDED}</p>
      <CardStatus versionId={versionId} />
      <PackDownloads versionId={versionId} versionLabel={versionLabel} />
    </Card>
  );
}

/**
 * Exports (PRD §5.4): the four exports of a published version with a green quality card, what
 * each leaves out, and Download; the version's finalised gap analysis reports; and, while the
 * Reality views are switched on, the Reality pack.
 */
export function ExportsScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const versions = useVersions(engagementId);
  const settings = useSettings();
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
          {chosen.signal && (
            <p className="exports__signal">
              <SignalMeter signal={chosen.signal} />
            </p>
          )}
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
            <GapReportsCard versionId={chosen.id} versionLabel={chosen.label} engagementId={engagementId} />
            {settings.data?.reality_views_enabled === true && (
              <RealityPackCard versionId={chosen.id} versionLabel={chosen.label} />
            )}
            {engagement.data?.compass && (
              <CompassReturnCard
                engagementId={engagementId}
                versionId={chosen.id}
                versionLabel={chosen.label}
                link={engagement.data.compass}
              />
            )}
          </div>
        </>
      )}
    </main>
  );
}
