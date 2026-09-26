import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createEngagement,
  deleteEngagement,
  getEngagement,
  getReadiness,
  listEngagements,
  updateEngagement,
} from "../api/engagements";
import type { Engagement, ScopeFields } from "../api/types";

const ENGAGEMENTS = ["engagements"] as const;
const engagementKey = (id: string) => ["engagements", id] as const;
const readinessKey = (id: string) => ["engagements", id, "readiness"] as const;

export function useEngagements() {
  return useQuery({ queryKey: ENGAGEMENTS, queryFn: listEngagements });
}

export function useEngagement(id: string | undefined) {
  return useQuery({
    queryKey: engagementKey(id ?? ""),
    queryFn: () => getEngagement(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useReadiness(id: string | undefined) {
  return useQuery({
    queryKey: readinessKey(id ?? ""),
    queryFn: () => getReadiness(id ?? ""),
    enabled: Boolean(id),
  });
}

export function useCreateEngagement() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: createEngagement,
    onSuccess: (engagement: Engagement) => {
      client.setQueryData(engagementKey(engagement.id), engagement);
      void client.invalidateQueries({ queryKey: ENGAGEMENTS });
    },
  });
}

export function useUpdateEngagement(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (fields: ScopeFields) => updateEngagement(id, fields),
    onSuccess: (engagement: Engagement) => {
      client.setQueryData(engagementKey(id), engagement);
      void client.invalidateQueries({ queryKey: ENGAGEMENTS, exact: true });
      void client.invalidateQueries({ queryKey: readinessKey(id) });
    },
  });
}

export function useDeleteEngagement() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: deleteEngagement,
    // Refresh even on failure: a partial delete (files left behind) still removes the engagement.
    onSettled: (_data, _error, id) => {
      client.removeQueries({ queryKey: engagementKey(id), exact: true });
      client.removeQueries({ queryKey: readinessKey(id), exact: true });
      void client.invalidateQueries({ queryKey: ENGAGEMENTS, exact: true });
    },
  });
}
