import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { getJob } from "../api/draft";
import { addIntent, decideVerdict, extractIntent, getReality, listIntent, updateIntent } from "../api/reality";
import type { IntentFields } from "../lib/reality";

const POLL_MS = 1000;
const realityKey = (versionId: string) => ["versions", versionId, "reality"] as const;
const intentKey = (engagementId: string) => ["engagements", engagementId, "intent"] as const;

/** The version's Reality snapshot (one per version; shared by the Reality screen and the panel). */
export function useReality(versionId: string | null, enabled = true) {
  return useQuery({
    queryKey: realityKey(versionId ?? ""),
    queryFn: () => getReality(versionId ?? ""),
    enabled: Boolean(versionId) && enabled,
  });
}

export function useIntent(engagementId: string, enabled = true) {
  return useQuery({
    queryKey: intentKey(engagementId),
    queryFn: () => listIntent(engagementId),
    enabled: Boolean(engagementId) && enabled,
  });
}

/** Intent and verdicts change the engagement's snapshots and Leadership's figures: asked again. */
function refresh(client: QueryClient, engagementId: string) {
  void client.invalidateQueries({ queryKey: intentKey(engagementId) });
  void client.invalidateQueries({
    predicate: (q) => q.queryKey[0] === "versions" && (q.queryKey[2] === "reality" || q.queryKey[2] === "leadership"),
  });
}

export function useAddIntent(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (fields: IntentFields) => addIntent(engagementId, fields),
    onSuccess: () => refresh(client, engagementId),
  });
}

export function useUpdateIntent(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: { id: string; status?: string; note?: string; edits?: IntentFields }) =>
      updateIntent(id, body),
    onSuccess: () => refresh(client, engagementId),
  });
}

/**
 * Finds intent statements in the engagement's policy or charter documents (the S1 intent job):
 * starts the job, follows it, and lists the proposals when it ends.
 */
export function useExtractIntent(engagementId: string) {
  const client = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const start = useMutation({
    mutationFn: () => extractIntent(engagementId),
    onSuccess: (s) => setJobId(s.job_id),
  });
  const job = useQuery({
    queryKey: ["jobs", jobId ?? ""],
    queryFn: () => getJob(jobId ?? ""),
    enabled: Boolean(jobId),
    refetchInterval: (q) =>
      q.state.data && (q.state.data.status === "done" || q.state.data.status === "failed") ? false : POLL_MS,
  });
  const status = job.data?.status;
  const finished = status === "done" || status === "failed";
  useEffect(() => {
    if (finished) {
      refresh(client, engagementId);
      void client.invalidateQueries({ queryKey: ["settings", "usage"] });
    }
  }, [client, engagementId, finished]);
  return {
    start: () => {
      setJobId(null);
      start.mutate();
    },
    running: start.isPending || (Boolean(jobId) && !finished),
    outcome: finished && job.data ? { failed: status === "failed", message: status === "failed" ? job.data.error : job.data.message } : null,
    error: start.error,
  };
}

export function useDecideVerdict(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ itemId, verdict, note }: { itemId: string; verdict: string | null; note: string }) =>
      decideVerdict(itemId, { verdict, note }),
    onSuccess: () => refresh(client, engagementId),
  });
}
