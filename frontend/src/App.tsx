import { Route, Routes } from "react-router";
import { EngagementsScreen } from "./features/home/EngagementsScreen";
import { SettingsScreen } from "./features/settings/SettingsScreen";
import { AppShell } from "./features/shell/AppShell";
import { NotFoundScreen } from "./features/shell/NotFoundScreen";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<EngagementsScreen />} />
        <Route path="settings" element={<SettingsScreen />} />
        <Route path="*" element={<NotFoundScreen />} />
      </Route>
    </Routes>
  );
}
