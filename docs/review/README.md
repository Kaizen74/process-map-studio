# Waiting for your approval: the Matrix splits the interview into SME official and SME lived

P9u asks the Matrix to show four layers (SOP / manual · SME official · SME lived · executed
artefacts, plus job descriptions). The single Interview column is now two:

- **SME official**: what interviewees say about how the step is meant to work.
- **SME lived**: what they say they actually do.

Each shows **Supports** or **Contradicts** where the interview gives that kind of account,
**Silent** where it gives only the other kind (or doesn't mention the step), and **Account
unclear** where the interview mentions the step only in answers that are neither clearly official
nor clearly lived. The app never guesses which. On the sample, 3 steps are "Account unclear":
Resolve or offload, Deviation in limits? and Approve deviation.

Because this adds two fields to every row of the Matrix, it changes the reference file G4 you
approved earlier. Nothing else changes.

## Files to open

- `matrix-with-sme-layers.png`: the Matrix screen with the new columns (sample).
- `G4_alignment_matrix-candidate.json`: each row gains `sme_official` and `sme_lived`.

Reply "approve" and this becomes the reference file, the change in `p9u-2-pending.patch` goes into
the app, P9u is closed, and this folder is removed.
