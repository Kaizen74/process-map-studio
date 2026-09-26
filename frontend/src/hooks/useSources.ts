import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { deleteSource, getSource, listSegments, listSources, updateSource, uploadSource } from "../api/sources";
import type { Source, SourcePatch, SourceUpload } from "../api/types";

const sourcesKey = (engagementId: string) => ["engagements", engagementId, "sources"] as const;
const sourceKey = (sourceId: string) => ["sources", sourceId] as const;
const segmentsKey = (sourceId: string) => ["sources", sourceId, "segments"] as const;

/** Sources change what the draft still needs and the Home card counts: refresh those too. */
function refreshAround(client: QueryClient, engagementId: string) {
  void client.invalidateQueries({ queryKey: sourcesKey(engagementId) });
  void client.invalidateQueries({ queryKey: ["engagements", engagementId, "readiness"] });
  void client.invalidateQueries({ queryKey: ["engagements"], exact: true });
}

export function useSources(engagementId: string) {
  return useQuery({ queryKey: sourcesKey(engagementId), queryFn: () => listSources(engagementId) });
}

export function useSource(sourceId: string | null) {
  return useQuery({
    queryKey: sourceKey(sourceId ?? ""),
    queryFn: () => getSource(sourceId ?? ""),
    enabled: Boolean(sourceId),
  });
}

export function useSegments(sourceId: string | null) {
  return useInfiniteQuery({
    queryKey: segmentsKey(sourceId ?? ""),
    queryFn: ({ pageParam }) => listSegments(sourceId ?? "", pageParam),
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
