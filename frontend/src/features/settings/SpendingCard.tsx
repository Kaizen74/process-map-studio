import { useState } from "react";
import type { Settings } from "../../api/types";
import { Button, Card, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useSaveSpending } from "../../hooks/useSettings";
import { messageOf } from "../../lib/errors";

const BAD_LIMIT = "Enter an amount above 0 and up to 1,000, or leave it empty for no limit.";

const shown = (limit: number | null) => (limit === null ? "" : limit.toFixed(2));

/**
 * AI spending (2026-10-19, deep review item 5): the most one draft or refresh may cost. The Draft
 * screen shows the estimate; a draft estimated above the limit doesn't start. Empty means no limit.
 */
export function SpendingCard({ settings }: { settings: Settings }) {
  const [limit, setLimit] = useState(shown(settings.draft_cost_limit_usd));
  const [problem, setProblem] = useState<string | null>(null);
  const save = useSaveSpending();
  const toast = useToast();

  function onSave() {
    const text = limit.trim().replace(/^US\$|^\$/, "").replace(/,/g, "");
    const amount = text === "" ? null : Number(text);
    if (amount !== null && !(Number.isFinite(amount) && amount > 0 && amount <= 1000)) {
      return setProblem(BAD_LIMIT);
    }
    setProblem(null);
    save.mutate(amount, {
      onSuccess: (saved) => {
        setLimit(shown(saved.draft_cost_limit_usd));
        toast(saved.draft_cost_limit_usd === null ? "No spending limit is set." : "Your spending limit was saved.");
      },
      onError: (e) => setProblem(messageOf(e)),
    });
  }

  return (
    <Card
      title="AI spending"
      description="The Draft screen shows what a draft will probably cost before it starts. Set a limit to stop a draft that would cost more."
    >
      <div className="settings-form">
        <TextField
          label="Most to spend on one draft (US$)"
          value={limit}
          onChange={setLimit}
          mono
          help="For example 5.00. Leave it empty for no limit. It also applies when you refresh a draft."
          error={problem}
        />
        <div className="settings-actions">
          <Button variant="primary" onClick={onSave}>
            {save.isPending ? "Saving…" : "Save spending limit"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
