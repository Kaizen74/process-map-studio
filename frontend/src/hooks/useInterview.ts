import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addProfile, editProfile, listGuides, listProfiles, makeGuide } from "../api/interview";
import type { ProfileInput } from "../lib/interview";

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

/** Makes a new version of one interviewee's guide. */
export function useMakeGuide(engagementId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (profileId: string) => makeGuide(engagementId, profileId),
    onSuccess: () => void client.invalidateQueries({ queryKey: guidesKey(engagementId) }),
  });
}
