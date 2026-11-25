import { useState, type FormEvent } from "react";
import type { Engagement, Role } from "../../api/types";
import { Button, Card, SelectField, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useUpdateEngagement } from "../../hooks/useEngagements";
import { messageOf } from "../../lib/errors";

const OTHER = "__other";

/**
 * The process owner (PRD §3.20; DECISIONS 110): a role of this engagement, or another role's name
 * typed (a name on the list of names to hide is refused: "Name the role, not the person."). When
 * the engagement came from a Capability Compass hand-off naming one, it is offered; Eric uses it
 * or chooses another. It is never set without him.
 */
export function ProcessOwnerCard({ engagement, roles }: { engagement: Engagement; roles: readonly Role[] }) {
  const people = roles.filter((r) => !r.is_system);
  const roleId = engagement.process_owner_role_id ?? null;
  const other = engagement.process_owner_other ?? "";
  const [choice, setChoice] = useState(roleId ?? (other ? OTHER : ""));
  const [typed, setTyped] = useState(other);
  const [error, setError] = useState<string | null>(null);
  const save = useUpdateEngagement(engagement.id);
  const toast = useToast();
  const offered = engagement.compass?.process_owner ?? "";
  const named = engagement.process_owner ?? "";

  function send(fields: { process_owner_role_id?: string | null; process_owner_other?: string }) {
    setError(null);
    save.mutate(fields, {
      onSuccess: (saved) => {
        setChoice(saved.process_owner_role_id ?? (saved.process_owner_other ? OTHER : ""));
        setTyped(saved.process_owner_other ?? "");
        toast("Process owner saved.");
      },
      onError: (e) => setError(messageOf(e)),
    });
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (save.isPending) return;
    if (choice === OTHER) {
      if (!typed.trim()) {
        setError("Type the role's name, or choose one of the roles.");
        return;
      }
      send({ process_owner_other: typed.trim() });
    } else send({ process_owner_role_id: choice || null, process_owner_other: "" });
  }

  function takeOffered() {
    const match = people.find((r) => r.name.trim().toLowerCase() === offered.trim().toLowerCase());
    send(match ? { process_owner_role_id: match.id } : { process_owner_other: offered });
  }

  return (
    <Card
      title="Process owner"
      description="The role accountable for this process from start to end. A role, never a person's name."
    >
      <form className="setup-form" onSubmit={onSubmit} noValidate>
        <p className="setup-form__note">Process owner: {named || "not named"}</p>
        {offered && !named && (
          <div className="setup-form__note" role="note">
            <p>The Capability Compass hand-off names {offered} as process owner.</p>
            <Button onClick={takeOffered} disabled={save.isPending}>
              Use it
            </Button>
          </div>
        )}
        <SelectField
          label="Process owner"
          value={choice}
          onChange={(value) => {
            setChoice(value);
            setError(null);
          }}
          options={[
            { value: "", label: "Not named" },
            ...people.map((r) => ({ value: r.id, label: r.name })),
            { value: OTHER, label: "Other role…" },
          ]}
        />
        {choice === OTHER && (
          <TextField
            label="The role's name"
            value={typed}
            onChange={setTyped}
            help="For a role outside this map's lanes, for example Head of ground operations."
            error={null}
          />
        )}
        {error && (
          <p className="field__error" role="alert">
            {error}
          </p>
        )}
        <div className="setup-form__actions">
          <Button variant="primary" type="submit">
            {save.isPending ? "Saving…" : "Save process owner"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
