# Candidates waiting for Eric's approval (2026-10-06)

These files show what the app's saved reference outputs ("golden baselines") will become once you approve. Nothing here replaces anything until you say "approved".

| File to open | What it is | What changed |
|---|---|---|
| `G5_map.candidate-1440.png` | A picture of the whole HTML map export of the sample | Easiest to look at first. The export now draws **both maps** ("Map as done" and "Map as documented") instead of one, and adds the new sections listed below |
| `G5_map.candidate.html` | The HTML map export itself (open in a browser; fonts are left out of this copy) | Same as the picture |
| `G3_master_map.candidate.md` | The Master Process Map export of the sample | New sections from PRD v1.11 §7.3 (listed below), a View column in each phase's step table, and the new quality-card row Q11 |
| `G1_graph.candidate.json` | The graph JSON of the sample | Each step gains two empty fields, `level` and `parent_element_id` (team-level vs detailed steps; the sample has only one level) |

**New in both map exports (decision B):**
- Section 1 Facts: **Stories** (in the SME's own words, never a verbatim quote) and **Strengths as stated**.
- Section 2 Interpretation: a **View** column (both · as done · as documented), **Two views**, **Work type and know-how**, **Official vs lived**, **Glossary of SME terms**.
- Section 3 Recommendation: **Preserve / Improve** and **Reality gaps by gap class** first; **Disposition and value** and **System records** last, each saying "Not used in this engagement." until those optional modules are switched on.
- Quality card: **Q11 Work types confirmed** (a warning, never a blocker). On the sample it says 5 decisions or approvals still need their work type confirmed, which you do with **Confirm work type** in each step's details.
- Two new warnings under the card: the same work-type reminder, and "Fewer than three kinds of story" (the sample interview has only a story about a time it went badly).

To approve, reply "approved" (or say what to change). After approval these become the baselines and the work is committed and pushed.

For the builder: `K2-K3-pending.patch` holds the code, tests and new baselines of K2 and K3 (not yet committed), so the work survives if the build machine is restarted before approval. On approval it is already applied in the working copy; otherwise apply it with `git apply docs/review/K2-K3-pending.patch`. The frontend test sample (`frontend/tests/fixtures/sample_map.json`) gains the same two empty fields per step as G1.
