import { request } from "./request";
import type {
  AnotherCountry,
  AnotherFlow,
  Engagement,
  EngagementCreate,
  EngagementSummary,
  Readiness,
  ScopeFields,
} from "./types";

export const listEngagements = () => request<EngagementSummary[]>("/engagements");

export const getEngagement = (id: string) => request<Engagement>(`/engagements/${encodeURIComponent(id)}`);

export const createEngagement = (fields: EngagementCreate) =>
  request<Engagement>("/engagements", { method: "POST", body: fields });

export const updateEngagement = (id: string, fields: ScopeFields) =>
  request<Engagement>(`/engagements/${encodeURIComponent(id)}`, { method: "PATCH", body: fields });

export const deleteEngagement = (id: string) =>
  request<null>(`/engagements/${encodeURIComponent(id)}`, { method: "DELETE" });

export const getReadiness = (id: string) =>
  request<Readiness>(`/engagements/${encodeURIComponent(id)}/readiness`);

/** Map this process in another country (DECISIONS 98): scope card, conventions and lane names only. */
export const startAnotherCountry = (id: string, fields: AnotherCountry) =>
  request<Engagement>(`/engagements/${encodeURIComponent(id)}/another-country`, { method: "POST", body: fields });

/** Map another flow from these sources (DECISIONS 81): a new engagement, same documents and roles. */
export const startAnotherFlow = (id: string, fields: AnotherFlow) =>
  request<Engagement>(`/engagements/${encodeURIComponent(id)}/another-flow`, { method: "POST", body: fields });
