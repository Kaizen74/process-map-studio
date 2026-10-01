<!-- prompt: codebook · version 1 -->
How a process map is built from the sources. Tier 1 rules never change. Tier 2 rules are the defaults: you may depart from one only when the passages give a reason, and you say so in the answer. Tier 3 is open: keep the SME's own words and groupings.

Tier 1 — invariants (never overridden)
- Use only the supplied passages; every claim cites them and quotes them exactly. A source that does not mention something is silent, never contradicting.
- One Responsible role per activity, and the activity sits in that role's lane. An approval sits in the lane of the role that approves it. A decision sits in the lane of the role that makes the routing call.
- Every decision has at least two labelled exits; every approval has an approve exit and a reject or rework exit.
- Exactly one Accountable role per step, or several all marked contested.
- Roles, never people.
- Complex and chaotic work is never an automation candidate.

Tier 2 — conventions (defaults)
- Unit of work: one activity is one Responsible role producing one outcome or handoff. Split when the role changes or something is handed over. Merge consecutive small actions by the same role with no handoff or decision between them.
- Element type: choosing between paths is a decision, phrased as a question with its criterion. Sign-off by someone other than the doer is an approval. Waiting or queueing is wait time on a step, not a step. Checking without branching is an activity with a control note. Complex judgment is a judgment step (one decision whose exits are typical responses). Anything else is an activity.
- Naming: verb and object, at most five words, sentence case, no role or person names. The SME's own term may be the label when it is the everyday name for the step.
- Sequence evidence, strongest to weakest: explicit order words or times ("first", "then", "after that", "around T-90"); the document's step order; dependency (something must exist before it is used); the order in which things were mentioned. Order resting only on the order of mentioning is weak and becomes a question.
- Phases: boundaries at handoffs between functions, stated milestones or stated time windows; the SME's phase names are preferred.
- RACI: R does the work; one A owns the outcome or signs off; C gives two-way input; I is told. If unclear, ask rather than guess.
- Time: work and wait are kept separate; ranges stay ranges; nothing is converted unless the passage states it.
- Exceptions: every "unless", "if not", "sometimes", "on a busy day" becomes a labelled branch, a typical response of a judgment step, or a question.
- Accounts: what the SME says should happen ("supposed to", "officially", "the rule is") is the official account; what the SME does or did ("what actually happens", a specific past case) is the lived account. The lived account describes the work as done.

Tier 3 — emergent (open)
- Keep the SME's own terms, phase names and ways of grouping the work alongside the standard categories.
- Patterns across stories that fit no category are proposed as emerging themes, never forced into one.

Worked examples (illustrative load-control sample)
- "First thing, I build the preliminary load plan off the booked figures" → activity "Draft load plan" in the Load controller lane; "First thing" is explicit order.
- "If something can't be accepted, the airline decides what to offload" → decision "Special loads OK?" (Load controller) with the exit "No" to the activity "Resolve or offload" in the Airline ops lane.
- "Officially the ramp should send the report within ten minutes" is official; "What actually happens on a busy wave is I walk down and read it off their sheet" is lived, and "on a busy wave" is a condition: a decision "Busy wave?" with the lived alternative "Read report at aircraft" as its "Yes" branch.
- "We sometimes wait fifteen minutes for it" is wait time on the step that receives the report, not a step.
