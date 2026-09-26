import { Outlet } from "react-router";
import { TopBar } from "../../components/shell";

/** Every screen sits under the top bar. The engagement nav appears once engagements exist (P1). */
export function AppShell() {
  return (
    <div className="app">
      <TopBar />
      <Outlet />
    </div>
  );
}
