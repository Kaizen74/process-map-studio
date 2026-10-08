import { Outlet, useMatch } from "react-router";
import { EngagementNav, TopBar, type NavItem } from "../../components/shell";
import type { NavKey } from "../../api/types";
import { useEngagement, useReadiness } from "../../hooks/useEngagements";
import { useSettings } from "../../hooks/useSettings";
import { useEventLogs } from "../../hooks/useSystemRecords";
import { engagementPath, visibleSteps, type StepKey } from "../../lib/engagementSteps";

/** Every screen sits under the top bar. Inside an engagement it shows the guided path (PRD §5.3). */
export function AppShell() {
  const match = useMatch("/engagements/:engagementId/*");
  const id = match?.params.engagementId;
  const engagement = useEngagement(id);
  const readiness = useReadiness(id);
  const settings = useSettings();
  const systemRecordsOn = settings.data?.system_records_enabled === true;
  const logs = useEventLogs(id ?? "", Boolean(id) && systemRecordsOn);

  let nav;
  if (id && readiness.data) {
    const status = readiness.data;
    // Optional modules aren't in the readiness nav: System records is done once a log is imported.
    const moduleStatus: Partial<Record<StepKey, NavItem["status"]>> = {
      system_records: logs.data?.some((l) => l.status === "imported") ? "done" : "not_started",
    };
    const items: NavItem[] = visibleSteps(settings.data).map((step) => {
      const count = step.module ? undefined : status.nav_counts[step.key as NavKey];
      return {
        key: step.key,
        label: step.label,
        to: engagementPath(id, step.key),
        status: step.module ? (moduleStatus[step.key] ?? "not_started") : status.nav[step.key as NavKey],
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
