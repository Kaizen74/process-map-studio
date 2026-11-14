import { useEffect, useState } from "react";
import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  decideDifference,
  getComparison,
  listCandidates,
  listComparisons,
  refreshComparison,
  setPair,
  startComparison,
  suggestPairs,
} from "../api/comparisons";
import { getJob } from "../api/draft";
import type { Comparison, DifferenceDecision, PairDecisionKind } from "../lib/comparisons";

const POLL_MS = 1000;
const comparisonKey = (id: string) => ["comparisons", id] as const;

export function useCandidates(engagementId: string) {
  return useQuery({
    queryKey: ["engagements", engagementId, "comparison-candidates"],
    queryFn: () => listCandidates(engagementId),
    enabled: Boolean(engagementId),
  });
}

export function useComparisons(engagementId: string) {
  return useQuery({
    queryKey: ["engagements", engagementId, "comparisons"],
    queryFn: () => listComparisons(engagementId),
    enabled: Boolean(engagementId),
  });
}

export function useComparison(id: string | null) {
  return useQuery({
    queryKey: comparisonKey(id ?? ""),
    queryFn: () => getComparison(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useStartComparison(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: startComparison,
    onSuccess: (view: Comparison) => {
      client.setQueryData(comparisonKey(view.id), view);
      void client.invalidateQueries({ queryKey: ["engagements", engagementId, "comparisons"] });
    },
  });
}

/**
 * The lists of comparisons, on both countries' screens, carry each comparison's counts: asked again
 * after every change so they keep up with the comparison shown (Eric, 2026-11-14).
 */
function refreshLists(client: QueryClient) {
  void client.invalidateQueries({
    predicate: (q) => q.queryKey[0] === "engagements" && q.queryKey[2] === "comparisons",
  });
}

/** Every change answers with the whole comparison, which replaces the one shown. */
function useReplacing<T>(id: string, fn: (arg: T) => Promise<Comparison>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (view: Comparison) => {
      client.setQueryData(comparisonKey(id), view);
      refreshLists(client);
    },
  });
}

export function useSetPair(id: string) {
  return useReplacing(
    id,
    (body: { reference_key: string | null; other_key: string | null; decision: PairDecisionKind }) =>
      setPair(id, body),
  );
}

export function useRefreshComparison(id: string) {
  return useReplacing(id, () => refreshComparison(id));
}

export function useDecideDifference(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ key, body }: { key: string; body: DifferenceDecision }) => decideDifference(id, key, body),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: comparisonKey(id) });
      refreshLists(client);
    },
  });
}

/** Claude's suggestion job (CC_match): started, followed until it ends, then the view asked again. */
export function useSuggestPairs(id: string) {
  const client = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const start = useMutation({ mutationFn: () => suggestPairs(id), onSuccess: (s) => setJobId(s.job_id) });
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
    if (!finished) return;
    void client.invalidateQueries({ queryKey: comparisonKey(id) });
    refreshLists(client);
  }, [client, id, finished]);
  return {
    start: () => {
      setJobId(null);
      start.mutate();
    },
    running: start.isPending || (Boolean(jobId) && !finished),
    outcome:
      finished && job.data
        ? { failed: status === "failed", message: status === "failed" ? job.data.error : job.data.message }
        : null,
    error: start.error,
  };
}
