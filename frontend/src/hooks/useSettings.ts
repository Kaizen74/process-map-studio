import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getSettings,
  listModels,
  saveApiKey,
  saveModel,
  saveProfile,
  testConnection,
} from "../api/settings";
import type { ModelUpdate, Settings } from "../api/types";

const SETTINGS = ["settings"] as const;
const MODELS = ["settings", "models"] as const;

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

export function useTestConnection() {
  return useMutation({ mutationFn: testConnection });
}
