import type {
  Alignment,
  AlignmentStatus,
  ColumnMapInput,
  EventLog,
  ImportInput,
  ImportStarted,
  LogUpload,
  MetricScope,
  MetricsResponse,
} from "../lib/systemRecords";
import { request } from "./request";

// System records (API_CONTRACT.md → System records; PRD §3.13; R7).

const enc = encodeURIComponent;

export const listEventLogs = (engagementId: string) =>
  request<EventLog[]>(`/engagements/${enc(engagementId)}/event-logs`);

export const getEventLog = (logId: string) => request<EventLog>(`/event-logs/${enc(logId)}`);

export function uploadEventLog(engagementId: string, upload: LogUpload) {
  const form = new FormData();
  form.append("file", upload.file, upload.file.name);
  form.append("name", upload.name);
  form.append("system", upload.system);
  form.append("timezone", upload.timezone);
  form.append("window_start", upload.window_start);
  form.append("window_end", upload.window_end);
  return request<EventLog>(`/engagements/${enc(engagementId)}/event-logs`, { method: "POST", body: form });
}

export const deleteEventLog = (logId: string) => request<null>(`/event-logs/${enc(logId)}`, { method: "DELETE" });

export const saveColumnMap = (logId: string, body: ColumnMapInput) =>
  request<EventLog>(`/event-logs/${enc(logId)}/column-map`, { method: "PUT", body });

export const saveRoleMap = (logId: string, roles: Record<string, string | null>) =>
  request<EventLog>(`/event-logs/${enc(logId)}/role-map`, { method: "PUT", body: { roles } });

export const startImport = (logId: string, body: ImportInput) =>
  request<ImportStarted>(`/event-logs/${enc(logId)}/import`, { method: "POST", body });

export const getMetrics = <M>(logId: string, scope: MetricScope) =>
  request<MetricsResponse<M>>(`/event-logs/${enc(logId)}/metrics?scope=${scope}`);

export const getAlignment = (logId: string) => request<Alignment>(`/event-logs/${enc(logId)}/alignment`);

export const saveAlignment = (
  logId: string,
  rows: { activity: string; element_id: string | null; status: Exclude<AlignmentStatus, "proposed"> }[],
) => request<Alignment>(`/event-logs/${enc(logId)}/alignment`, { method: "PUT", body: { rows } });

export const suggestAlignment = (logId: string) =>
  request<ImportStarted>(`/event-logs/${enc(logId)}/alignment/suggest`, { method: "POST" });
