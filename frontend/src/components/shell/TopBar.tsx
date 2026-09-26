import type { ReactNode } from "react";
import { Link, NavLink } from "react-router";
import "./shell.css";

export interface TopBarProps {
  /** Name of the open engagement, if any. */
  engagementName?: string;
  /** True when the open engagement is the illustrative fixture. */
  isFixture?: boolean;
  /** The guided engagement navigation, shown when an engagement is open. */
  nav?: ReactNode;
}

/** Top bar on every screen (PRD §5.3): product · engagement · guided nav · Engagements · Settings. */
export function TopBar({ engagementName, isFixture = false, nav }: TopBarProps) {
  return (
    <header className="topbar">
      <Link to="/" className="topbar__product">
        Process Map Studio
      </Link>
      {engagementName && (
        <span className="topbar__engagement">
          <span>{engagementName}</span>
          {isFixture && <span className="topbar__fixture">Illustrative fixture</span>}
        </span>
      )}
      <div className="topbar__nav">{nav}</div>
      <nav className="topbar__links" aria-label="App">
        <NavLink to="/" end className="topbar__link">
          Engagements
        </NavLink>
        <NavLink to="/settings" className="topbar__link">
          Settings
        </NavLink>
      </nav>
    </header>
  );
}
