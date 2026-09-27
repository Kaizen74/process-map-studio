import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { getDraft, getRejectedClaims, startDraft, startRefresh } from "../api/draft";
import type { DraftState } from "../api/types";

const draftKey = (engagementId: string) => ["engagements", engagementId, "draft"] as const;
const rejectedKey = (versionId: string) => ["versions", versionId, "rejected-claims"] as const;

/** How often to look again while a draft is being made in the background. */
export const DRAFT_POLL_MS = 1000;

const drafting = (state: DraftState | undefined) =>
  state?.job?.status === "queued" || state?.job?.status === "running";

/** The latest draft job and the current draft (API_CONTRACT.md → Draft). */
export function useDraft(engagementId: string) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: draftKey(engagementId),
    queryFn: () => getDraft(engagementId),
    refetchInterval: (q) => (drafting(q.state.data) ? DRAFT_POLL_MS : false),
  });
  // When a draft finishes, the guided path, the Home card and the AI usage change too.
  const running = drafting(query.data);
  const wasRunning = useRef(running);
  useEffect(() => {
    if (wasRunning.current && !running) {
      void client.invalidateQueries({ queryKey: ["engagements", engagementId, "readiness"] });
      void client.invalidateQueries({ queryKey: ["engagements"], exact: true });
      void client.invalidateQueries({ queryKey: ["settings", "usage"] });
    }
    wasRunning.current = running;
  }, [client, engagementId, running]);
  return query;
}

export function useStartDraft(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => startDraft(engagementId),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: draftKey(engagementId) });
      void client.invalidateQueries({ queryKey: ["engagements", engagementId, "readiness"] });
    },
  });
}

/** Refresh the current draft from its sources; progress shows on the Draft screen. */
export function useStartRefresh(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) => startRefresh(versionId),
    onSettled: () => void client.invalidateQueries({ queryKey: draftKey(engagementId) }),
  });
}

export function useRejectedClaims(versionId: string | null) {
  return useQuery({
    queryKey: rejectedKey(versionId ?? ""),
    queryFn: () => getRejectedClaims(versionId ?? ""),
    enabled: Boolean(versionId),
  });
}
