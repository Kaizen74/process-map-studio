import { useState } from "react";
import type { ModuleSwitches } from "../../api/settings";
import type { Settings } from "../../api/types";
import { Card, CheckboxField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useSaveModules } from "../../hooks/useSettings";
import { messageOf } from "../../lib/errors";

type ModuleKey = keyof Required<ModuleSwitches>;

const MODULES: readonly { key: ModuleKey; label: string; help: string }[] = [
  {
    key: "gap_analysis_enabled",
    label: "Gap analysis",
    help: "Compares a map with your sources, or with published practice from a brief you approve. On by default.",
  },
  {
    key: "system_records_enabled",
    label: "System records",
    help: "Adds a System records step to each engagement: import an event-log extract from a system to measure volumes and waiting times. Off by default.",
  },
  {
    key: "value_enabled",
    label: "Value calculator and step dispositions",
    help: "Shows each step's suggested disposition (delete, automate, AI-assisted, human approves, keep human) and its indicative hours and cost a month, labelled measured, estimated or assumed. Off by default.",
  },
];

/**
 * Optional modules (PRD §5.4 Settings; decision A): gap analysis starts on, the others off, so the
 * core screens stay as they are until Eric wants more. Switching one off hides it, keeps its data.
 */
export function ModulesCard({ settings }: { settings: Settings }) {
  const save = useSaveModules();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);

  function onToggle(key: ModuleKey, label: string, enabled: boolean) {
    setError(null);
    save.mutate(
      { [key]: enabled },
      {
        onSuccess: () => toast(`${label} switched ${enabled ? "on" : "off"}.`),
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
        {MODULES.map((m) => (
          <CheckboxField
            key={m.key}
            label={m.label}
            checked={settings[m.key]}
            onChange={(on) => onToggle(m.key, m.label, on)}
            help={m.help}
          />
        ))}
        {error && (
          <p className="danger-note" role="alert">
            {error}
          </p>
        )}
      </div>
    </Card>
  );
}
