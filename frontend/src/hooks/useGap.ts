import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import {
  decideFinding,
  finaliseReport,
  getReport,
  listAnalyses,
  runResearch,
  startExternal,
  startInternal,
  updateBrief,
} from "../api/gap";
import { getJob } from "../api/draft";
import { isRunning, type Brief, type FindingDecision, type GapReport } from "../lib/gap";

/** How often to look again while an analysis runs in the background. */
export const GAP_POLL_MS = 1000;

const listKey = (versionId: string) => ["versions", versionId, "gap-analyses"] as const;
const reportKey = (analysisId: string) => ["gap-analyses", analysisId] as const;

export function useGapAnalyses(versionId: string | null) {
  return useQuery({
    queryKey: listKey(versionId ?? ""),
    queryFn: () => listAnalyses(versionId ?? ""),
    enabled: Boolean(versionId),
    refetchInterval: (q) => ((q.state.data ?? []).some((a) => isRunning(a)) ? GAP_POLL_MS : false),
  });
}

/** One report; checked again every second while its analysis runs. */
export function useGapReport(analysisId: string | null, engagementId: string) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: reportKey(analysisId ?? ""),
    queryFn: () => getReport(analysisId ?? ""),
    enabled: Boolean(analysisId),
    refetchInterval: (q) => (isRunning(q.state.data?.analysis) ? GAP_POLL_MS : false),
  });
  // When a run ends, the history, the AI usage and the guided path change too.
  const running = isRunning(query.data?.analysis);
  const wasRunning = useRef(running);
  useEffect(() => {
    if (wasRunning.current && !running) refreshAround(client, query.data, engagementId);
    wasRunning.current = running;
  }, [client, engagementId, query.data, running]);
  return query;
}

function refreshAround(client: QueryClient, report: GapReport | undefined, engagementId: string) {
  if (report) void client.invalidateQueries({ queryKey: listKey(report.analysis.version_id) });
  void client.invalidateQueries({ queryKey: ["settings", "usage"] });
  void client.invalidateQueries({ queryKey: ["engagements", engagementId, "readiness"] });
}

export function useStartInternal(versionId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => startInternal(versionId),
    onSettled: () => void client.invalidateQueries({ queryKey: listKey(versionId) }),
  });
}

export function useStartExternal(versionId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => startExternal(versionId),
    onSettled: () => void client.invalidateQueries({ queryKey: listKey(versionId) }),
  });
}

export function useUpdateBrief(analysisId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ brief, confirmed }: { brief: Brief; confirmed: boolean }) =>
      updateBrief(analysisId, brief, confirmed),
    onSuccess: (view) =>
      client.setQueryData<GapReport>(reportKey(analysisId), (old) =>
        old ? { ...old, analysis: view.analysis, brief: view.brief } : old,
      ),
  });
}

export function useRunResearch(analysisId: string, versionId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => runResearch(analysisId),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: reportKey(analysisId) });
      void client.invalidateQueries({ queryKey: listKey(versionId) });
    },
  });
}

/** A decision may add a question, a cause-library entry or a step: those views change too. */
export function useDecideFinding(analysisId: string, engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ findingId, decision }: { findingId: string; decision: FindingDecision }) =>
      decideFinding(findingId, decision),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: reportKey(analysisId) });
      void client.invalidateQueries({ queryKey: ["versions"] });
      void client.invalidateQueries({ queryKey: ["elements"] });
      void client.invalidateQueries({ queryKey: ["engagements", engagementId] });
    },
  });
}

export function useFinaliseReport(analysisId: string, engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => finaliseReport(analysisId),
    onSuccess: (report) => {
      client.setQueryData(reportKey(analysisId), report);
      refreshAround(client, report, engagementId);
    },
  });
}

/** The run's job (its stages and AI usage), checked every second while the analysis runs. */
export function useGapJob(jobId: string | null, running: boolean) {
  return useQuery({
    queryKey: ["jobs", jobId ?? ""],
    queryFn: () => getJob(jobId ?? ""),
    enabled: Boolean(jobId),
    refetchInterval: running ? GAP_POLL_MS : false,
  });
}
