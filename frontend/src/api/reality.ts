import type { IntentFields, IntentStatement, RealitySnapshot, VerdictDecided } from "../lib/reality";
import { request } from "./request";

// Intent and Reality (API_CONTRACT.md → Intent, Discrepancies, Reality snapshot; P13).

const enc = encodeURIComponent;

export const getReality = (versionId: string) => request<RealitySnapshot>(`/versions/${enc(versionId)}/reality`);

export const listIntent = (engagementId: string) =>
  request<IntentStatement[]>(`/engagements/${enc(engagementId)}/intent`);

export const addIntent = (engagementId: string, fields: IntentFields) =>
  request<IntentStatement>(`/engagements/${enc(engagementId)}/intent`, { method: "POST", body: fields });

export const updateIntent = (intentId: string, body: { status?: string; note?: string; edits?: IntentFields }) =>
  request<IntentStatement>(`/intent/${enc(intentId)}`, { method: "PATCH", body });

export const extractIntent = (engagementId: string) =>
  request<{ job_id: string }>(`/engagements/${enc(engagementId)}/intent/extract`, { method: "POST" });

export const decideVerdict = (
  itemId: string,
  body: { verdict: string | null; note: string; decision_owner_role_id?: string | null },
) => request<VerdictDecided>(`/discrepancy-items/${enc(itemId)}/verdict`, { method: "PUT", body });
