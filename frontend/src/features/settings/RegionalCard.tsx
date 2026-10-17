import { useState } from "react";
import type { Settings } from "../../api/types";
import { Button, Card, SelectField, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useSaveRegional } from "../../hooks/useSettings";
import { fieldOf, messageOf } from "../../lib/errors";
import { zoneOptions } from "../../lib/systemRecords";

const BAD_CODE = "Enter a three-letter currency code, for example SGD.";

/**
 * Regional (PRD §3.4 item 9, §5.4 Settings; R10): the currency the value calculator labels its
 * figures with (it never converts amounts) and the time zone a new system log starts with.
 */
export function RegionalCard({ settings }: { settings: Settings }) {
  const [currency, setCurrency] = useState(settings.currency);
  const [zone, setZone] = useState(settings.default_timezone);
  const [problem, setProblem] = useState<string | null>(null);
  const save = useSaveRegional();
  const toast = useToast();
  const blamed = fieldOf(save.error);

  function onSave() {
    const code = currency.trim().toUpperCase();
    if (!/^[A-Z]{3}$/.test(code)) return setProblem(BAD_CODE);
    setProblem(null);
    save.mutate(
      { currency: code, default_timezone: zone },
      {
        onSuccess: (saved) => {
          setCurrency(saved.currency);
          setZone(saved.default_timezone);
          toast("Regional settings were saved.");
        },
      },
    );
  }

  return (
    <Card
      title="Regional"
      description="How money is labelled in the value calculator, and the time zone a new system log starts with."
    >
      <div className="settings-form">
        <TextField
          label="Currency"
          value={currency}
          onChange={setCurrency}
          mono
          help="A three-letter code such as SGD, USD or EUR. Amounts are labelled with it, never converted."
          error={problem ?? (blamed === "currency" ? messageOf(save.error) : null)}
        />
        <SelectField
          label="Default time zone for system logs"
          value={zone}
          options={zoneOptions(zone)}
          onChange={setZone}
          help="Each log can still have its own time zone."
          error={blamed === "default_timezone" ? messageOf(save.error) : null}
        />
        {save.isError && !blamed && (
          <p className="danger-note" role="alert">
            {messageOf(save.error)}
          </p>
        )}
        <div className="settings-actions">
          <Button variant="primary" onClick={onSave}>
            {save.isPending ? "Saving…" : "Save regional settings"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
