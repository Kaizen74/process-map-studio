import { useState, type FormEvent } from "react";
import type { TestingItem, TestingVerdict } from "../../api/types";
import { Button, Card, Chip, Dialog, ErrorState, Skeleton, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useAddTesting, useDeleteTesting, useTesting, useUpdateTesting } from "../../hooks/useCompass";
import { copyDetailsOf, messageOf } from "../../lib/errors";

const EMPTY =
  "Nothing to test yet. Design principles arrive with a Capability Compass hand-off; you can also add a hypothesis by hand.";
const VERDICT_WORDS: Record<TestingVerdict, string> = { open: "Open", supported: "Supported", refuted: "Refuted" };
const VERDICTS: TestingVerdict[] = ["open", "supported", "refuted"];

function VerdictDialog({
  item,
  engagementId,
  onClose,
}: {
  item: TestingItem;
  engagementId: string;
  onClose: () => void;
}) {
  const update = useUpdateTesting(engagementId);
  const toast = useToast();
  const [verdict, setVerdict] = useState<TestingVerdict>(item.verdict);
  const [codes, setCodes] = useState(item.evidence_refs.join(", "));
  const [note, setNote] = useState(item.note);
  const [error, setError] = useState<string | null>(null);

  function save(event?: FormEvent) {
    event?.preventDefault();
    if (update.isPending) return;
    setError(null);
    const evidence_refs = codes
      .split(/[\s,;]+/)
      .map((c) => c.trim())
      .filter(Boolean);
    update.mutate(
      { id: item.id, patch: { verdict, evidence_refs, note: note.trim() } },
      {
        onSuccess: () => {
          toast(`Verdict for ${item.ref} saved.`);
          onClose();
        },
        onError: (e) => setError(messageOf(e)),
      },
    );
  }

  return (
    <Dialog
      open
      title={`Verdict for ${item.ref}`}
      description={item.text}
      onClose={onClose}
      actions={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={() => save()}>
            {update.isPending ? "Saving…" : "Save verdict"}
          </Button>
        </>
      }
    >
      <form className="setup-form" onSubmit={save} noValidate>
        <fieldset className="role-picks">
          <legend>Verdict</legend>
          {VERDICTS.map((v) => (
            <label key={v} className="testing-verdict">
              <input type="radio" name="testing-verdict" checked={verdict === v} onChange={() => setVerdict(v)} />
              {VERDICT_WORDS[v]}
            </label>
          ))}
        </fieldset>
        <TextField
          label="Step, discrepancy or intent codes"
          value={codes}
          onChange={setCodes}
          help="What the verdict rests on, for example X2, S-04. Needed for Supported or Refuted."
        />
        <TextField label="Note (optional)" value={note} onChange={setNote} />
        {error && (
          <p className="field__error" role="alert">
            {error}
          </p>
        )}
      </form>
    </Dialog>
  );
}

/**
 * What we are testing (DECISIONS 95): the design principles from the hand-off and any hypothesis
 * Eric adds by hand, each with the verdict he sets and the codes behind it. IDs are typed as
 * written in the app that owns them; this app never mints one.
 */
export function TestingCard({ engagementId }: { engagementId: string }) {
  const items = useTesting(engagementId);
  const add = useAddTesting(engagementId);
  const remove = useDeleteTesting(engagementId);
  const toast = useToast();
  const [judging, setJudging] = useState<TestingItem | null>(null);
  const [ref, setRef] = useState("");
  const [text, setText] = useState("");
  const [refutedBy, setRefutedBy] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  function onAdd(event: FormEvent) {
    event.preventDefault();
    if (add.isPending) return;
    setAddError(null);
    const made = ref.trim().toUpperCase();
    add.mutate(
      { ref: ref.trim(), text: text.trim(), refuted_by: refutedBy.trim() },
      {
        onSuccess: () => {
          setRef("");
          setText("");
          setRefutedBy("");
          toast(`${made} added.`);
        },
        onError: (e) => setAddError(messageOf(e)),
      },
    );
  }

  return (
    <Card
      title="What we are testing"
      description="Design principles and operating-model hypotheses this map can support or refute. You set each verdict and name the steps or discrepancies behind it."
    >
      <div className="stack">
        {items.isError ? (
          <ErrorState
            title="The list couldn't be loaded"
            message={messageOf(items.error)}
            details={copyDetailsOf(items.error)}
            onRetry={() => void items.refetch()}
          />
        ) : !items.data ? (
          <Skeleton height="48px" />
        ) : items.data.length === 0 ? (
          <p className="field__help">{EMPTY}</p>
        ) : (
          <ul className="testing-list" aria-label="Items being tested">
            {items.data.map((item) => (
              <li key={item.id} className="testing-item">
                <div className="testing-item__head">
                  <span className="mono testing-item__ref">{item.ref}</span>
                  <Chip>{item.origin === "compass" ? "From the hand-off" : "Added by you"}</Chip>
                  <span className={`testing-item__verdict testing-item__verdict--${item.verdict}`}>
                    {VERDICT_WORDS[item.verdict]}
                    {item.evidence_refs.length > 0 && (
                      <>
                        {" · "}
                        <span className="mono">{item.evidence_refs.join(", ")}</span>
                      </>
                    )}
                  </span>
                </div>
                <p className="testing-item__text">{item.text}</p>
                {item.refuted_by && <p className="field__help">Refuted by: {item.refuted_by}</p>}
                {item.note && <p className="field__help">Note: {item.note}</p>}
                <div className="role-row__actions">
                  <Button variant="link" aria-label={`Set verdict for ${item.ref}`} onClick={() => setJudging(item)}>
                    Set verdict
                  </Button>
                  {item.origin === "owner" && (
                    <Button
                      variant="link"
                      aria-label={`Remove ${item.ref}`}
                      onClick={() => {
                        setRowError(null);
                        remove.mutate(item.id, {
                          onSuccess: () => toast(`${item.ref} removed.`),
                          onError: (e) => setRowError(messageOf(e)),
                        });
                      }}
                    >
                      Remove
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
        {rowError && (
          <p className="field__error" role="alert">
            {rowError}
          </p>
        )}
        <form className="role-add setup-form" onSubmit={onAdd} noValidate>
          <h3 className="role-add__title">Add a hypothesis</h3>
          <TextField
            label="ID"
            value={ref}
            onChange={setRef}
            help="As written in the app it comes from, for example H2. This app doesn't make these up."
          />
          <TextField label="What is being tested" value={text} onChange={setText} />
          <TextField label="What would refute it (optional)" value={refutedBy} onChange={setRefutedBy} />
          {addError && (
            <p className="field__error" role="alert">
              {addError}
            </p>
          )}
          <div>
            <Button type="submit">{add.isPending ? "Adding…" : "Add item"}</Button>
          </div>
        </form>
      </div>
      {judging && <VerdictDialog item={judging} engagementId={engagementId} onClose={() => setJudging(null)} />}
    </Card>
  );
}
