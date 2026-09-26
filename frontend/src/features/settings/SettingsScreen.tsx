import { Card, ErrorState, Skeleton } from "../../components/common";
import { useSettings } from "../../hooks/useSettings";
import { useHealth } from "../../hooks/useSystem";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { ConnectionCard } from "./ConnectionCard";
import { ModelCard } from "./ModelCard";
import { OwnerNameCard } from "./OwnerNameCard";
import "./settings.css";

function AboutCard() {
  const health = useHealth();
  return (
    <Card title="About">
      <dl className="about">
        <dt>App version</dt>
        <dd>{health.data?.app_version ?? "…"}</dd>
        <dt>PRD version</dt>
        <dd>{health.data?.prd_version ?? "…"}</dd>
      </dl>
    </Card>
  );
}

/** Settings (PRD §5.4). AI usage arrives in P1/P3, web research in P10. */
export function SettingsScreen() {
  const settings = useSettings();
  return (
    <main className="screen" aria-labelledby="settings-title">
      <div>
        <h1 id="settings-title">Settings</h1>
        <p className="screen__intro">Changes take effect straight away; no restart needed.</p>
      </div>
      {settings.isPending && (
        <div className="settings-grid" aria-busy="true">
          <Card title="Your name">
            <Skeleton height="28px" />
          </Card>
          <Card title="Claude connection">
            <Skeleton height="28px" />
          </Card>
        </div>
      )}
      {settings.isError && (
        <ErrorState
          title="Your settings couldn't be loaded"
          message={messageOf(settings.error)}
          details={copyDetailsOf(settings.error)}
          onRetry={() => void settings.refetch()}
        />
      )}
      {settings.isSuccess && (
        <div className="settings-grid">
          <ConnectionCard settings={settings.data} />
          <OwnerNameCard settings={settings.data} />
          <ModelCard settings={settings.data} />
          <AboutCard />
        </div>
      )}
    </main>
  );
}
