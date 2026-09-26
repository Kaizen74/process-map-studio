import { NavLink } from "react-router";
import "./shell.css";

export type NavStatus = "done" | "attention" | "not_started";

export interface NavItem {
  key: string;
  label: string;
  to: string;
  status: NavStatus;
  /** Number of things needing attention (shown with the attention glyph). */
  count?: number;
  /** Optional steps (Gap analysis) are labelled and never recommended as Next. */
  optional?: boolean;
}

export interface EngagementNavProps {
  items: readonly NavItem[];
  /** Key of the next recommended item (from the readiness endpoint). */
  nextKey?: string;
}

const STATUS_TEXT: Record<NavStatus, string> = {
  done: "done",
  attention: "needs attention",
  not_started: "not started",
};

/** The engagement navigation doubles as a guided path (PRD §5.3). */
export function EngagementNav({ items, nextKey }: EngagementNavProps) {
  return (
    <nav aria-label="Engagement steps">
      <ol className="engagement-nav">
        {items.map((item) => {
          const isNext = item.key === nextKey && !item.optional;
          const spoken = [
            item.label,
            STATUS_TEXT[item.status],
            item.status === "attention" && item.count !== undefined ? `${item.count} to resolve` : "",
            item.optional ? "optional" : "",
            isNext ? "recommended next step" : "",
          ]
            .filter(Boolean)
            .join(", ");
          return (
            <li key={item.key}>
              <NavLink to={item.to} className="engagement-nav__item" aria-label={spoken}>
                <span className={`nav-status nav-status--${item.status}`} aria-hidden="true" />
                <span aria-hidden="true">{item.label}</span>
                {item.status === "attention" && item.count !== undefined && (
                  <span className="engagement-nav__count" aria-hidden="true">
                    {item.count}
                  </span>
                )}
                {item.optional && (
                  <span className="engagement-nav__tag" aria-hidden="true">
                    Optional
                  </span>
                )}
                {isNext && (
                  <span className="chip chip--neutral" aria-hidden="true">
                    Next
                  </span>
                )}
              </NavLink>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
