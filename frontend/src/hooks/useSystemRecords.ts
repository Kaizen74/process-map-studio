import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getJob } from "../api/draft";
import {
  deleteEventLog,
  listEventLogs,
  saveColumnMap,
  saveRoleMap,
  startImport,
  uploadEventLog,
} from "../api/systemRecords";
import type { ColumnMapInput, EventLog, ImportInput, LogUpload } from "../lib/systemRecords";

// System records (PRD §3.13; R7): the engagement's logs and the import wizard's saves.

/** How often to look again while an import runs in the background. */
export const IMPORT_POLL_MS = 1000;

const logsKey = (engagementId: string) => ["engagements", engagementId, "event-logs"] as const;

/** The engagement's logs, oldest first; `enabled` is false while the module is off. */
export function useEventLogs(engagementId: string, enabled = true) {
  return useQuery({ queryKey: logsKey(engagementId), queryFn: () => listEventLogs(engagementId), enabled });
}

/** Puts the log the backend answered with into the list, in place. */
function useLogMutation<TInput>(engagementId: string, save: (input: TInput) => Promise<EventLog>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: save,
    onSuccess: (log) => {
      client.setQueryData<EventLog[]>(logsKey(engagementId), (logs) => {
        if (!logs) return [log];
        return logs.some((l) => l.id === log.id) ? logs.map((l) => (l.id === log.id ? log : l)) : [...logs, log];
      });
    },
  });
}

export const useUploadEventLog = (engagementId: string) =>
  useLogMutation(engagementId, (upload: LogUpload) => uploadEventLog(engagementId, upload));

export const useSaveColumnMap = (engagementId: string, logId: string) =>
  useLogMutation(engagementId, (body: ColumnMapInput) => saveColumnMap(logId, body));

export const useSaveRoleMap = (engagementId: string, logId: string) =>
  useLogMutation(engagementId, (roles: Record<string, string | null>) => saveRoleMap(logId, roles));

export function useDeleteEventLog(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (logId: string) => deleteEventLog(logId),
    onSuccess: (_, logId) => {
      client.setQueryData<EventLog[]>(logsKey(engagementId), (logs) => logs?.filter((l) => l.id !== logId));
    },
  });
}

export function useStartImport(logId: string) {
  return useMutation({ mutationFn: (body: ImportInput) => startImport(logId, body) });
}

/** The import job, checked every second until it ends; then the log list is read again. */
export function useImportJob(engagementId: string, jobId: string | null) {
  const client = useQueryClient();
  return useQuery({
    queryKey: ["jobs", jobId ?? ""],
    queryFn: async () => {
      const job = await getJob(jobId ?? "");
      if (job.status === "done" || job.status === "failed") {
        void client.invalidateQueries({ queryKey: logsKey(engagementId) });
      }
      return job;
    },
    enabled: Boolean(jobId),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status === "done" || status === "failed" ? false : IMPORT_POLL_MS;
    },
  });
}
