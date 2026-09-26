import type { ReactNode } from "react";
import "./common.css";

export interface EmptyStateProps {
  /** One sentence: what belongs here and why. */
  message: string;
  /** At most one primary action. */
  action?: ReactNode;
}

export function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className="state-message">
      <p>{message}</p>
      {action}
    </div>
  );
}
