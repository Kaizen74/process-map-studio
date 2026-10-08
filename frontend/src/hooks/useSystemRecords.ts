import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { getJob } from "../api/draft";
import {
  deleteEventLog,
  getAlignment,
  getMetrics,
  listEventLogs,
  saveAlignment,
  saveColumnMap,
  saveRoleMap,
  startImport,
  suggestAlignment,
  uploadEventLog,
} from "../api/systemRecords";
import type {
  Alignment,
  AlignmentDecision,
  ColumnMapInput,
  EventLog,
  ImportInput,
  LogUpload,
  MetricScope,
} from "../lib/systemRecords";

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

/** A background job of a log (import or Claude's suggestions), checked every second until it
 * ends; then the given queries are read again. */
function useLogJob(jobId: string | null, refresh: readonly QueryKey[]) {
  const client = useQueryClient();
  return useQuery({
    queryKey: ["jobs", jobId ?? ""],
    queryFn: async () => {
      const job = await getJob(jobId ?? "");
      if (job.status === "done" || job.status === "failed") {
        for (const key of refresh) void client.invalidateQueries({ queryKey: key });
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

/** The import job; when it ends the log list is read again. */
export const useImportJob = (engagementId: string, jobId: string | null) => useLogJob(jobId, [logsKey(engagementId)]);

// --- Matching activities to map steps and the figures (R7b) --------------------------------------

const alignmentKey = (logId: string) => ["event-logs", logId, "alignment"] as const;

/** The log's activities matched to the current map's steps (proposals and Eric's decisions). */
export function useAlignment(logId: string, enabled = true) {
  return useQuery({ queryKey: alignmentKey(logId), queryFn: () => getAlignment(logId), enabled });
}

/**
 * Eric's decisions. Confirmed matches change the draft map (the order basis of its lines and the
 * support of its steps), so the map's reads are refreshed too.
 */
export function useSaveAlignment(logId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (rows: AlignmentDecision[]) => saveAlignment(logId, rows),
    onSuccess: (alignment: Alignment) => {
      client.setQueryData(alignmentKey(logId), alignment);
      void client.invalidateQueries({ queryKey: ["versions", alignment.version_id] });
      void client.invalidateQueries({ queryKey: ["elements"] });
    },
  });
}

/** Claude's suggestions for the activities nobody has matched (a background job). */
export function useSuggestAlignment(logId: string) {
  return useMutation({ mutationFn: () => suggestAlignment(logId) });
}

/** Claude's suggestion job; when it ends the table is read again. */
export const useSuggestJob = (logId: string, jobId: string | null) => useLogJob(jobId, [alignmentKey(logId)]);

/** One scope of the log's stored figures (only groups of at least 5 cases come back). */
export function useMetrics<M>(logId: string, scope: MetricScope, enabled = true) {
  return useQuery({
    queryKey: ["event-logs", logId, "metrics", scope],
    queryFn: () => getMetrics<M>(logId, scope),
    enabled,
  });
}
