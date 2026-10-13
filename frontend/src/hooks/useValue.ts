import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getAssumptions,
  getDispositions,
  getRoleCosts,
  getValue,
  setAssumptions,
  setDisposition,
  setRoleCosts,
  setValueOverride,
} from "../api/value";
import type { Disposition, DispositionChoice, ValueOverride } from "../lib/value";

// Step disposition and the value calculator (R10): read only while the value module is on.

/** Every step's suggested disposition with its reason, and Eric's choice. */
export function useDispositions(versionId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["versions", versionId ?? "", "dispositions"],
    queryFn: () => getDispositions(versionId ?? ""),
    enabled: enabled && Boolean(versionId),
  });
}

/** Hours and cost per step, phase and disposition, each labelled (§3.14). */
export function useValue(versionId: string | null, view: "done" | "documented", enabled: boolean) {
  return useQuery({
    queryKey: ["versions", versionId ?? "", "value", view],
    queryFn: () => getValue(versionId ?? "", view),
    enabled: enabled && Boolean(versionId),
  });
}

function refreshValue(client: ReturnType<typeof useQueryClient>, versionId: string) {
  // A choice changes the step's scenario, and the backend refreshes the map checks (L10).
  for (const part of ["dispositions", "value", "lint", "quality-card"]) {
    void client.invalidateQueries({ queryKey: ["versions", versionId, part] });
  }
}

/** Eric's disposition for one step (drafts only), with a note and the risk flag. */
export function useSetDisposition(versionId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ elementId, choice }: { elementId: string; choice: DispositionChoice }) =>
      setDisposition(elementId, choice),
    onSuccess: () => refreshValue(client, versionId),
  });
}

/** Eric's own time per case and volume per month for one step, with where they come from. */
export function useSetValueOverride(versionId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ elementId, override }: { elementId: string; override: ValueOverride }) =>
      setValueOverride(elementId, override),
    onSuccess: () => refreshValue(client, versionId),
  });
}

export function useRoleCosts(engagementId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["engagements", engagementId, "role-costs"],
    queryFn: () => getRoleCosts(engagementId),
    enabled: enabled && Boolean(engagementId),
  });
}

export function useAssumptions(engagementId: string, enabled: boolean) {
  return useQuery({
    queryKey: ["engagements", engagementId, "value-assumptions"],
    queryFn: () => getAssumptions(engagementId),
    enabled: enabled && Boolean(engagementId),
  });
}

/** Role costs and assumptions change every version's figures. */
function refreshEngagementValue(client: ReturnType<typeof useQueryClient>, engagementId: string) {
  void client.invalidateQueries({ queryKey: ["engagements", engagementId, "role-costs"] });
  void client.invalidateQueries({ queryKey: ["engagements", engagementId, "value-assumptions"] });
  void client.invalidateQueries({ predicate: (q) => q.queryKey[0] === "versions" && q.queryKey[2] === "value" });
}

export function useSetRoleCosts(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (rows: { role_id: string; hourly_cost: number | null; note: string }[]) =>
      setRoleCosts(engagementId, rows),
    onSuccess: () => refreshEngagementValue(client, engagementId),
  });
}

export function useSetAssumptions(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (rows: { disposition: Disposition; reduction_pct: number; note: string }[]) =>
      setAssumptions(engagementId, rows),
    onSuccess: () => refreshEngagementValue(client, engagementId),
  });
}
