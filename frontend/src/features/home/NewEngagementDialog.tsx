import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Button, Dialog, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useCreateEngagement } from "../../hooks/useEngagements";
import { engagementPath } from "../../lib/engagementSteps";
import { messageOf } from "../../lib/errors";
import { validateEngagementName } from "../../lib/validation";

/** Asks for a name, creates the engagement and opens its Setup screen (PRD §5.4 Home). */
export function NewEngagementDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateEngagement();
  const navigate = useNavigate();
  const toast = useToast();

  function close() {
    setName("");
    setError(null);
    onClose();
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const problem = validateEngagementName(name);
    setError(problem);
    if (problem || create.isPending) return;
    create.mutate(
      { name: name.trim() },
      {
        onSuccess: (engagement) => {
          toast("Engagement created.");
          close();
          void navigate(engagementPath(engagement.id, "setup"));
        },
        onError: (e) => setError(messageOf(e)),
      },
    );
  }

  return (
    <Dialog
      open={open}
      title="New engagement"
      description="One engagement maps one process. You can change the name and add its scope on the next screen."
      onClose={close}
      actions={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button variant="primary" type="submit" form="new-engagement-form">
            {create.isPending ? "Creating…" : "Create engagement"}
          </Button>
        </>
      }
    >
      <form id="new-engagement-form" onSubmit={onSubmit} noValidate>
        <TextField
          label="Engagement name"
          value={name}
          onChange={setName}
          error={error}
          help="Usually the process, for example “Aircraft load control”."
        />
      </form>
    </Dialog>
  );
}
