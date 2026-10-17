import { useRef, useState, type FormEvent } from "react";
import { Button, Card, SelectField, TextField } from "../../components/common";
import { fieldOf, messageOf } from "../../lib/errors";
import { zoneOptions, type EventLog } from "../../lib/systemRecords";
import { useSettings } from "../../hooks/useSettings";
import { useUploadEventLog } from "../../hooks/useSystemRecords";

/**
 * Upload one log (PRD §3.13.3 step 1): the file is held in memory only until it is imported or
 * deleted, because it may carry user IDs.
 */
export function UploadLogForm({ engagementId, onUploaded }: { engagementId: string; onUploaded: (log: EventLog) => void }) {
  const upload = useUploadEventLog(engagementId);
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [system, setSystem] = useState("");
  const settings = useSettings();
  // Starts with Settings → Regional (R10) until Eric picks another zone for this log.
  const [picked, setZone] = useState<string | null>(null);
  const zone = picked ?? settings.data?.default_timezone ?? "Asia/Singapore";
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [missing, setMissing] = useState<string | null>(null);

  const error = upload.error;
  const blamed = fieldOf(error);
  const errorFor = (field: string) => (blamed === field ? messageOf(error) : null);

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return setMissing("Choose the file from IT first.");
    if (!name.trim()) return setMissing("Give the log a name, for example DCS extract.");
    setMissing(null);
    upload.mutate(
      { file, name: name.trim(), system: system.trim(), timezone: zone, window_start: from, window_end: to },
      {
        onSuccess: (log) => {
          setFile(null);
          setName("");
          setSystem("");
          setFrom("");
          setTo("");
          onUploaded(log);
        },
      },
    );
  }

  return (
    <Card
      title="Upload a log"
      description="A CSV file (UTF-8) or an Excel workbook (.xlsx; its first sheet is read) of up to 100 MB, one per system. The file stays in memory only until you import it."
    >
      <form className="system-upload" onSubmit={onSubmit} noValidate>
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
            data-testid="log-file-input"
            onChange={(event) => {
              const chosen = event.target.files?.[0] ?? null;
              event.target.value = "";
              setFile(chosen);
              if (chosen && !name) setName(chosen.name.replace(/\.[^.]+$/, ""));
            }}
          />
        </div>
        {errorFor("file") && (
          <p className="danger-note" role="alert">
            {errorFor("file")}
          </p>
        )}
        <div className="system-upload__fields">
          <TextField label="Name" value={name} onChange={setName} error={errorFor("name")} />
          <TextField
            label="System (optional)"
            value={system}
            onChange={setSystem}
            placeholder="For example DCS"
            error={errorFor("system")}
          />
          <SelectField
            label="Time zone"
            value={zone}
            options={zoneOptions(zone)}
            onChange={setZone}
            error={errorFor("timezone")}
          />
          <TextField
            label="Window starts (optional)"
            value={from}
            onChange={setFrom}
            placeholder="2026-03-02"
            mono
            error={errorFor("window_start")}
          />
          <TextField
            label="Window ends (optional)"
            value={to}
            onChange={setTo}
            placeholder="2026-04-26"
            mono
            error={errorFor("window_end")}
          />
        </div>
        {(missing || (error && !blamed)) && (
          <p className="danger-note" role="alert">
            {missing ?? messageOf(error)}
          </p>
        )}
        <div>
          <Button type="submit" variant="primary" aria-busy={upload.isPending || undefined}>
            {upload.isPending ? "Uploading…" : "Upload"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
