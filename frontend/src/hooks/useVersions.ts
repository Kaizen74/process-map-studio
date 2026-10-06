import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import {
  decideTheme,
  getAlignmentMatrix,
  getQualityCard,
  getRegisters,
  getVersion,
  listCauses,
  listThemes,
  listVersions,
  publishVersion,
  reopenVersion,
  validateCause,
} from "../api/versions";
import type { ThemeStatus, ValidationResult } from "../lib/registers";
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

export function useRegisters(versionId: string | null) {
  return useQuery({
    queryKey: ["versions", versionId ?? "", "registers"],
    queryFn: () => getRegisters(versionId ?? ""),
    enabled: Boolean(versionId),
  });
}

export function useCauseLibrary(engagementId: string) {
  return useQuery({
    queryKey: ["engagements", engagementId, "cause-library"],
    queryFn: () => listCauses(engagementId),
  });
}

/** Confirm, refute or reopen a cause-library entry; the audit log changes too. */
export function useValidateCause(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ causeId, result }: { causeId: string; result: ValidationResult }) => validateCause(causeId, result),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ["engagements", engagementId, "cause-library"] });
      void client.invalidateQueries({ queryKey: ["versions"], predicate: (q) => q.queryKey[2] === "audit" });
    },
  });
}

/** The engagement's emerging themes (C7b). */
export function useThemes(engagementId: string) {
  return useQuery({ queryKey: ["engagements", engagementId, "themes"], queryFn: () => listThemes(engagementId) });
}

/** Accept (optionally renamed), dismiss or reopen a theme; the audit log changes too. */
export function useDecideTheme(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ themeId, status, theme }: { themeId: string; status: ThemeStatus; theme?: string }) =>
      decideTheme(themeId, theme === undefined ? { status } : { status, theme }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["engagements", engagementId, "themes"] }),
  });
}

