import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getAiUsage,
  getSettings,
  listModels,
  saveApiKey,
  saveModel,
  saveProfile,
  saveModules,
  saveRegional,
  saveResearch,
  type ModuleSwitches,
  type RegionalUpdate,
  testConnection,
  testWebSearch,
} from "../api/settings";
import type { ModelUpdate, Settings } from "../api/types";

const SETTINGS = ["settings"] as const;
const MODELS = ["settings", "models"] as const;
const USAGE = ["settings", "usage"] as const;

export function useSettings() {
  return useQuery({ queryKey: SETTINGS, queryFn: getSettings });
}

export function useModelChoices(enabled: boolean) {
  return useQuery({ queryKey: MODELS, queryFn: listModels, enabled });
}

function useSettingsMutation<TInput>(save: (input: TInput) => Promise<Settings>, refreshModels = false) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: save,
    onSuccess: (settings) => {
      client.setQueryData(SETTINGS, settings);
      if (refreshModels) void client.invalidateQueries({ queryKey: MODELS });
    },
  });
}

export const useSaveProfile = () => useSettingsMutation(saveProfile);
export const useSaveApiKey = () => useSettingsMutation(saveApiKey, true);
export const useSaveModel = () => useSettingsMutation((update: ModelUpdate) => saveModel(update));

export const useSaveResearch = () => useSettingsMutation((enabled: boolean) => saveResearch(enabled));

export const useSaveModules = () => useSettingsMutation((modules: ModuleSwitches) => saveModules(modules));

export const useSaveRegional = () => useSettingsMutation((regional: RegionalUpdate) => saveRegional(regional));

/** One small search (billed as one search); the AI usage list gains the call. */
export function useTestWebSearch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: testWebSearch,
    onSettled: () => void client.invalidateQueries({ queryKey: USAGE }),
  });
}

export function useTestConnection() {
  return useMutation({ mutationFn: testConnection });
}

/** The most recent AI calls and all-time totals (Settings, AI usage). */
export function useAiUsage() {
  return useQuery({ queryKey: USAGE, queryFn: () => getAiUsage() });
}
