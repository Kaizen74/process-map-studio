import { Outlet, useMatch } from "react-router";
import { EngagementNav, TopBar, type NavItem } from "../../components/shell";
import { useEngagement, useReadiness } from "../../hooks/useEngagements";
import { ENGAGEMENT_STEPS, engagementPath } from "../../lib/engagementSteps";

/** Every screen sits under the top bar. Inside an engagement it shows the guided path (PRD §5.3). */
export function AppShell() {
  const match = useMatch("/engagements/:engagementId/*");
  const id = match?.params.engagementId;
  const engagement = useEngagement(id);
  const readiness = useReadiness(id);

  let nav;
  if (id && readiness.data) {
    const status = readiness.data;
    const items: NavItem[] = ENGAGEMENT_STEPS.map((step) => {
      const count = status.nav_counts[step.key];
      return {
        key: step.key,
        label: step.label,
        to: engagementPath(id, step.key),
        status: status.nav[step.key],
        ...(count !== undefined ? { count } : {}),
        ...(step.optional ? { optional: true } : {}),
      };
    });
    nav = <EngagementNav items={items} {...(status.next_step ? { nextKey: status.next_step } : {})} />;
  }

  return (
    <div className="app">
      <TopBar {...(engagement.data ? { engagementName: engagement.data.name } : {})} nav={nav} />
      <Outlet />
    </div>
  );
}
