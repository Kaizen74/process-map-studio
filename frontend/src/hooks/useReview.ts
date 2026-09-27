import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { getGraph } from "../api/draft";
import {
  addStep,
  getElement,
  getLayout,
  listSegmentsAround,
  reviewElement,
  updateElement,
  type ReviewAction,
} from "../api/review";
import type { NewStepBody } from "../lib/addStep";
import type { StepPatch } from "../lib/stepForm";
import type { ElementDetail, Graph } from "../api/types";

// Keys follow PRD §5.8 "invalidate graph, layout, quality-card and lint for the version".
export function useGraph(versionId: string | null) {
  return useQuery({
    queryKey: ["versions", versionId ?? "", "graph"],
    queryFn: () => getGraph(versionId ?? ""),
    enabled: Boolean(versionId),
  });
}

export function useLayout(versionId: string | null) {
  return useQuery({
    queryKey: ["versions", versionId ?? "", "layout"],
    queryFn: () => getLayout(versionId ?? ""),
    enabled: Boolean(versionId),
  });
}

export function useElement(elementId: string | null) {
  return useQuery({
    queryKey: ["elements", elementId ?? ""],
    queryFn: () => getElement(elementId ?? ""),
    enabled: Boolean(elementId),
  });
}

export function useSegmentsAround(sourceId: string | null, segmentId: string | null) {
  return useQuery({
    queryKey: ["sources", sourceId ?? "", "segments", "around", segmentId ?? ""],
    queryFn: () => listSegmentsAround(sourceId ?? "", segmentId ?? ""),
    enabled: Boolean(sourceId && segmentId),
  });
}

const AFTER: Readonly<Record<ReviewAction, string>> = {
  confirm: "confirmed",
  reject: "rejected",
  restore: "draft",
};

/** Everything that shows a version's review state, refreshed after a change (PRD §5.8). */
export function refreshReview(client: QueryClient, versionId: string, engagementId: string) {
  for (const part of ["graph", "layout", "lint", "audit", "questions", "merge-proposals"]) {
    void client.invalidateQueries({ queryKey: ["versions", versionId, part] });
  }
  void client.invalidateQueries({ queryKey: ["engagements", engagementId] });
  void client.invalidateQueries({ queryKey: ["engagements"], exact: true });
}

/**
 * Confirm, reject or restore a step. The map and progress change at once (optimistic update)
 * and roll back if the server refuses; then everything that shows review state is refreshed.
 */
export function useReviewStep(versionId: string, engagementId: string) {
  const client = useQueryClient();
  const graphKey = ["versions", versionId, "graph"];
  return useMutation({
    mutationFn: ({ elementId, action }: { elementId: string; action: ReviewAction }) =>
      reviewElement(elementId, action),
    onMutate: async ({ elementId, action }) => {
      await client.cancelQueries({ queryKey: graphKey });
      const before = client.getQueryData<Graph>(graphKey);
      if (before) {
        const current = before.elements.find((e) => e.id === elementId)?.review_status;
        const locked = current === "confirmed" || current === "edited" || current === "added";
        const next = action === "confirm" && locked ? current : AFTER[action];
        client.setQueryData<Graph>(graphKey, {
          ...before,
          elements: before.elements.map((e) => (e.id === elementId ? { ...e, review_status: next ?? e.review_status } : e)),
        });
      }
      return { before };
    },
    onError: (_error, _vars, context) => {
      if (context?.before) client.setQueryData(graphKey, context.before);
    },
    onSuccess: (detail: ElementDetail) => client.setQueryData(["elements", detail.id], detail),
    onSettled: () => refreshReview(client, versionId, engagementId),
  });
}

/**
 * Save edits to a step. Not optimistic: the form stays open until the server accepts, so a
 * refused field can show its message. When kind or lane changed, it waits for the new layout
 * (PRD §5.7.6) before it counts as saved.
 */
export function useEditStep(versionId: string, engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ elementId, patch }: { elementId: string; patch: Partial<StepPatch> }) =>
      updateElement(elementId, patch),
    onSuccess: async (detail: ElementDetail, { patch }) => {
      client.setQueryData(["elements", detail.id], detail);
      refreshReview(client, versionId, engagementId);
      if ("kind" in patch || "lane_role_id" in patch) {
        await client.refetchQueries({ queryKey: ["versions", versionId, "layout"] });
      }
    },
  });
}

/** Add a missing step; counts as done once the new layout (with the step placed) is in. */
export function useAddStep(versionId: string, engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: NewStepBody) => addStep(versionId, body),
    onSuccess: async (detail: ElementDetail) => {
      client.setQueryData(["elements", detail.id], detail);
      refreshReview(client, versionId, engagementId);
      await client.refetchQueries({ queryKey: ["versions", versionId, "graph"] });
      await client.refetchQueries({ queryKey: ["versions", versionId, "layout"] });
    },
  });
}
