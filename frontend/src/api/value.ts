import type {
  Assumption,
  Disposition,
  DispositionChoice,
  DispositionRow,
  RoleCosts,
  StepValue,
  ValueOverride,
  ValueReport,
} from "../lib/value";
import { request } from "./request";

// Step disposition and the value calculator (API_CONTRACT.md → Step disposition, Value calculator;
// PRD §3.14-3.15; R9, R10).

const enc = encodeURIComponent;

export const getDispositions = (versionId: string) =>
  request<DispositionRow[]>(`/versions/${enc(versionId)}/dispositions`);

export const setDisposition = (elementId: string, choice: DispositionChoice) =>
  request<DispositionRow>(`/elements/${enc(elementId)}/disposition`, { method: "PUT", body: choice });

export const getValue = (versionId: string, view: "done" | "documented") =>
  request<ValueReport>(`/versions/${enc(versionId)}/value?view=${view}`);

export const setValueOverride = (elementId: string, override: ValueOverride) =>
  request<StepValue>(`/elements/${enc(elementId)}/value-override`, { method: "PUT", body: override });

export const getRoleCosts = (engagementId: string) => request<RoleCosts>(`/engagements/${enc(engagementId)}/role-costs`);

export const setRoleCosts = (engagementId: string, rows: { role_id: string; hourly_cost: number | null; note: string }[]) =>
  request<RoleCosts>(`/engagements/${enc(engagementId)}/role-costs`, { method: "PUT", body: { rows } });

export const getAssumptions = (engagementId: string) =>
  request<Assumption[]>(`/engagements/${enc(engagementId)}/value-assumptions`);

export const setAssumptions = (
  engagementId: string,
  rows: { disposition: Disposition; reduction_pct: number; note: string }[],
) => request<Assumption[]>(`/engagements/${enc(engagementId)}/value-assumptions`, { method: "PUT", body: { rows } });
