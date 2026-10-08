import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { Button, Card, Chip, Dialog, EmptyState, ErrorState, Skeleton } from "../../components/common";
import { useToast } from "../../components/shell";
import { LogList, ValidationReportView } from "../../components/system";
import { useEngagement } from "../../hooks/useEngagements";
import { useSettings } from "../../hooks/useSettings";
import { useDeleteEventLog, useEventLogs } from "../../hooks/useSystemRecords";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { formatDateTime } from "../../lib/format";
import { DATA_REQUEST_FILES, dataRequestUrl, type EventLog } from "../../lib/systemRecords";
import { EngagementProblem } from "../engagement/EngagementProblem";
import { ImportWizard } from "./ImportWizard";
import { UploadLogForm } from "./UploadLogForm";
import "./system.css";

function TemplateCard() {
  return (
    <Card
      title="Ask IT for an extract"
      description="Send this data request template to the system owner. It lists the columns needed and the privacy rules: roles rather than user IDs, no comments, no customer details."
    >
      <ul className="system-templates">
        {DATA_REQUEST_FILES.map((f) => (
          <li key={f.format}>
            <a href={dataRequestUrl(f.format)} download>
              Download {f.label}
            </a>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** An imported log: its final report. Matching to steps and the figures come with R7b. */
function ImportedLog({ log }: { log: EventLog }) {
  return (
    <Card
      title={log.name}
      description={`Imported${log.approved_at ? ` ${formatDateTime(log.approved_at)}` : ""}, approved by ${log.approved_by_role}. Time zone ${log.timezone}.`}
    >
      {log.validation_report && <ValidationReportView report={log.validation_report} final />}
    </Card>
  );
}

function OpenLog({ engagementId, log }: { engagementId: string; log: EventLog }) {
  if (log.status === "imported") return <ImportedLog log={log} />;
  if (!log.file_held || log.status === "failed") {
    return (
      <Card title={log.name}>
        <p>
          The file is no longer in memory (the app was restarted, or the import didn't finish), so it can't be imported.
          Delete this log and upload the file again.
        </p>
      </Card>
    );
  }
  return <ImportWizard key={log.id} engagementId={engagementId} log={log} />;
}

/**
 * System records (PRD §5.4, optional; §3.13): the data request template, uploading logs and the
 * stepped import with its privacy safeguards. Off until Eric switches the module on in Settings.
 */
export function SystemRecordsScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const settings = useSettings();
  const on = settings.data?.system_records_enabled === true;
  const logs = useEventLogs(engagementId, on);
  const remove = useDeleteEventLog(engagementId);
  const [params, setParams] = useSearchParams();
  const [deleting, setDeleting] = useState<EventLog | null>(null);
  const toast = useToast();

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }

  const openId = params.get("log");
  const open = (logs.data ?? []).find((l) => l.id === openId) ?? null;
  const setOpen = (id: string | null) => setParams(id ? { log: id } : {}, { replace: true });

  function confirmDelete() {
    if (!deleting) return;
    const gone = deleting;
    remove.mutate(gone.id, {
      onSuccess: () => {
        toast(`${gone.name} deleted.`);
        if (openId === gone.id) setOpen(null);
        setDeleting(null);
      },
    });
  }

  return (
    <main className="screen" aria-labelledby="system-title">
      <div>
        <h1 id="system-title">
          System records <Chip>Optional</Chip>
        </h1>
        <p className="screen__intro">
          Real volumes, waiting times and hidden work from a system&apos;s event log, set beside what people describe.
          Figures are shown per step and role only, never per person, and never for fewer than 5 cases.
        </p>
      </div>
      {settings.isPending && <Skeleton height="120px" />}
      {settings.isError && (
        <ErrorState
          title="Your settings couldn't be loaded"
          message={messageOf(settings.error)}
          details={copyDetailsOf(settings.error)}
          onRetry={() => void settings.refetch()}
        />
      )}
      {settings.isSuccess && !on && (
        <EmptyState
          message="System records is switched off. Switch it on under Optional modules in Settings to import event logs for this engagement."
          action={<Link to="/settings">Go to Settings</Link>}
        />
      )}
      {on && (
        <>
          <div className="system__cards">
            <TemplateCard />
            <UploadLogForm engagementId={engagementId} onUploaded={(log) => setOpen(log.id)} />
          </div>
          <section className="system__logs" aria-labelledby="system-logs-title">
            <h2 id="system-logs-title">Logs</h2>
            {logs.isPending && <Skeleton height="80px" />}
            {logs.isError && (
              <ErrorState
                title="The logs couldn't be loaded"
                message={messageOf(logs.error)}
                details={copyDetailsOf(logs.error)}
                onRetry={() => void logs.refetch()}
              />
            )}
            {logs.isSuccess && logs.data.length === 0 && (
              <EmptyState message="No logs yet. A system's event log shows how often each step really happens, how long work waits between steps, and work the map doesn't show. Start by sending IT the data request template above, then upload the extract they send back." />
            )}
            {logs.isSuccess && logs.data.length > 0 && (
              <LogList logs={logs.data} openId={open?.id ?? null} onOpen={setOpen} onDelete={setDeleting} />
            )}
          </section>
          {open && <OpenLog engagementId={engagementId} log={open} />}
        </>
      )}
      <Dialog
        open={deleting !== null}
        title={`Delete ${deleting?.name ?? "this log"}?`}
        description="This removes the log, its events and its figures from this engagement. The map keeps everything you confirmed on it."
        onClose={() => setDeleting(null)}
        actions={
          <>
            <Button onClick={() => setDeleting(null)}>Cancel</Button>
            <Button variant="danger" onClick={confirmDelete} aria-busy={remove.isPending || undefined}>
              Delete log
            </Button>
          </>
        }
      >
        {remove.isError && (
          <p className="danger-note" role="alert">
            {messageOf(remove.error)}
          </p>
        )}
      </Dialog>
    </main>
  );
}
