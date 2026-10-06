import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getJob } from "../api/draft";
import { addProfile, editGuide, editProfile, getGuide, listGuides, listProfiles, makeGuide } from "../api/interview";
import type { GuideEdit, ProfileInput } from "../lib/interview";

const profilesKey = (engagementId: string) => ["engagements", engagementId, "profiles"] as const;

/** The engagement's interviewee profiles (C5a), oldest first. */
export function useProfiles(engagementId: string) {
  return useQuery({ queryKey: profilesKey(engagementId), queryFn: () => listProfiles(engagementId) });
}

export function useAddProfile(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: ProfileInput) => addProfile(engagementId, body),
    onSuccess: () => void client.invalidateQueries({ queryKey: profilesKey(engagementId) }),
  });
}

export function useEditProfile(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<ProfileInput> }) => editProfile(id, patch),
    onSuccess: () => void client.invalidateQueries({ queryKey: profilesKey(engagementId) }),
  });
}

const guidesKey = (engagementId: string) => ["engagements", engagementId, "interview-guides"] as const;

/** Each interviewee's latest tailored guide (G2). */
export function useGuides(engagementId: string) {
  return useQuery({ queryKey: guidesKey(engagementId), queryFn: () => listGuides(engagementId) });
}

/** How often to look again while a guide is being made (C5b: a background job). */
export const GUIDE_POLL_MS = 1000;

/** What became of the last guide asked for: its interviewee, and the job's message or error. */
export interface GuideOutcome {
  profileId: string;
  message: string;
  failed: boolean;
}

/**
 * Makes a new version of one interviewee's guide: starts the job, follows it, and refreshes the
 * guides list when it ends. `making` is the interviewee whose guide is on its way.
 */
export function useMakeGuide(engagementId: string) {
  const client = useQueryClient();
  const [started, setStarted] = useState<{ jobId: string; profileId: string } | null>(null);
  const start = useMutation({
    mutationFn: (profileId: string) => makeGuide(engagementId, profileId),
    onSuccess: (s) => setStarted({ jobId: s.job_id, profileId: s.profile_id }),
  });
  const job = useQuery({
    queryKey: ["jobs", started?.jobId ?? ""],
    queryFn: () => getJob(started?.jobId ?? ""),
    enabled: Boolean(started),
    refetchInterval: (q) =>
      q.state.data && (q.state.data.status === "done" || q.state.data.status === "failed") ? false : GUIDE_POLL_MS,
  });
  const status = job.data?.status;
  const finished = status === "done" || status === "failed";
  useEffect(() => {
    if (finished) {
      void client.invalidateQueries({ queryKey: guidesKey(engagementId) });
      void client.invalidateQueries({ queryKey: ["engagements", engagementId, "interview-guide"] });
      void client.invalidateQueries({ queryKey: ["settings", "usage"] });
    }
  }, [client, engagementId, finished]);
  const making = start.isPending ? (start.variables ?? null) : started && !finished ? started.profileId : null;
  const outcome: GuideOutcome | null =
    started && finished && job.data
      ? { profileId: started.profileId, message: status === "failed" ? job.data.error : job.data.message, failed: status === "failed" }
      : start.isError && start.variables
        ? { profileId: start.variables, message: "", failed: true }
        : null;
  return {
    make: (profileId: string) => {
      setStarted(null);
      start.mutate(profileId);
    },
    making,
    outcome,
    startError: start.isError ? start.error : null,
    stage: !finished ? (job.data?.stage ?? "") : "",
  };
}

const guideKey = (engagementId: string, profileId: string) =>
  ["engagements", engagementId, "interview-guide", profileId] as const;

/** One interviewee's latest guide, in full, for the editor (C5c). */
export function useGuide(engagementId: string, profileId: string | null) {
  return useQuery({
    queryKey: guideKey(engagementId, profileId ?? ""),
    queryFn: () => getGuide(engagementId, profileId ?? ""),
    enabled: Boolean(profileId),
  });
}

/** Saves Eric's edits to that guide. */
export function useEditGuide(engagementId: string, profileId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: GuideEdit) => editGuide(engagementId, profileId, body),
    onSuccess: (saved) => {
      client.setQueryData(guideKey(engagementId, profileId), saved);
      void client.invalidateQueries({ queryKey: guidesKey(engagementId) });
    },
  });
}

