# Waiting for your approval: cycle time and exceptions in the exports

You said yes to (1) basing the cycle time on the usual route and (2) adding exceptions and
workarounds to the Master Process Map and the HTML map. Both are built and tested. Because they
change three reference files you approved earlier, the new versions wait here until you say yes.

## What changes

1. **Cycle time (reference file G1).** The cycle time now follows the usual route: it no longer
   runs through the busy-wave workaround ("Read report at aircraft") and it now goes through
   "Special loads OK?". On the sample the time stays the same (about 75 minutes elapsed, 60 of
   work), but the steps without a time drop from 3 to 1 (only "Issue load sheet" has no time).
   The map as one now uses the As done view's figure. On Review the header strip says
   "Incomplete: 1 step without time" instead of "2 steps".
2. **Exports (reference files G3 and G5).** The Master Process Map and the HTML map gain a section
   "Exceptions, rework and workarounds (as done)": the line of facts, each exception route and
   variation (where it starts, the steps and lanes, where it rejoins or loops back, the extra
   hand-overs, how often, the reason given), the rework loops, the workarounds and the "how
   often?" questions still to ask. Nothing else in either file changes.

## Files to open

- `G3_master_map-candidate.md`: search for "Exceptions, rework and workarounds".
- `G5_map-candidate.html`: open it in your browser; the section is under "Two views".
- `G1_graph-candidate.json`: only one number changes (`incomplete_steps` 3 → 1).

Reply "approve" and these become the reference files, the change in `x5-x6-pending.patch` goes
into the app, and this folder is removed.
