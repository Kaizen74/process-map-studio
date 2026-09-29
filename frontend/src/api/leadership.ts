import { request } from "./request";
import type { DecisionNeeded, LeadershipView } from "../lib/leadership";

const enc = encodeURIComponent;

// API_CONTRACT.md → Leadership view (phase P11).
export const getLeadership = (versionId: string) =>
  request<LeadershipView>(`/versions/${enc(versionId)}/leadership`);

export const saveDecisions = (versionId: string, lines: DecisionNeeded[]) =>
  request<DecisionNeeded[]>(`/versions/${enc(versionId)}/leadership/decisions`, { method: "PUT", body: lines });
