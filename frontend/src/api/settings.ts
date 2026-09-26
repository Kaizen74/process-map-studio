import { request } from "./request";
import type { ConnectionTest, ModelChoices, ModelUpdate, Settings } from "./types";

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
