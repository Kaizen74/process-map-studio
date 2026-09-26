import { useState } from "react";
import type { Settings } from "../../api/types";
import { Button, Card, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useSaveProfile } from "../../hooks/useSettings";
import { messageOf } from "../../lib/errors";
import { validateOwnerName } from "../../lib/validation";

export function OwnerNameCard({ settings }: { settings: Settings }) {
  const [name, setName] = useState(settings.owner_name);
  const [error, setError] = useState<string | null>(null);
  const save = useSaveProfile();
  const toast = useToast();

  function onSave() {
    const problem = validateOwnerName(name);
    setError(problem);
    if (problem) return;
    save.mutate(name.trim(), {
      onSuccess: (saved) => {
        setName(saved.owner_name);
        toast("Your name was saved.");
      },
      onError: (e) => setError(messageOf(e)),
    });
  }

  return (
    <Card title="Your name" description="Shown as the validator on published versions and exports.">
      <div className="settings-form">
        <TextField label="Your name" value={name} onChange={setName} error={error} autoComplete="name" />
        <div className="settings-actions">
          <Button variant="primary" onClick={onSave}>
            {save.isPending ? "Saving…" : "Save name"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
