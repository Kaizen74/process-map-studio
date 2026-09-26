import "./common.css";

export interface SkeletonProps {
  width?: string;
  height?: string;
}

/** A static placeholder block in the shape of content that is loading. Hidden from screen readers. */
export function Skeleton({ width = "100%", height = "12px" }: SkeletonProps) {
  return <span className="skeleton" style={{ width, height }} aria-hidden="true" />;
}
