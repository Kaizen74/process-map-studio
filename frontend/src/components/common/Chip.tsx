import type { ReactNode } from "react";
import "./common.css";

export type ChipTone = "neutral" | "good" | "danger" | "decision";

export interface ChipProps {
  tone?: ChipTone;
  /** Dashed outline, e.g. an unreviewed draft. */
  dashed?: boolean;
  /** Mono font for IDs, versions and numbers. */
  mono?: boolean;
  title?: string;
  children: ReactNode;
}

/** A small label. Meaning is always in its text; tone only reinforces it. */
export function Chip({ tone = "neutral", dashed = false, mono = false, title, children }: ChipProps) {
  const classes = ["chip", `chip--${tone}`, dashed && "chip--dashed", mono && "chip--mono"]
    .filter(Boolean)
    .join(" ");
  return (
    <span className={classes} title={title}>
      {children}
    </span>
  );
}
