import type {
  Candidate,
  Comparison,
  ComparisonSummary,
  Difference,
  DifferenceDecision,
  PairDecisionKind,
} from "../lib/comparisons";
import { request } from "./request";

const enc = encodeURIComponent;

export const listCandidates = (engagementId: string) =>
  request<Candidate[]>(`/engagements/${enc(engagementId)}/comparison-candidates`);

export const listComparisons = (engagementId: string) =>
  request<ComparisonSummary[]>(`/engagements/${enc(engagementId)}/comparisons`);

export const startComparison = (body: { reference_engagement_id: string; other_engagement_id: string }) =>
  request<Comparison>("/comparisons", { method: "POST", body });

export const getComparison = (id: string) => request<Comparison>(`/comparisons/${enc(id)}`);

export const setPair = (
  id: string,
  body: { reference_key: string | null; other_key: string | null; decision: PairDecisionKind },
) => request<Comparison>(`/comparisons/${enc(id)}/pairs`, { method: "PUT", body });

export const suggestPairs = (id: string) =>
  request<{ job_id: string; comparison_id: string }>(`/comparisons/${enc(id)}/suggest`, { method: "POST" });

export const refreshComparison = (id: string) =>
  request<Comparison>(`/comparisons/${enc(id)}/refresh`, { method: "POST" });

export const decideDifference = (id: string, key: string, body: DifferenceDecision) =>
  request<Difference>(`/comparisons/${enc(id)}/differences/${enc(key)}`, { method: "PUT", body });

/** The printable comparison pages (A3 or 16:9 slides). */
export const comparisonExportUrl = (id: string, layout: "a3" | "slide") =>
  `/api/comparisons/${enc(id)}/export?layout=${layout}`;
