import { PACK_LAYOUTS, realityPackUrl } from "../../lib/exports";
import "./packDownloads.css";

export interface PackDownloadsProps {
  versionId: string;
  versionLabel: string;
}

/**
 * The Reality pack's two downloads (PRD §3.18.6, §7.4; P13d): A3 and 16:9 pages of the same
 * frozen snapshot. Plain links: the browser saves the file the server names.
 */
export function PackDownloads({ versionId, versionLabel }: PackDownloadsProps) {
  return (
    <p className="pack-downloads">
      {PACK_LAYOUTS.map(({ layout, label }, i) => (
        <a
          key={layout}
          className={`btn ${i === 0 ? "btn--primary" : "btn--secondary"}`}
          href={realityPackUrl(versionId, layout)}
          download
        >
          Download {label}{" "}
          <span className="visually-hidden">Reality pack of {versionLabel}</span>
        </a>
      ))}
    </p>
  );
}
