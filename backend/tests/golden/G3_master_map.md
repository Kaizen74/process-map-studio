# Load control — Master Process Map

Version v1.0 · published 28 Sep 2026 · validated by Owner

Signal strength: Strong (3 of 3). Built from interviews and a written procedure (SOP or manual): steps can be corroborated or contested.

**Quality card**

| Check | Status | Detail |
|---|---|---|
| Q1 Provenance green | Pass | All 10 steps are tagged O, I or R. |
| Q2 Evidence verified | Pass | Every observed or inferred step has a verified passage. |
| Q3 Diamonds closed | Pass | Every decision and approval has all its exits, each labelled. |
| Q4 Lanes and ownership | Pass | Every step sits in the right lane, has one Accountable role and is connected. |
| Q5 Flags executable | Pass | Every AI flag is complete, and none is on a judgment step. |
| Q6 Fully reviewed | Pass | Every step, merge and suggested image has been reviewed. |
| Q7 Facts, interpretation and recommendation separated | Pass | The exports keep facts, interpretation and recommendation in their own sections. |
| Q8 Anonymised | Pass | No name from your list of names to hide appears in any export. |
| Q9 Images contained | Pass | No image or image reference in any export. |
| Q10 60-minute validatable | Pass | 10 steps and 5 lanes: fits a one-hour session. |
| Q11 Work types confirmed | Warning | 5 decisions, approvals or judgment steps without a confirmed work type: “Approve load plan”, “Special loads OK?”, “Busy wave?” and 2 more. |

All hard checks green: yes.

Warnings:
- Approval "Approve load plan" has no time stated.
- Activity "Read report at aircraft" has no time stated.
- Activity "Issue load sheet" has no time stated.
- The line from "Load and return LIR" to "Busy wave?" rests only on the order the sources mention them.
- The line from "Read report at aircraft" to "Deviation in limits?" rests only on the order the sources mention them.
- 5 decisions, approvals or judgment steps without a confirmed work type: "Approve load plan", "Special loads OK?", "Busy wave?" and 2 more.
- Fewer than three kinds of story: none yet about a time it went well (M5.1); a time something surprised (M5.3).

## 1. Facts: what the sources tell us

### Source registry

| Source | Kind | Version date | Owner | Controlled copy |
|---|---|---|---|---|
| interview_transcript.txt | Interview | — | — | No |
| sop_LC-07.docx | SOP | — | — | No |
| sop_RP-02.docx | SOP | — | — | No |
| jd_load_control_lead.docx | Job description | — | — | No |
| jd_load_controller.docx | Job description | — | — | No |
| landscape_ramp_lead.txt | Interview | — | — | No |

### Pain points as stated in the sources

- [O] Only one other controller knows the widebody configurations (step: Draft load plan · interview_transcript.txt 06:40; sop_LC-07.docx §3.1; jd_load_controller.docx ¶ 2)
- [O] The cargo terminal's notification often comes late (step: Special loads OK? · interview_transcript.txt 14:05; sop_LC-07.docx §4; jd_load_controller.docx ¶ 2)
- [O] The paper loading report gets lost or arrives late. (step: Load and return LIR · interview_transcript.txt 21:50; landscape_ramp_lead.txt 02:18)
- [O] The loading report is on paper and re-keyed (step: Load and return LIR · interview_transcript.txt 21:50; landscape_ramp_lead.txt 02:18)
- [O] Containers run short at peak times (step: Load and return LIR · interview_transcript.txt 21:50; landscape_ramp_lead.txt 02:18)

### How well the sources agree

| Source state | Steps |
|---|---|
| Corroborated | 3 |
| Documented only | 1 |
| Practiced only | 4 |
| Contested | 2 |
| Trace contradicted | 0 |
| Not assessed | 0 |

### Stories

- [O] Had to re-trim three flights in one night (went badly · interview_transcript.txt 24:10; step: Draft load plan, Deviation in limits?)

### Strengths as stated (preserve)

- [O] Skillset: Ramp supervisors know the aircraft types inside out. (step: Load and return LIR)

## 2. Interpretation: how the process works

### Phase 1: Plan

Time window: T-120 to T-90.
Purpose: covers 2 steps, from “Draft load plan” to “Approve load plan”.

| Step | View | Lane | Prov | Source state | Time (work/wait) | Complexity | Data in → out | Flags |
|---|---|---|---|---|---|---|---|---|
| Draft load plan | both | Load controller | [O] | Corroborated | 20 min / not stated | M | — → Preliminary load plan | knowledge risk |

Decisions and approvals:

- [O] Approve load plan (approval, judgment, approver: Load control lead). Exits: Approve → Special loads OK?; Rework → Draft load plan.

This phase has 1 activity and 1 decision or approval, involving Load controller, Load control lead.

### Phase 2: Check and load

Time window: not stated.
Purpose: covers 5 steps, from “Special loads OK?” to “Read report at aircraft”.

| Step | View | Lane | Prov | Source state | Time (work/wait) | Complexity | Data in → out | Flags |
|---|---|---|---|---|---|---|---|---|
| Resolve or offload | as done | Airline ops | [O] | Practiced only | 40 min / not stated | — | — | — |
| Load and return LIR | both | Ramp | [O] | Contested | 40 min / 15 min | — | — → Loading report to the Load controller | key constraint, AI flag |
| Read report at aircraft | as done | Load controller | [O] | Practiced only | not stated / not stated | — | Loading report on the ramp's sheet → — | — |

Decisions and approvals:

- [O] Special loads OK? (decision, rule-based, decider: Load controller). Exits: Yes → Load and return LIR; No → Resolve or offload.
- [O] Busy wave? (decision, rule-based, decider: Load controller). Exits: Yes → Read report at aircraft; No → Deviation in limits?.

This phase has 3 activities and 2 decisions or approvals, involving Load controller, Airline ops, Ramp.

### Phase 3: Close out

Time window: T-15 to T-10.
Purpose: covers 3 steps, from “Deviation in limits?” to “Issue load sheet”.

| Step | View | Lane | Prov | Source state | Time (work/wait) | Complexity | Data in → out | Flags |
|---|---|---|---|---|---|---|---|---|
| Issue load sheet | both | Load controller | [O] | Corroborated | not stated / not stated | — | — | AI flag |

Decisions and approvals:

- [O] Deviation in limits? (decision, judgment, decider: Load controller). Exits: Within limits → Issue load sheet; Outside limits → Approve deviation.
- [O] Approve deviation (approval, judgment, approver: Captain). Exits: Accept → Issue load sheet; Re-trim → Load and return LIR.

This phase has 1 activity and 2 decisions or approvals, involving Load controller, Captain.

### RACI

| Step | Load controller | Load control lead | Ramp | Airline ops | Captain |
|---|---|---|---|---|---|
| [O] Draft load plan | R A | · | · | · | · |
| [O] Approve load plan | · | R A | · | · | · |
| [O] Special loads OK? | A | · | · | · | · |
| [O] Resolve or offload | · | · | · | R A | · |
| [O] Load and return LIR | · | · | R A | · | · |
| [O] Busy wave? | R A | · | · | · | · |
| [O] Read report at aircraft | R A | · | · | · | · |
| [O] Deviation in limits? | R | A? | · | · | A? |
| [O] Approve deviation | · | · | · | · | A |
| [O] Issue load sheet | R A | · | · | · | · |

A? means the sources disagree about who is accountable.

### Divergences between sources

| Divergence | Steps |
|---|---|
| Ownership | Deviation in limits? |
| Threshold | Load and return LIR |

### Two views: as done and as documented

- As done: 9 steps; only here: Resolve or offload, Busy wave?, Read report at aircraft, Approve deviation.
- As documented: 6 steps; only here: Approve load plan.

### Work type and know-how

| Step | Work type | Know-how (knowledge risk · dominant ASHEN) |
|---|---|---|
| [O] Draft load plan | Complicated (proposed) | — |
| [O] Approve load plan | Not classified | unknown · none described |
| [O] Special loads OK? | Clear (proposed) | low · artefacts |
| [O] Resolve or offload | Not classified | — |
| [O] Load and return LIR | Not classified | — |
| [O] Busy wave? | Not classified | unknown · none described |
| [O] Read report at aircraft | Not classified | — |
| [O] Deviation in limits? | Complex (proposed) | high · artefacts |
| [O] Approve deviation | Not classified | unknown · none described |
| [O] Issue load sheet | Clear (proposed) | — |

### Official vs lived

- [O] Load and return LIR: official and lived accounts both given; they differ on time (as done: Up to fifteen minutes' wait for the report; as documented: Within 10 minutes of loading completion).

### Glossary of SME terms

- re-trim: Rebalance an aircraft's load after it has been planned. (step: Approve deviation)
- wave: A busy period of departures. (step: Busy wave?)
- forward hold: The cargo hold at the front of the aircraft. (step: Draft load plan)

## 3. Recommendation: enablement and gaps

### Preserve / Improve

- Skillset: preserve: Ramp supervisors know the aircraft types inside out.
- Systems: improve: The paper loading report gets lost or arrives late.

### Reality gaps by gap class

No reality gaps from a finalised documents-vs-practice analysis.

### AI flags

**[O] Special loads OK?**

- Component: Reasoning
- Input: Special load notification and acceptance checklist
- Output: Accept or refuse each special load
- Handoff: Load controller
- Basis: Rule-based: an automation candidate

**[O] Load and return LIR**

- Component: Perception
- Input: Paper loading report
- Output: Keyed loading data
- Handoff: Load controller
- Basis: Rule-based: an automation candidate

**[O] Issue load sheet**

- Component: Action
- Input: Final load figures
- Output: Load sheet issued through the departure control system
- Handoff: Captain
- Basis: Rule-based: an automation candidate

### Knowledge-risk register

- [O] Draft load plan: Widebody plans rely on the Load controller and one other controller

### External-practice register

No steps from external practice.

### Open validation questions

1. The SOP says the Load control lead approves the preliminary load plan before release to Ramp, but the interview never mentions it. Is this approval done in practice? (step: Approve load plan · Plan) · documented only
2. The SOP asks for the loading report within 10 minutes of loading, but in practice the wait can be 15 minutes. Which is right, and what causes the difference? (step: Load and return LIR · Check and load) · contested
3. When the weight deviation is outside tolerance, who decides: the Load control lead, as the SOP says, or the captain, as happens in practice? (step: Deviation in limits? · Close out) · contested
4. Who approves the preliminary load plan before it is released? · gap
5. Which role issues the final load sheet? · gap
6. What kind of work is "Approve load plan"? Is it done by following a fixed rule, worked out by someone experienced, a judgment call that depends on the situation, or firefighting? (step: Approve load plan · Plan) · work type not clear
7. What kind of work is "Busy wave?"? Is it done by following a fixed rule, worked out by someone experienced, a judgment call that depends on the situation, or firefighting? (step: Busy wave? · Check and load) · work type not clear
8. What kind of work is "Approve deviation"? Is it done by following a fixed rule, worked out by someone experienced, a judgment call that depends on the situation, or firefighting? (step: Approve deviation · Close out) · work type not clear
9. Does "Busy wave?" come right after "Load and return LIR"? The sources mention it later but don't say it comes next. (step: Busy wave? · Check and load) · order not stated
10. Does "Deviation in limits?" come right after "Read report at aircraft"? The sources mention it later but don't say it comes next. (step: Deviation in limits? · Close out) · order not stated

### Cause library entries (pending validation)

- [O] Load and return LIR · threshold: Threshold divergence: 10 min in the SOP vs up to 15 min wait in practice. [I] Likely cause: The loading report is on paper and re-keyed
- [O] Deviation in limits? · ownership: Ownership divergence: the Load control lead decides in the SOP, the Captain in practice. Likely cause: not known yet: ask your SMEs.

### Gap analyses

No finalised gap analyses.

### Disposition and value

Not used in this engagement.

### System records

Not used in this engagement.
