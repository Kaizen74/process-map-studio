import type {
  Alignment,
  AlignmentDecision,
  CaseKeyMap,
  ColumnMapInput,
  EventLog,
  ImportInput,
  ImportStarted,
  LogUpload,
  MetricScope,
  MetricsResponse,
  SystemTrace,
  SystemVariants,
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

export const saveAlignment = (logId: string, rows: AlignmentDecision[]) =>
  request<Alignment>(`/event-logs/${enc(logId)}/alignment`, { method: "PUT", body: { rows } });

export const suggestAlignment = (logId: string) =>
  request<ImportStarted>(`/event-logs/${enc(logId)}/alignment/suggest`, { method: "POST" });

// Panel 4e, the Volume and wait lens and the Variants tab (R8).
export const getSystemTraces = (versionId: string) => request<SystemTrace[]>(`/versions/${enc(versionId)}/system-traces`);

export const getSystemVariants = (versionId: string) =>
  request<SystemVariants>(`/versions/${enc(versionId)}/system-variants`);

// Case-key maps (R11c): linking two imported logs whose systems give a case different IDs.

export const listCaseKeyMaps = (engagementId: string) =>
  request<CaseKeyMap[]>(`/engagements/${enc(engagementId)}/case-key-maps`);

export function uploadCaseKeyMap(engagementId: string, link: { file: File; fromLogId: string; toLogId: string }) {
  const form = new FormData();
  form.append("file", link.file, link.file.name);
  form.append("from_log_id", link.fromLogId);
  form.append("to_log_id", link.toLogId);
  return request<CaseKeyMap>(`/engagements/${enc(engagementId)}/case-key-maps`, { method: "POST", body: form });
}

export const deleteCaseKeyMap = (engagementId: string, fromLogId: string, toLogId: string) =>
  request<null>(
    `/engagements/${enc(engagementId)}/case-key-maps?from_log_id=${enc(fromLogId)}&to_log_id=${enc(toLogId)}`,
    { method: "DELETE" },
  );
