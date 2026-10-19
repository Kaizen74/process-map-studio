import type { DraftAcceptance } from "./reviewTypes";

const steps = (n: number) => `${n} ${n === 1 ? "step" : "steps"}`;

/** "Of the 10 steps Claude drafted, you kept 6 as drafted, edited 2 and rejected 1; 1 isn't
 * reviewed yet. You added 2 steps yourself." Facts only: no verdict on the draft. */
export function acceptanceSentence(a: DraftAcceptance): string {
  if (a.drafted === 0) {
    return a.added === 0 ? "Claude drafted no steps in this version." : `Claude drafted no steps in this version; you added ${steps(a.added)}.`;
  }
  const parts = [`kept ${a.confirmed} as drafted`];
  if (a.edited) parts.push(`edited ${a.edited}`);
  if (a.rejected) parts.push(`rejected ${a.rejected}`);
  const done = parts.length === 1 ? parts[0] : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
  const open = a.unreviewed ? `; ${a.unreviewed} ${a.unreviewed === 1 ? "isn't" : "aren't"} reviewed yet` : "";
  const mine = a.added ? ` You added ${steps(a.added)} yourself.` : "";
  return `Of the ${steps(a.drafted)} Claude drafted, you ${done}${open}.${mine}`;
}
