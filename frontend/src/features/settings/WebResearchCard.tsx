import { useState } from "react";
import type { Settings } from "../../api/types";
import { Button, Card, CheckboxField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useSaveResearch, useTestWebSearch } from "../../hooks/useSettings";
import { messageOf } from "../../lib/errors";

/**
 * Web research (PRD §3.11, §5.4 Settings): off by default. Lets the optional external
 * best-practice analysis search the web with a brief Eric approves; Test web search checks that
 * web search is enabled for his Anthropic organisation (one search, billed as one).
 */
export function WebResearchCard({ settings }: { settings: Settings }) {
  const save = useSaveResearch();
  const test = useTestWebSearch();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);

  function onToggle(enabled: boolean) {
    setError(null);
    save.mutate(enabled, {
      onSuccess: () => toast(enabled ? "Web research switched on." : "Web research switched off."),
      onError: (e) => setError(messageOf(e)),
    });
  }

  return (
    <Card
      title="Web research"
      description="Lets the optional external best-practice analysis search the web using only a brief you approve. Each search is billed by Anthropic."
    >
      <div className="settings-form">
        <CheckboxField
          label="Allow web research"
          checked={settings.web_research_enabled}
          onChange={onToggle}
          help="Off by default. Transcripts, documents and your map are never sent to web search."
        />
        {error && (
          <p className="danger-note" role="alert">
            {error}
          </p>
        )}
        <div className="settings-actions">
          <Button onClick={() => test.mutate()} aria-busy={test.isPending || undefined}>
            {test.isPending ? "Testing…" : "Test web search"}
          </Button>
        </div>
        {test.data && (
          <p className="results__message" role="status">
            {test.data.available ? "Available. " : "Not available. "}
            {test.data.message}
          </p>
        )}
        {test.isError && (
          <p className="danger-note" role="alert">
            {messageOf(test.error)}
          </p>
        )}
      </div>
    </Card>
  );
}
