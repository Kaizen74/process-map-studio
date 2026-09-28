import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import {
  correctSegment,
  deleteSource,
  getSource,
  getSpeakers,
  listSegments,
  listSources,
  mapSpeakers,
  updateSource,
  uploadSource,
} from "../api/sources";
import type { Source, SourcePatch, SourceUpload, SpeakerMapping } from "../api/types";

const sourcesKey = (engagementId: string) => ["engagements", engagementId, "sources"] as const;
const sourceKey = (sourceId: string) => ["sources", sourceId] as const;
const segmentsKey = (sourceId: string) => ["sources", sourceId, "segments"] as const;
const rawSegmentsKey = (sourceId: string) => ["sources", sourceId, "segments", "raw"] as const;
const speakersKey = (sourceId: string) => ["sources", sourceId, "speakers"] as const;

/** Sources change what the draft still needs and the Home card counts: refresh those too. */
function refreshAround(client: QueryClient, engagementId: string) {
  void client.invalidateQueries({ queryKey: sourcesKey(engagementId) });
  void client.invalidateQueries({ queryKey: ["engagements", engagementId, "readiness"] });
  void client.invalidateQueries({ queryKey: ["engagements"], exact: true });
}

/** How often to look again while a file is being read in the background. */
export const READING_POLL_MS = 1000;

const reading = (sources: readonly Source[] | undefined) => sources?.some((s) => s.text_status === "pending");

export function useSources(engagementId: string) {
  const client = useQueryClient();
  const query = useQuery({
    queryKey: sourcesKey(engagementId),
    queryFn: () => listSources(engagementId),
    refetchInterval: (q) => (reading(q.state.data) ? READING_POLL_MS : false),
  });
  // When a file finishes reading, what the draft needs (readiness), the passages and the names to
  // hide (reading adds name-like speaker labels, G10) change too.
  const readingCount = query.data?.filter((s) => s.text_status === "pending").length ?? 0;
  const previous = useRef(readingCount);
  useEffect(() => {
    if (readingCount < previous.current) {
      void client.invalidateQueries({ queryKey: ["engagements", engagementId, "readiness"] });
      void client.invalidateQueries({ queryKey: ["engagements", engagementId, "redaction-terms"] });
      void client.invalidateQueries({ queryKey: ["engagements"], exact: true });
      void client.invalidateQueries({ queryKey: ["sources"] });
    }
    previous.current = readingCount;
  }, [client, engagementId, readingCount]);
  return query;
}

export function useSource(sourceId: string | null) {
  return useQuery({
    queryKey: sourceKey(sourceId ?? ""),
    queryFn: () => getSource(sourceId ?? ""),
    enabled: Boolean(sourceId),
    refetchInterval: (q) => (q.state.data?.text_status === "pending" ? READING_POLL_MS : false),
  });
}

/** A source's passages; `uncitedOnly` lists only those the current map doesn't cite (G11). */
export function useSegments(sourceId: string | null, uncitedOnly = false) {
  return useInfiniteQuery({
    queryKey: uncitedOnly ? [...segmentsKey(sourceId ?? ""), "uncited"] : segmentsKey(sourceId ?? ""),
    queryFn: ({ pageParam }) => listSegments(sourceId ?? "", pageParam, 200, false, uncitedOnly),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page < last.pages ? last.page + 1 : undefined),
    enabled: Boolean(sourceId),
  });
}

export function useUploadSource(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (upload: SourceUpload) => uploadSource(engagementId, upload),
    onSettled: () => refreshAround(client, engagementId),
  });
}

export function useUpdateSource(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: SourcePatch }) => updateSource(id, patch),
    onSuccess: (source: Source) => client.setQueryData(sourceKey(source.id), source),
    onSettled: () => refreshAround(client, engagementId),
  });
}

export function useDeleteSource(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: deleteSource,
    onSettled: (_data, _error, id) => {
      client.removeQueries({ queryKey: sourceKey(id) });
      refreshAround(client, engagementId);
    },
  });
}

/** Owner-only: the passages exactly as stored, for the correction editor. */
export function useRawSegments(sourceId: string | null, enabled: boolean) {
  return useInfiniteQuery({
    queryKey: rawSegmentsKey(sourceId ?? ""),
    queryFn: ({ pageParam }) => listSegments(sourceId ?? "", pageParam, 200, true),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page < last.pages ? last.page + 1 : undefined),
    enabled: Boolean(sourceId) && enabled,
  });
}

export function useSpeakers(sourceId: string | null, enabled = true) {
  return useQuery({
    queryKey: speakersKey(sourceId ?? ""),
    queryFn: () => getSpeakers(sourceId ?? ""),
    enabled: Boolean(sourceId) && enabled,
  });
}

export function useMapSpeakers(engagementId: string, sourceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (mapping: SpeakerMapping) => mapSpeakers(sourceId, mapping),
    onSuccess: (speakers) => client.setQueryData(speakersKey(sourceId), speakers),
    onSettled: () => {
      // Passages now show roles, and names show as the mapped role.
      void client.invalidateQueries({ queryKey: ["sources"] });
      void client.invalidateQueries({ queryKey: ["engagements", engagementId, "redaction-terms"] });
      refreshAround(client, engagementId);
    },
  });
}

export function useCorrectSegment(sourceId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, text }: { id: string; text: string }) => correctSegment(id, text),
    onSettled: () => void client.invalidateQueries({ queryKey: ["sources", sourceId] }),
  });
}
