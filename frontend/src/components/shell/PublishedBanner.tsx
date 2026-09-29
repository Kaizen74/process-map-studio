import type { ReactNode } from "react";
import type { SignalStrength } from "../../lib/reviewTypes";
import { Chip, SignalMeter } from "../common";
import "./shell.css";

export interface PublishedBannerProps {
  label: string;
  state: "published" | "superseded" | string;
  /** The owner who validated it, and when (already formatted). */
  publishedBy: string;
  publishedOn: string;
  /** Version picker and Reopen as new draft, on the right. */
  actions?: ReactNode;
  /** How well the sources support the map (P12); shown after the version chip when known. */
  signal?: SignalStrength | null | undefined;
}

/** The banner of a published version (PRD §5.7.1, §5.9): read-only, who validated it and when. */
export function PublishedBanner({ label, state, publishedBy, publishedOn, actions, signal }: PublishedBannerProps) {
  const superseded = state === "superseded";
  return (
    <div className="version-banner">
      <Chip tone={superseded ? "neutral" : "good"} mono>
        {superseded ? "Superseded" : "Published"} {label}
      </Chip>
      {signal && <SignalMeter signal={signal} compact />}
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
