import { useRef, useState, type DragEvent } from "react";
import { Button } from "../../components/common";
import { ACCEPTED_FORMATS } from "../../lib/sources";

/** The large drop zone at the top of Sources (PRD §5.4), with a button for choosing files. */
export function DropZone({ onFiles, busy }: { onFiles: (files: File[]) => void; busy: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setOver(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) onFiles(files);
  }

  return (
    <div
      className={["drop-zone", over ? "drop-zone--over" : ""].filter(Boolean).join(" ")}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
    >
      <p className="drop-zone__title">Drop files here</p>
      <p className="drop-zone__formats">
        Interview transcripts, SOPs, manuals, job descriptions, working spreadsheets and emails:{" "}
        <span className="mono">{ACCEPTED_FORMATS.join(" ")}</span>, up to 50 MB each.
      </p>
      <Button variant="primary" onClick={() => input.current?.click()}>
        {busy ? "Uploading…" : "Choose files"}
      </Button>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPTED_FORMATS.join(",")}
        className="visually-hidden"
        tabIndex={-1}
        aria-hidden="true"
        data-testid="source-file-input"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          if (files.length > 0) onFiles(files);
        }}
      />
    </div>
  );
}
