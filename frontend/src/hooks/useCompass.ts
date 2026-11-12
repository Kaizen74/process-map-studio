import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addTesting, deleteTesting, listTesting, previewHandoff, updateTesting } from "../api/compass";
import type { TestingPatch } from "../api/types";

const testingKey = (engagementId: string) => ["engagements", engagementId, "testing"] as const;

/** The preview of a hand-off file: a mutation, since the file is sent and nothing is kept. */
export function usePreviewHandoff() {
  return useMutation({ mutationFn: (handoff: unknown) => previewHandoff(handoff) });
}

export function useTesting(engagementId: string) {
  return useQuery({ queryKey: testingKey(engagementId), queryFn: () => listTesting(engagementId) });
}

export function useAddTesting(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (item: { ref: string; text: string; refuted_by: string }) => addTesting(engagementId, item),
    onSuccess: () => void client.invalidateQueries({ queryKey: testingKey(engagementId) }),
  });
}

export function useUpdateTesting(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: TestingPatch }) => updateTesting(id, patch),
    onSuccess: () => void client.invalidateQueries({ queryKey: testingKey(engagementId) }),
  });
}

export function useDeleteTesting(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTesting(id),
    onSuccess: () => void client.invalidateQueries({ queryKey: testingKey(engagementId) }),
  });
}
