import { useRef, useState } from "react";
import { useParams, useSearchParams } from "react-router";
import type { Source, SourcePatch } from "../../api/types";
import { Button, Card, Dialog, EmptyState, ErrorState, Skeleton } from "../../components/common";
import { useToast } from "../../components/shell";
import { useEngagement, useReadiness } from "../../hooks/useEngagements";
import { useDeleteSource, useSources, useUpdateSource, useUploadSource } from "../../hooks/useSources";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { plural } from "../../lib/format";
import { uploadProblem } from "../../lib/sources";
import { EngagementProblem } from "../engagement/EngagementProblem";
import { DropZone } from "./DropZone";
import { SourceRegistry } from "./SourceRegistry";
import { SourceViewer } from "./SourceViewer";
import "./sources.css";

interface UploadNote {
  key: number;
  name: string;
  state: "reading" | "failed";
  message?: string;
}

/** Sources (PRD §5.4): drop zone, registry, full-width viewer and the readiness line. */
export function SourcesScreen() {
  const { engagementId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const openId = params.get("source");
  const engagement = useEngagement(engagementId);
  const sources = useSources(engagementId);
  const readiness = useReadiness(engagementId);
  const upload = useUploadSource(engagementId);
  const update = useUpdateSource(engagementId);
  const remove = useDeleteSource(engagementId);
  const toast = useToast();
  const [notes, setNotes] = useState<UploadNote[]>([]);
  const [busy, setBusy] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Source | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const nextKey = useRef(0);

  function open(source: Source | null) {
    setParams(source ? { source: source.id } : {}, { replace: true });
  }

  async function addFiles(files: File[]) {
    setBusy(true);
    let uploaded = 0;
    for (const file of files) {
      const key = nextKey.current++;
      const problem = uploadProblem(file);
      if (problem) {
        setNotes((n) => [...n, { key, name: file.name, state: "failed", message: problem }]);
        continue;
      }
      setNotes((n) => [...n, { key, name: file.name, state: "reading" }]);
      try {
        await upload.mutateAsync({ file });
        uploaded += 1;
        setNotes((n) => n.filter((note) => note.key !== key));
      } catch (e) {
        setNotes((n) =>
          n.map((note) => (note.key === key ? { ...note, state: "failed", message: messageOf(e) } : note)),
        );
      }
    }
    setBusy(false);
    if (uploaded > 0) toast(`${plural(uploaded, "file")} uploaded.`);
  }

  function change(source: Source, patch: SourcePatch) {
    setRowError(null);
    update.mutate(
      { id: source.id, patch },
      { onError: (e) => setRowError(`${source.filename}: ${messageOf(e)}`) },
    );
  }

  function confirmDelete() {
    if (!deleting || remove.isPending) return;
    const target = deleting;
    remove.mutate(target.id, {
      onSuccess: () => {
        if (openId === target.id) open(null);
        setDeleting(null);
        toast(`${target.filename} deleted.`);
      },
      onError: (e) => setDeleteError(messageOf(e)),
    });
  }

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }

  const list = sources.data ?? [];
  const missing = readiness.data?.missing ?? [];

  return (
    <main className="screen" aria-labelledby="sources-title">
      <div>
        <h1 id="sources-title">Sources</h1>
        <p className="screen__intro">
          The documents and interviews this map is drawn from. Every step on the map will point back to them.
        </p>
      </div>

      <DropZone onFiles={(files) => void addFiles(files)} busy={busy} />

      {notes.length > 0 && (
        <ul className="upload-notes" aria-label="Uploads">
          {notes.map((note) => (
            <li key={note.key} className={`upload-note upload-note--${note.state}`}>
              <span className="upload-note__name">{note.name}</span>
              {note.state === "reading" ? (
                <span className="upload-note__state" role="status">
                  Reading…
                </span>
              ) : (
                <>
                  <span className="upload-note__state" role="alert">
                    Not uploaded. {note.message}
                  </span>
                  <Button
                    variant="link"
                    aria-label={`Dismiss the message about ${note.name}`}
                    onClick={() => setNotes((n) => n.filter((x) => x.key !== note.key))}
                  >
                    Dismiss
                  </Button>
                </>
              )}
            </li>
          ))}
        </ul>
      )}

      {sources.isPending && (
        <Card title="Your sources">
          <div className="stack" aria-busy="true">
            <Skeleton height="28px" />
            <Skeleton height="28px" />
          </div>
        </Card>
      )}
      {sources.isError && (
        <ErrorState
          title="The sources couldn't be loaded"
          message={messageOf(sources.error)}
          details={copyDetailsOf(sources.error)}
          onRetry={() => void sources.refetch()}
        />
      )}
      {sources.isSuccess && list.length === 0 && notes.length === 0 && (
        <EmptyState message="Add the interview transcript and at least one SOP to start. Drop them above or choose files." />
      )}
      {list.length > 0 && (
        <SourceRegistry
          sources={list}
          selectedId={openId}
          onOpen={open}
          onChange={change}
          onDelete={(source) => {
            setDeleteError(null);
            setDeleting(source);
          }}
        />
      )}
      {rowError && (
        <p className="field__error" role="alert">
          {rowError}
        </p>
      )}

      {readiness.data && (
        <div className={["readiness-line", missing.length ? "" : "readiness-line--ready"].join(" ")}>
          {missing.length === 0 ? (
            <p>
              <strong>Ready to draft.</strong> Drafting arrives in build phase P3.
            </p>
          ) : (
            <>
              <p>
                <strong>Before drafting:</strong>
              </p>
              <ul className="readiness-line__list">
                {missing.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {openId && <SourceViewer key={openId} sourceId={openId} onClose={() => open(null)} />}

      <Dialog
        open={deleting !== null}
        title={`Delete ${deleting?.filename ?? ""}?`}
        description={`This removes the file from this computer, its ${plural(deleting?.segment_count ?? 0, "passage")} and any images found in it. Steps that cite it will lose that evidence. This can't be undone.`}
        onClose={() => setDeleting(null)}
        actions={
          <>
            <Button onClick={() => setDeleting(null)}>{deleteError ? "Close" : "Cancel"}</Button>
            {!deleteError && (
              <Button variant="danger" onClick={confirmDelete}>
                {remove.isPending ? "Deleting…" : "Delete source"}
              </Button>
            )}
          </>
        }
      >
        {deleteError && (
          <p className="field__error" role="alert">
            {deleteError}
          </p>
        )}
      </Dialog>
    </main>
  );
}
