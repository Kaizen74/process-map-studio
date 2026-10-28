import { useState } from "react";
import { NavLink, useLocation } from "react-router";
import { Popover } from "../common";
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
  /** Off the main path: listed under "More" (2026-10-28). */
  more?: boolean;
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

function StepLink({
  item,
  isNext,
  onClick,
}: {
  item: NavItem;
  isNext: boolean;
  onClick?: () => void;
}) {
  const spoken = [
    item.label,
    STATUS_TEXT[item.status],
    item.status === "attention" && item.count !== undefined
      ? `${item.count} to resolve`
      : "",
    item.optional ? "optional" : "",
    isNext ? "recommended next step" : "",
  ]
    .filter(Boolean)
    .join(", ");
  return (
    <NavLink
      to={item.to}
      className="engagement-nav__item"
      aria-label={spoken}
      onClick={onClick}
    >
      <span
        className={`nav-status nav-status--${item.status}`}
        aria-hidden="true"
      />
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
  );
}

/**
 * The engagement navigation doubles as a guided path (PRD §5.3). The main path stays in the bar;
 * the other screens sit under "More" (2026-10-28, Eric: the bar was overwhelming), which carries
 * their attention count, the Next badge when the next step is among them, and the current one.
 */
export function EngagementNav({ items, nextKey }: EngagementNavProps) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const main = items.filter((i) => !i.more);
  const more = items.filter((i) => i.more);
  const isNext = (item: NavItem) => item.key === nextKey && !item.optional;
  const current = more.find(
    (i) => pathname === i.to || pathname.startsWith(`${i.to}/`),
  );
  const nextInMore = more.some(isNext);
  const attention = more.filter((i) => i.status === "attention").length;
  const spoken = [
    "More steps",
    current ? `current: ${current.label}` : "",
    nextInMore ? "includes the recommended next step" : "",
    attention
      ? `${attention} ${attention === 1 ? "needs" : "need"} attention`
      : "",
  ]
    .filter(Boolean)
    .join(", ");
  return (
    <nav aria-label="Engagement steps">
      <ol className="engagement-nav">
        {main.map((item) => (
          <li key={item.key}>
            <StepLink item={item} isNext={isNext(item)} />
          </li>
        ))}
        {more.length > 0 && (
          <li className="popover-anchor">
            <button
              type="button"
              className={
                current
                  ? "engagement-nav__item engagement-nav__more engagement-nav__more--current"
                  : "engagement-nav__item engagement-nav__more"
              }
              aria-expanded={open}
              aria-label={spoken}
              onClick={() => setOpen(!open)}
            >
              <span aria-hidden="true">
                {current ? `More: ${current.label}` : "More"}
              </span>
              {attention > 0 && (
                <span className="engagement-nav__count" aria-hidden="true">
                  {attention}
                </span>
              )}
              {nextInMore && (
                <span className="chip chip--neutral" aria-hidden="true">
                  Next
                </span>
              )}
            </button>
            <Popover
              open={open}
              title="More steps"
              onClose={() => setOpen(false)}
            >
              <ul className="engagement-nav__menu">
                {more.map((item) => (
                  <li key={item.key}>
                    <StepLink
                      item={item}
                      isNext={isNext(item)}
                      onClick={() => setOpen(false)}
                    />
                  </li>
                ))}
              </ul>
            </Popover>
          </li>
        )}
      </ol>
    </nav>
  );
}
