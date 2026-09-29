import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getLeadership, saveDecisions } from "../api/leadership";
import type { DecisionNeeded, LeadershipView } from "../lib/leadership";

const key = (versionId: string) => ["versions", versionId, "leadership"] as const;

export function useLeadership(versionId: string | null) {
  return useQuery({
    queryKey: key(versionId ?? ""),
    queryFn: () => getLeadership(versionId ?? ""),
    enabled: Boolean(versionId),
  });
}

/** Saves every "Decision needed" line of the version; the view shows the saved text at once. */
export function useSaveDecisions(versionId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (lines: DecisionNeeded[]) => saveDecisions(versionId, lines),
    onSuccess: (saved) => {
      client.setQueryData<LeadershipView>(key(versionId), (old) =>
        old ? { ...old, recommendation: { ...old.recommendation, decisions_needed: saved } } : old,
      );
      void client.invalidateQueries({ queryKey: ["versions", versionId, "audit"] });
    },
  });
}
