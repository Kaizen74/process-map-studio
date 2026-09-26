import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { addRedactionTerm, deleteRedactionTerm, listRedactionTerms } from "../api/redaction";

const termsKey = (engagementId: string) => ["engagements", engagementId, "redaction-terms"] as const;

/** A changed list changes what every passage and file name shows. */
function refreshShownText(client: QueryClient, engagementId: string) {
  void client.invalidateQueries({ queryKey: termsKey(engagementId) });
  void client.invalidateQueries({ queryKey: ["sources"] });
  void client.invalidateQueries({ queryKey: ["engagements", engagementId, "sources"] });
  void client.invalidateQueries({ queryKey: ["engagements", engagementId, "readiness"] });
}

export function useRedactionTerms(engagementId: string) {
  return useQuery({ queryKey: termsKey(engagementId), queryFn: () => listRedactionTerms(engagementId) });
}

export function useAddRedactionTerm(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ term, replacement }: { term: string; replacement: string }) =>
      addRedactionTerm(engagementId, term, replacement),
    onSuccess: () => refreshShownText(client, engagementId),
  });
}

export function useDeleteRedactionTerm(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: deleteRedactionTerm,
    onSettled: () => refreshShownText(client, engagementId),
  });
}
