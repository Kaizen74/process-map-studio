import { useEffect, useState } from "react";
import { Button, Card, CheckboxField, SelectField, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import {
  ColumnMapTable,
  RoleMapTable,
  UNKNOWN_ROLE,
  ValidationReportView,
  WizardProgress,
} from "../../components/system";
import { useRoles } from "../../hooks/useRoles";
import { useImportJob, useSaveColumnMap, useSaveRoleMap, useStartImport } from "../../hooks/useSystemRecords";
import { fieldOf, messageOf } from "../../lib/errors";
import { TIME_ZONES, TIMESTAMP_FORMATS, WIZARD_STEPS, type EventLog } from "../../lib/systemRecords";

const DETECTED = "";

/** The roles chosen so far: each user ID's saved choice, else the backend's suggestion. */
function initialRoles(log: EventLog): Record<string, string> {
  const out: Record<string, string> = {};
  for (const r of log.resources) {
    if (r.value in log.role_map) out[r.value] = log.role_map[r.value] ?? UNKNOWN_ROLE;
    else out[r.value] = r.suggested_role_id ?? "";
  }
  return out;
}

/**
 * The stepped import wizard (PRD §5.4 System records; §3.13.3): Map columns → Time zone → Map users
 * to roles → Validation report → approval and Import. Each save goes to the backend, which checks
 * everything again on import.
 */
export function ImportWizard({ engagementId, log }: { engagementId: string; log: EventLog }) {
  const [step, setStep] = useState(log.status === "mapped" ? 3 : 0);
  const [columns, setColumns] = useState(log.column_map);
  const [format, setFormat] = useState(log.timestamp_format ?? DETECTED);
  const [zone, setZone] = useState(log.timezone);
  const [roles, setRoles] = useState(() => initialRoles(log));
  const [approved, setApproved] = useState(false);
  const [approver, setApprover] = useState(log.approved_by_role);
  const [problem, setProblem] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  const engagementRoles = useRoles(engagementId);
  const saveColumns = useSaveColumnMap(engagementId, log.id);
  const saveRoles = useSaveRoleMap(engagementId, log.id);
  const start = useStartImport(log.id);
  const job = useImportJob(engagementId, jobId);
  const toast = useToast();

  const go = (n: number) => {
    setProblem(null);
    setStep(n);
  };
  const fail = (error: unknown, back?: number) => {
    setProblem(messageOf(error));
    if (back !== undefined) setStep(back);
  };

  function saveColumnStep() {
    saveColumns.mutate(
      { columns, timestamp_format: format === DETECTED ? null : format, timezone: zone },
      {
        onSuccess: (saved) => {
          setRoles(initialRoles(saved));
          go(2);
        },
        onError: (e) => fail(e, ["columns", "timestamp_format"].includes(fieldOf(e) ?? "") ? 0 : undefined),
      },
    );
  }

  function saveRoleStep() {
    const left = log.resources.filter((r) => !roles[r.value]).length;
    if (left > 0) {
      setProblem(`Choose a role or Unknown role for every user ID (${left} left).`);
      return;
    }
    if (log.resources.length === 0) return go(3);
    const chosen = Object.fromEntries(
      Object.entries(roles).map(([id, choice]) => [id, choice === UNKNOWN_ROLE ? null : choice]),
    );
    saveRoles.mutate(chosen, { onSuccess: () => go(3), onError: (e) => fail(e) });
  }

  function runImport() {
    setProblem(null);
    start.mutate(
      { approved_by_role: approver.trim(), confirm_approval: approved },
      { onSuccess: (started) => setJobId(started.job_id), onError: (e) => fail(e) },
    );
  }

  const ended = job.data?.status === "done" || job.data?.status === "failed";
  const running = jobId !== null && !ended;
  const imported = job.data?.status === "done";
  useEffect(() => {
    if (imported) toast(`${log.name} imported.`);
  }, [imported, log.name, toast]);

  const report = log.validation_report;
  const zones = TIME_ZONES.includes(zone) ? TIME_ZONES : [zone, ...TIME_ZONES];
  const busy = saveColumns.isPending || saveRoles.isPending || start.isPending || running;

  return (
    <Card title={`Import ${log.name}`} description={`Step ${step + 1} of ${WIZARD_STEPS.length}: ${WIZARD_STEPS[step]}`}>
      <div className="system-wizard">
        <WizardProgress current={step} />
        {step === 0 && (
          <>
            <ColumnMapTable columns={columns} onChange={(header, field) => setColumns({ ...columns, [header]: field })} />
            <SelectField
              label="Date format"
              value={format}
              options={[
                { value: DETECTED, label: `As detected${report?.timestamp_format ? `: ${report.timestamp_format}` : ""}` },
                ...TIMESTAMP_FORMATS.map((f) => ({ value: f.value, label: f.example })),
              ]}
              onChange={setFormat}
              help="Change it only if the validation report shows dates the app couldn't read."
            />
          </>
        )}
        {step === 1 && (
          <SelectField
            label="Time zone of the times in the file"
            value={zone}
            options={zones.map((z) => ({ value: z, label: z.replace("_", " ") }))}
            onChange={setZone}
            help="Waits and months are worked out in this time zone. Ask IT if you're not sure."
          />
        )}
        {step === 2 && (
          <RoleMapTable
            resources={log.resources}
            roles={(engagementRoles.data ?? []).filter((r) => !r.is_system)}
            value={roles}
            onChange={(id, choice) => setRoles({ ...roles, [id]: choice })}
          />
        )}
        {step === 3 && report && <ValidationReportView report={report} />}
        {step === 4 && (
          <div className="system-wizard__approve">
            <CheckboxField
              label="The data owner approved this extract for this purpose"
              checked={approved}
              onChange={setApproved}
              help="Measuring volumes and waiting times in this process; no individual performance analysis."
            />
            <TextField
              label="Approver's role"
              value={approver}
              onChange={setApprover}
              help="A role, not a name, for example Head of ground operations."
            />
            {running && (
              <p role="status">
                Importing… {job.data?.message ?? "The file is being read; the user IDs are converted to roles."}
              </p>
            )}
            {job.data?.status === "failed" && (
              <p className="danger-note" role="alert">
                {job.data.error || "The import didn't finish."}
              </p>
            )}
          </div>
        )}
        {problem && (
          <p className="danger-note" role="alert">
            {problem}
          </p>
        )}
        <div className="system-wizard__actions">
          {step > 0 && !busy && <Button onClick={() => go(step - 1)}>Back</Button>}
          {step === 0 && (
            <Button variant="primary" onClick={() => go(1)}>
              Next: time zone
            </Button>
          )}
          {step === 1 && (
            <Button variant="primary" onClick={saveColumnStep} aria-busy={saveColumns.isPending || undefined}>
              {saveColumns.isPending ? "Saving…" : "Next: map users to roles"}
            </Button>
          )}
          {step === 2 && (
            <Button variant="primary" onClick={saveRoleStep} aria-busy={saveRoles.isPending || undefined}>
              {saveRoles.isPending ? "Saving…" : "Next: validation report"}
            </Button>
          )}
          {step === 3 && (
            <Button
              variant="primary"
              onClick={() =>
                report?.refused
                  ? setProblem("Fix the problems above first: go back to Map columns, or upload a corrected extract.")
                  : go(4)
              }
            >
              Next: approve and import
            </Button>
          )}
          {step === 4 && !running && (
            <Button variant="primary" onClick={runImport} aria-busy={start.isPending || undefined}>
              Import
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
