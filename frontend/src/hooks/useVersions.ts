import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import {
  getAlignmentMatrix,
  getQualityCard,
  getVersion,
  listVersions,
  publishVersion,
  reopenVersion,
} from "../api/versions";
import { refreshReview } from "./useReview";

export function useQualityCard(versionId: string | null) {
  return useQuery({
    queryKey: ["versions", versionId ?? "", "quality-card"],
    queryFn: () => getQualityCard(versionId ?? ""),
    enabled: Boolean(versionId),
  });
}

export function useVersion(versionId: string | null) {
  return useQuery({
    queryKey: ["versions", versionId ?? "", "detail"],
    queryFn: () => getVersion(versionId ?? ""),
    enabled: Boolean(versionId),
  });
}

export function useVersions(engagementId: string) {
  return useQuery({
    queryKey: ["engagements", engagementId, "versions"],
    queryFn: () => listVersions(engagementId),
  });
}

/** After publishing or reopening, everything that shows which version is current changes. */
function refreshVersions(client: QueryClient, engagementId: string) {
  void client.invalidateQueries({ queryKey: ["engagements", engagementId] });
  void client.invalidateQueries({ queryKey: ["engagements"], exact: true });
  void client.invalidateQueries({ queryKey: ["versions"] });
}

export function usePublish(versionId: string, engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => publishVersion(versionId),
    onSuccess: () => refreshVersions(client, engagementId),
    // A refusal lists the blockers; the card may have changed since it was last shown.
    onError: () => refreshReview(client, versionId, engagementId),
  });
}

export function useReopen(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (versionId: string) => reopenVersion(versionId),
    onSuccess: () => refreshVersions(client, engagementId),
  });
}

export function useAlignmentMatrix(versionId: string | null) {
  return useQuery({
    queryKey: ["versions", versionId ?? "", "alignment-matrix"],
    queryFn: () => getAlignmentMatrix(versionId ?? ""),
    enabled: Boolean(versionId),
  });
}
