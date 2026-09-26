import { useState, type FormEvent } from "react";
import { Button, Card, ErrorState, Skeleton, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useAddRedactionTerm, useDeleteRedactionTerm, useRedactionTerms } from "../../hooks/useRedaction";
import { messageOf, copyDetailsOf } from "../../lib/errors";

const NAME_MESSAGE = "Please enter a name of up to 120 characters, on one line.";

/**
 * Names to hide (PRD §5.4 Sources, §3.8 G10): shown only here, in the speaker-mapping card and in
 * the correction editor. Everywhere else the app shows the replacement.
 */
export function RedactionList({ engagementId }: { engagementId: string }) {
  const terms = useRedactionTerms(engagementId);
  const add = useAddRedactionTerm(engagementId);
  const remove = useDeleteRedactionTerm(engagementId);
  const toast = useToast();
  const [term, setTerm] = useState("");
  const [replacement, setReplacement] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);

  function onAdd(event: FormEvent) {
    event.preventDefault();
    const name = term.trim();
    setError(null);
    if (!name || name.length > 120) {
      setError(NAME_MESSAGE);
      return;
    }
    add.mutate(
      { term: name, replacement: replacement.trim() },
      {
        onSuccess: () => {
          setTerm("");
          setReplacement("");
          toast("Name added. It is now hidden everywhere else in the app.");
        },
        onError: (e) => setError(messageOf(e)),
      },
    );
  }

  return (
    <div data-owner-only="redaction-list">
      <Card
        title="Names to hide"
        description="These names never appear outside this list, the speaker mapping and the correction editor. Names of speakers are added automatically; add nicknames or other names people are called by."
      >
        <div className="stack">
          {terms.isPending && <Skeleton height="28px" />}
          {terms.isError && (
            <ErrorState
              title="The list of names couldn't be loaded"
              message={messageOf(terms.error)}
              details={copyDetailsOf(terms.error)}
              onRetry={() => void terms.refetch()}
            />
          )}
          {terms.isSuccess && terms.data.length === 0 && (
            <p className="inline-note">No names yet. Speaker names are added when a transcript is read.</p>
          )}
          {terms.isSuccess && terms.data.length > 0 && (
            <ul className="name-list" aria-label="Names hidden in this engagement">
              {terms.data.map((item) => (
                <li key={item.id} className="chip chip--neutral name-list__chip">
                  <span>
                    {item.term} <span className="name-list__shown">→ shown as {item.replacement || "[name]"}</span>
                  </span>
                  {item.origin === "speaker_map" && <span className="name-list__tag">from speaker label</span>}
                  <button
                    type="button"
                    className="chip-field__remove"
                    aria-label={`Stop hiding ${item.term}`}
                    onClick={() => {
                      setListError(null);
                      remove.mutate(item.id, {
                        onSuccess: () => toast("Name removed from the list."),
                        onError: (e) => setListError(messageOf(e)),
                      });
                    }}
                  >
                    <span aria-hidden="true">×</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {listError && (
            <p className="field__error" role="alert">
              {listError}
            </p>
          )}
          <form className="name-form" onSubmit={onAdd} noValidate>
            <TextField label="Name to hide" value={term} onChange={setTerm} error={error} />
            <TextField
              label="Show instead (optional)"
              value={replacement}
              onChange={setReplacement}
              help="A role, for example “Load controller”. Leave empty to show [name]."
            />
            <div className="name-form__actions">
              <Button type="submit">{add.isPending ? "Adding…" : "Add name"}</Button>
            </div>
          </form>
        </div>
      </Card>
    </div>
  );
}
