import { request } from "./request";
import type { RedactionTerm } from "./types";

const enc = encodeURIComponent;

// Owner-only (PRD §3.8 G10): the list of names to hide.
export const listRedactionTerms = (engagementId: string) =>
  request<RedactionTerm[]>(`/engagements/${enc(engagementId)}/redaction-terms`);

export const addRedactionTerm = (engagementId: string, term: string, replacement: string) =>
  request<RedactionTerm>(`/engagements/${enc(engagementId)}/redaction-terms`, {
    method: "POST",
    body: { term, replacement },
  });

export const deleteRedactionTerm = (termId: string) =>
  request<null>(`/redaction-terms/${enc(termId)}`, { method: "DELETE" });
