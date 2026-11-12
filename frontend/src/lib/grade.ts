/**
 * The shared grade (DECISIONS 96): how sure a finding is, in the three words every app in the set
 * uses. The backend suggests it by rule; Eric may choose another, and his choice wins.
 */
export type GradeKey = "confirmed" | "indicated" | "hypothesis";

export interface Grade {
  grade: GradeKey;
  suggested: GradeKey;
  chosen_by_owner: boolean;
  rules_version: string;
}

export const GRADE_LABELS: Record<GradeKey, string> = {
  confirmed: "Confirmed",
  indicated: "Indicated",
  hypothesis: "Hypothesis",
};

export const GRADE_MEANINGS: Record<GradeKey, string> = {
  confirmed: "a system record and at least one other source support it",
  indicated: "at least one checked source supports it",
  hypothesis: "inferred, or not yet checked against a source",
};

export const GRADE_OPTIONS = (Object.keys(GRADE_LABELS) as GradeKey[]).map((value) => ({
  value,
  label: GRADE_LABELS[value],
}));
