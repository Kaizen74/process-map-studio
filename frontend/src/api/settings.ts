import { request } from "./request";
import type { AiUsage, ConnectionTest, ModelChoices, ModelUpdate, Settings, WebSearchTest } from "./types";

export const getSettings = () => request<Settings>("/settings");

export const saveProfile = (ownerName: string) =>
  request<Settings>("/settings/profile", { method: "PUT", body: { owner_name: ownerName } });

export const saveApiKey = (apiKey: string) =>
  request<Settings>("/settings/key", { method: "PUT", body: { anthropic_api_key: apiKey } });

export const testConnection = () =>
  request<ConnectionTest>("/settings/test-connection", { method: "POST" });

export const listModels = () => request<ModelChoices>("/settings/models");

export const saveModel = (update: ModelUpdate) =>
  request<Settings>("/settings/model", { method: "PUT", body: update });

export const getAiUsage = (limit = 50) => request<AiUsage>(`/settings/usage?limit=${limit}`);

// Web research for gap analysis B (phase P10).
export const saveResearch = (enabled: boolean) =>
  request<Settings>("/settings/research", { method: "PUT", body: { web_research_enabled: enabled } });

export const testWebSearch = () => request<WebSearchTest>("/settings/test-web-search", { method: "POST" });

// Optional modules (R7, R10; decision A): a field left out keeps its value.
export type ModuleSwitches = Partial<
  Pick<Settings, "system_records_enabled" | "gap_analysis_enabled" | "value_enabled" | "reality_views_enabled">
>;

export const saveModules = (modules: ModuleSwitches) =>
  request<Settings>("/settings/modules", { method: "PUT", body: modules });

// Settings → Regional (R10): a field left out keeps its value.
export type RegionalUpdate = Partial<Pick<Settings, "currency" | "default_timezone">>;

export const saveRegional = (regional: RegionalUpdate) =>
  request<Settings>("/settings/regional", { method: "PUT", body: regional });

// Settings → AI spending (2026-10-19): null for no limit.
export const saveSpending = (limit: number | null) =>
  request<Settings>("/settings/spending", { method: "PUT", body: { draft_cost_limit_usd: limit } });
