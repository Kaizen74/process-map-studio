import { useQuery } from "@tanstack/react-query";
import { getGraph } from "../api/draft";
import { getElement, getLayout, listSegmentsAround } from "../api/review";

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
