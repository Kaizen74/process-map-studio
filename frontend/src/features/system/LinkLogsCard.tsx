import { useRef, useState, type FormEvent } from "react";
import { Button, Card, ErrorState, SelectField, Skeleton } from "../../components/common";
import { useToast } from "../../components/shell";
import { CaseKeyMapList } from "../../components/system";
import { useCaseKeyMaps, useDeleteCaseKeyMap, useUploadCaseKeyMap } from "../../hooks/useSystemRecords";
import { copyDetailsOf, fieldOf, messageOf } from "../../lib/errors";
import type { EventLog } from "../../lib/systemRecords";

/**
 * Linked logs (PRD §3.13.1; R11c): when two systems give the same case different IDs, a file of
 * pairs links their imported logs, and the backend works out the end-to-end time across both.
 * Shown once two logs are imported.
 */
export function LinkLogsCard({ engagementId, logs }: { engagementId: string; logs: readonly EventLog[] }) {
  const maps = useCaseKeyMaps(engagementId, true);
  const upload = useUploadCaseKeyMap(engagementId);
  const remove = useDeleteCaseKeyMap(engagementId);
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [first, setFirst] = useState(logs[0]?.id ?? "");
  const [second, setSecond] = useState(logs[1]?.id ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [missing, setMissing] = useState<string | null>(null);
  const options = logs.map((l) => ({ value: l.id, label: l.name }));
  const blamed = fieldOf(upload.error);
  const errorFor = (field: string) => (blamed === field ? messageOf(upload.error) : null);
  const name = (id: string) => logs.find((l) => l.id === id)?.name ?? "";

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (first === second) return setMissing("Choose two different logs.");
    if (!file) return setMissing("Choose the file of case IDs first.");
    setMissing(null);
    upload.mutate(
      { file, fromLogId: first, toLogId: second },
      {
        onSuccess: (map) => {
          setFile(null);
          toast(`${map.from_log_name} and ${map.to_log_name} linked.`);
        },
      },
    );
  }

  return (
    <Card
      title="Linked logs"
      description="When two systems give the same case different IDs (a flight number in one, a turnaround reference in the other), link their logs with a file of pairs: the first column holds the first log's case IDs, the second column the second log's, with a header row. The app then shows the end-to-end time across both systems. Without a link, each log is analysed on its own."
    >
      <form className="system-upload" onSubmit={onSubmit} noValidate>
        <div className="system-upload__fields">
          <SelectField
            label="First log (first column)"
            value={first}
            options={options}
            onChange={setFirst}
            error={errorFor("from_log_id")}
          />
          <SelectField
            label="Second log (second column)"
            value={second}
            options={options}
            onChange={setSecond}
            error={errorFor("to_log_id")}
          />
        </div>
        <div className="system-upload__file">
          <Button onClick={() => input.current?.click()}>{file ? "Choose another file" : "Choose file"}</Button>
          <span className="system-upload__chosen" aria-live="polite">
            {file ? file.name : "No file chosen"}
          </span>
          <input
            ref={input}
            type="file"
            accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            className="visually-hidden"
            tabIndex={-1}
            aria-hidden="true"
            data-testid="case-key-file-input"
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              event.target.value = "";
            }}
          />
        </div>
        {(missing ?? errorFor("file")) && (
          <p className="danger-note" role="alert">
            {missing ?? errorFor("file")}
          </p>
        )}
        {upload.isError && !blamed && (
          <p className="danger-note" role="alert">
            {messageOf(upload.error)}
          </p>
        )}
        <div>
          <Button type="submit" variant="primary" aria-busy={upload.isPending || undefined}>
            {upload.isPending ? "Linking…" : "Link logs"}
          </Button>
        </div>
      </form>
      {maps.isPending && <Skeleton height="60px" />}
      {maps.isError && (
        <ErrorState
          title="The linked logs couldn't be loaded"
          message={messageOf(maps.error)}
          details={copyDetailsOf(maps.error)}
          onRetry={() => void maps.refetch()}
        />
      )}
      {maps.data && (
        <CaseKeyMapList
          maps={maps.data}
          busy={remove.isPending}
          onRemove={(map) =>
            remove.mutate(
              { fromLogId: map.from_log_id, toLogId: map.to_log_id },
              { onSuccess: () => toast(`${name(map.from_log_id)} and ${name(map.to_log_id)} unlinked.`) },
            )
          }
        />
      )}
      {remove.isError && (
        <p className="danger-note" role="alert">
          {messageOf(remove.error)}
        </p>
      )}
    </Card>
  );
}
