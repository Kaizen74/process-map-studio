import { useState } from "react";
import type { Settings } from "../../api/types";
import { Card, CheckboxField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useSaveModules } from "../../hooks/useSettings";
import { messageOf } from "../../lib/errors";

/**
 * Optional modules (PRD §5.4 Settings; decision A): each starts off, so the core screens stay as
 * they are until Eric wants more. Switching a module off hides its screens and never deletes data.
 */
export function ModulesCard({ settings }: { settings: Settings }) {
  const save = useSaveModules();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);

  function onToggle(enabled: boolean) {
    setError(null);
    save.mutate(
      { system_records_enabled: enabled },
      {
        onSuccess: () => toast(enabled ? "System records switched on." : "System records switched off."),
        onError: (e) => setError(messageOf(e)),
      },
    );
  }

  return (
    <Card
      title="Optional modules"
      description="Extra screens you can switch on when an engagement needs them. Switching one off hides it and keeps its data."
    >
      <div className="settings-form">
        <CheckboxField
          label="System records"
          checked={settings.system_records_enabled}
          onChange={onToggle}
          help="Adds a System records step to each engagement: import an event-log extract from a system to measure volumes and waiting times. Off by default."
        />
        {error && (
          <p className="danger-note" role="alert">
            {error}
          </p>
        )}
      </div>
    </Card>
  );
}
