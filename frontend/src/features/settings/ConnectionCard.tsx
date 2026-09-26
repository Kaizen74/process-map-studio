import { useState } from "react";
import type { ConnectionTest, Settings } from "../../api/types";
import { Button, Card, Chip, ErrorState, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useSaveApiKey, useTestConnection } from "../../hooks/useSettings";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { validateApiKey } from "../../lib/validation";

type Verdict = "pass" | "fail" | "yes" | "no" | "unchecked";

const VERDICT: Record<Verdict, { text: string; tone: "good" | "danger" | "neutral" }> = {
  pass: { text: "Pass", tone: "good" },
  fail: { text: "Fail", tone: "danger" },
  yes: { text: "Yes", tone: "good" },
  no: { text: "No", tone: "danger" },
  unchecked: { text: "Not checked", tone: "neutral" },
};

function rows(result: ConnectionTest): [string, Verdict][] {
  const model: Verdict = !result.key_valid ? "unchecked" : result.model_available ? "pass" : "fail";
  const cap = (supported: boolean): Verdict =>
    result.model_available ? (supported ? "yes" : "no") : "unchecked";
  return [
    ["Key valid", result.key_valid ? "pass" : "fail"],
    ["Model available", model],
    ["PDF input", cap(result.capabilities.pdf_input)],
    ["Structured outputs", cap(result.capabilities.structured_outputs)],
  ];
}

/** Claude connection (PRD §5.4 Settings): masked key, Save, Test connection. */
export function ConnectionCard({ settings }: { settings: Settings }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const saveKey = useSaveApiKey();
  const test = useTestConnection();
  const toast = useToast();

  function onSave() {
    const problem = validateApiKey(key);
    setError(problem);
    if (problem) return;
    saveKey.mutate(key.trim(), {
      onSuccess: () => {
        setKey(""); // never keep the key on screen longer than needed
        test.reset();
        toast("Your API key was saved. Press Test connection to check it.");
      },
      onError: (e) => setError(messageOf(e)),
    });
  }

  return (
    <Card
      title="Claude connection"
      description="Your key is stored only on this computer, in the app's private .env file."
    >
      <div className="settings-form">
        <p className="key-status">
          {settings.key_set ? (
            <>
              <span>Saved key</span>
              <span className="key-status__mask" aria-hidden="true">
                {"•".repeat(8)}
                {settings.key_last4}
              </span>
              <span className="visually-hidden">ending in {settings.key_last4}</span>
            </>
          ) : (
            <span>No key saved yet.</span>
          )}
        </p>
        <TextField
          label={settings.key_set ? "Replace the API key" : "Claude API key"}
          type="password"
          value={key}
          onChange={setKey}
          error={error}
          mono
          placeholder="sk-ant-…"
          autoComplete="new-password"
          help="Where to get it: sign in at platform.claude.com, open API keys, choose Create key, copy it once and paste it here."
        />
        <div className="settings-actions">
          <Button variant="primary" onClick={onSave}>
            {saveKey.isPending ? "Saving…" : "Save key"}
          </Button>
          <Button onClick={() => test.mutate()}>{test.isPending ? "Testing…" : "Test connection"}</Button>
        </div>
        {test.isSuccess && (
          <div className="stack" role="group" aria-label="Connection test results">
            <p className="results__message" role="status">
              {test.data.message}
            </p>
            <ul className="results">
              {rows(test.data).map(([label, verdict]) => (
                <li key={label} className="results__row">
                  <span>{label}</span>
                  <Chip tone={VERDICT[verdict].tone}>{VERDICT[verdict].text}</Chip>
                </li>
              ))}
            </ul>
          </div>
        )}
        {test.isError && (
          <ErrorState
            title="The connection test couldn't finish"
            message={messageOf(test.error)}
            details={copyDetailsOf(test.error)}
            onRetry={() => test.mutate()}
          />
        )}
      </div>
    </Card>
  );
}
