import { useState, type FormEvent } from "react";
import { Button, ErrorState, Skeleton, TextAreaField, TextField } from "../../components/common";
import { useAddProbes, useEditProbe, useProbes, useRemoveProbe } from "../../hooks/useInterview";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import type { OwnerProbe } from "../../lib/interview";

/**
 * Your own probes (DECISIONS 113): questions from your desk research to test in the interviews,
 * typed or pasted one per line, with an optional note of what they are about. They are shown
 * beside each guide; they are never a question of the guide, a claim or a step, and they are
 * never sent to Claude or put in a download.
 */
export function ProbesSection({ engagementId }: { engagementId: string }) {
  const probes = useProbes(engagementId);
  const add = useAddProbes(engagementId);
  const [text, setText] = useState("");
  const [about, setAbout] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (add.isPending) return;
    add.mutate(
      { text, about },
      {
        onSuccess: () => {
          setText("");
          setAbout("");
        },
      },
    );
  }

  const list = probes.data ?? [];
  return (
    <section className="interview-templates" aria-labelledby="own-probes-title">
      <h2 id="own-probes-title" className="interview-templates__title">
        Your probes
      </h2>
      <p className="interview-tip">
        Questions from your desk research to test in the interviews, for example from a document review. They are shown
        beside each guide, to use if they help. They are not questions of the guide and nothing here is evidence: only what
        the SME says, once checked against the transcript, reaches the map.
      </p>
      {probes.isPending && <Skeleton height="48px" />}
      {probes.isError && (
        <ErrorState
          title="Your probes couldn't be loaded"
          message={messageOf(probes.error)}
          details={copyDetailsOf(probes.error)}
          onRetry={() => void probes.refetch()}
        />
      )}
      {probes.isSuccess && list.length === 0 && <p className="interview-tip">No probes yet.</p>}
      {list.length > 0 && (
        <ul className="own-probes" aria-label="Your probes">
          {list.map((p) => (
            <ProbeRow key={`${p.id}-${p.text}-${p.about}`} engagementId={engagementId} probe={p} />
          ))}
        </ul>
      )}
      <form className="stack own-probes__form" onSubmit={onSubmit} noValidate>
        <TextAreaField
          label="Probes to add (one per line)"
          value={text}
          onChange={setText}
          error={add.isError ? messageOf(add.error) : null}
          help="Use roles, not names. Each line becomes one probe."
        />
        <TextField
          label="What they are about (optional)"
          value={about}
          onChange={setAbout}
          help="For example: Step 2, storage and build-up planning."
          error={null}
        />
        <div>
          <Button type="submit" variant="primary">
            {add.isPending ? "Adding…" : "Add probes"}
          </Button>
        </div>
      </form>
    </section>
  );
}

function ProbeRow({ engagementId, probe }: { engagementId: string; probe: OwnerProbe }) {
  const edit = useEditProbe(engagementId);
  const remove = useRemoveProbe(engagementId);
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(probe.text);
  const [about, setAbout] = useState(probe.about);
  if (editing) {
    return (
      <li>
        <form
          className="stack"
          onSubmit={(event) => {
            event.preventDefault();
            edit.mutate({ id: probe.id, body: { text, about } }, { onSuccess: () => setEditing(false) });
          }}
        >
          <TextField
            label="Probe"
            value={text}
            onChange={setText}
            error={edit.isError ? messageOf(edit.error) : null}
          />
          <TextField label="What it is about (optional)" value={about} onChange={setAbout} error={null} />
          <div className="own-probes__actions">
            <Button type="submit" variant="primary">
              Save
            </Button>
            <Button onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        </form>
      </li>
    );
  }
  return (
    <li className="own-probes__row">
      <span>
        {probe.text}
        {probe.about && <span className="own-probes__about"> · {probe.about}</span>}
      </span>
      <span className="own-probes__actions">
        <Button variant="link" aria-label={`Edit the probe ${probe.text}`} onClick={() => setEditing(true)}>
          Edit
        </Button>
        <Button
          variant="link"
          aria-label={`Remove the probe ${probe.text}`}
          onClick={() => remove.mutate(probe.id)}
          disabled={remove.isPending}
        >
          Remove
        </Button>
      </span>
      {remove.isError && (
        <span className="field__error" role="alert">
          {messageOf(remove.error)}
        </span>
      )}
    </li>
  );
}
