import { Route, Routes } from "react-router";
import { DraftScreen } from "./features/draft/DraftScreen";
import { EngagementIndex } from "./features/engagement/EngagementIndex";
import { ExportsScreen } from "./features/exports/ExportsScreen";
import { StepPlaceholder } from "./features/engagement/StepPlaceholder";
import { MatrixScreen } from "./features/matrix/MatrixScreen";
import { RegistersScreen } from "./features/registers/RegistersScreen";
import { EngagementsScreen } from "./features/home/EngagementsScreen";
import { PublishedScreen } from "./features/published/PublishedScreen";
import { ReviewScreen } from "./features/review/ReviewScreen";
import { SettingsScreen } from "./features/settings/SettingsScreen";
import { SetupScreen } from "./features/setup/SetupScreen";
import { SourcesScreen } from "./features/sources/SourcesScreen";
import { AppShell } from "./features/shell/AppShell";
import { NotFoundScreen } from "./features/shell/NotFoundScreen";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<EngagementsScreen />} />
        <Route path="settings" element={<SettingsScreen />} />
        <Route path="engagements/:engagementId" element={<EngagementIndex />} />
        <Route path="engagements/:engagementId/setup" element={<SetupScreen />} />
        <Route path="engagements/:engagementId/sources" element={<SourcesScreen />} />
        <Route path="engagements/:engagementId/draft" element={<DraftScreen />} />
        <Route path="engagements/:engagementId/review" element={<ReviewScreen />} />
        <Route path="engagements/:engagementId/published" element={<PublishedScreen />} />
        <Route path="engagements/:engagementId/matrix" element={<MatrixScreen />} />
        <Route path="engagements/:engagementId/registers" element={<RegistersScreen />} />
        <Route path="engagements/:engagementId/exports" element={<ExportsScreen />} />
        <Route path="engagements/:engagementId/:step" element={<StepPlaceholder />} />
        <Route path="*" element={<NotFoundScreen />} />
      </Route>
    </Routes>
  );
}
