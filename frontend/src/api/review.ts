import { request } from "./request";
import type { AuditEntry, ElementDetail, Layout, MergeProposal, Question, SegmentPage } from "./types";
import type { NewStepBody } from "../lib/addStep";
import type { StepPatch } from "../lib/stepForm";

const enc = encodeURIComponent;

// API_CONTRACT.md → Draft (layout) and Review (phase P5). The graph itself: api/draft.ts.
export const getLayout = (versionId: string) => request<Layout>(`/versions/${enc(versionId)}/layout`);

export const getElement = (elementId: string) => request<ElementDetail>(`/elements/${enc(elementId)}`);

/** The page of a source that holds one passage (the source viewer opened from evidence). */
export const listSegmentsAround = (sourceId: string, segmentId: string, pageSize = 200) =>
  request<SegmentPage>(`/sources/${enc(sourceId)}/segments?around=${enc(segmentId)}&page_size=${pageSize}`);

// Review actions (phase P6).
export type ReviewAction = "confirm" | "reject" | "restore";

export const reviewElement = (elementId: string, action: ReviewAction) =>
  request<ElementDetail>(`/elements/${enc(elementId)}/${action}`, { method: "POST" });

/** Edit a step: only the fields sent change (PATCH /elements/{eid}). */
export const updateElement = (elementId: string, patch: Partial<StepPatch>) =>
  request<ElementDetail>(`/elements/${enc(elementId)}`, { method: "PATCH", body: patch });

/** Add a missing step: Eric's own, observed with passages or recommended with a reference. */
export const addStep = (versionId: string, body: NewStepBody) =>
  request<ElementDetail>(`/versions/${enc(versionId)}/elements`, { method: "POST", body });

// The workbench tabs (phase P6).
export const listQuestions = (versionId: string) => request<Question[]>(`/versions/${enc(versionId)}/questions`);

export const setQuestionStatus = (questionId: string, status: "open" | "answered") =>
  request<Question>(`/questions/${enc(questionId)}`, { method: "PATCH", body: { status } });

export const listMergeProposals = (versionId: string) =>
  request<MergeProposal[]>(`/versions/${enc(versionId)}/merge-proposals`);

export type MergeChoice = "accepted" | "rejected" | "split";

export const decideMerge = (proposalId: string, decision: MergeChoice) =>
  request<MergeProposal>(`/merge-proposals/${enc(proposalId)}/decision`, { method: "POST", body: { decision } });

export const getAudit = (versionId: string) => request<AuditEntry[]>(`/versions/${enc(versionId)}/audit`);
