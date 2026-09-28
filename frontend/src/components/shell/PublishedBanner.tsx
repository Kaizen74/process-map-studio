import type { ReactNode } from "react";
import { Chip } from "../common";
import "./shell.css";

export interface PublishedBannerProps {
  label: string;
  state: "published" | "superseded" | string;
  /** The owner who validated it, and when (already formatted). */
  publishedBy: string;
  publishedOn: string;
  /** Version picker and Reopen as new draft, on the right. */
  actions?: ReactNode;
}

/** The banner of a published version (PRD §5.7.1, §5.9): read-only, who validated it and when. */
export function PublishedBanner({ label, state, publishedBy, publishedOn, actions }: PublishedBannerProps) {
  const superseded = state === "superseded";
  return (
    <div className="version-banner">
      <Chip tone={superseded ? "neutral" : "good"} mono>
        {superseded ? "Superseded" : "Published"} {label}
      </Chip>
      <p className="version-banner__text">
        Read-only. Validated by {publishedBy || "the owner"} on {publishedOn}.{" "}
        {superseded
          ? "A later version has been published since."
          : "Reopening creates a new draft version."}
      </p>
      {actions && <div className="version-banner__actions">{actions}</div>}
    </div>
  );
}
