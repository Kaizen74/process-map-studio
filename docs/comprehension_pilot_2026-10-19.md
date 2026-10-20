# Reality views: comprehension test, pilot run (2026-10-19)

**This is not the comprehension test, and it does not close P13.** The test in
[comprehension_test.md](comprehension_test.md) needs five people who have never seen the views.
This pilot used five fresh AI readers instead. Each played an executive, had no project context and
no explanation, saw only the two pages below once, then answered the four questions from memory.
The aim was to find confusing wording or protocol problems before Eric spends real executives' time
on the test. AI readers are not executives, so a pass or failure here proves nothing about real
people.

## What was shown

The printed Reality pack (A3) of the sample version v1.0, using the protocol's printed option:
page 2 (Glance) and page 3 (Reality stack). Same files as `docs/screens/p13d-pack-a3-02-rv1.png`
and `p13d-pack-a3-03-rv2.png`.

## Right answers for this version (fixed before any reader answered)

| | A right answer names… |
|---|---|
| Q1 | 0% of cases follow the manual (every case adds a manual weight override) |
| Q2 | Check and load (the hotspot: 75 extra minutes a case, 9 hours a month) |
| Q3 | This version has no control exposure (no confirmed intent), so the largest impact class: time impact, chiefly X1 Special loads OK? (+20 min a case, 9 h a month) |
| Q4 | X1 Special loads OK?: the first code under Decide first, which is also the hotspot's largest gap |

## Results

| Reader (role played) | Q1 | Q2 | Q3 | Q4 | All four? | What confused them |
|---|---|---|---|---|---|---|
| 1 Chief financial officer | Right | Right | No: the weight override | No: the weight override | No | Legend symbols not on any item; numbers don't add up (+75 vs 20 + 15); placeholder rows; "mixed" |
| 2 Chief operating officer | Right | Right | No: the weight override (read "mainly as a time cost") | No: the weight override | No | "Measured, mixed, stated" unexplained; placeholder rows; symbols not applied to X1 to X3 |
| 3 HR director | Right | Right | No: unsure, guessed the weight override | No: Check and load and the override | No | Jargon; "Add intent statements" repeated; numbers don't add up; symbols not on any item |
| 4 Head of risk | Right | Right | No: the weight override | No: the weight override | No | Dense table; symbols not on any callout; which figure the 9 hours belongs to |
| 5 Chief executive | Right | Right | No: the weight override, "partly guessing" | No: the weight override | No | Couldn't match legend icons to X1 to X3; placeholder rows; "6 cases" next to "26 px = 100%" |

Result: 0 of 5 answered all four. Q1 and Q2 were right for all five. Q3 and Q4 were wrong for all
five, and in the same way.

## What it points to (proposals for Eric; nothing has been changed)

1. **Colour alone on the callouts (a defect).** The X1 to X3 boxes show their impact class only as
   a border colour; the symbol and word from the legend are missing
   (`frontend/src/components/reality/RealityBits.tsx:179`, and the same in the pack). All five
   readers said they couldn't tell which item was a risk and which was only time. This breaks the
   rule that every colour has its symbol and word (CLAUDE.md constraint 17). Proposed fix: put the
   impact symbol and word on every callout. It changes approved screenshots, so it needs Eric's
   approval of new ones.
2. **The sample isn't a fair test of Q3.** It has no confirmed intent, so it can show no control
   exposure, and "Add intent statements…" fills a row of the stack. Readers then read the 100%
   weight override as the main risk. That is a sensible reading the app can't confirm without
   intent (constraint 25). Proposed: run the real test on a version with confirmed intent (the
   A.12 example with its charter statements confirmed).
3. **Q4 can't be answered from the two pages.** "Decide first" is on the Fix or keep view, which the
   protocol doesn't show. Options: show Fix or keep as a third page; ask Q4 against the hotspot's
   largest gap only; or put the top "Decide first" item on Glance. Eric decides.
4. **The printed stack is a table, not the picture.** It says so on the page; readers found it a
   wall of text. Proposed: run the test on screen, or with an A3 picture of the stack.
5. **Smaller wording items.**
   - Say "no intent yet" once, not in every column.
   - Explain "measured, stated, mixed" in the footer.
   - Show how the callouts add up to the hotspot's +75 minutes.
   - Keep the line-width note ("26 px = 100%") off the printed Glance or explain it.

## What happens next

- P13 stays open until the real test (five people, `docs/comprehension_test.md`) passes and is
  logged.
- The proposals above wait for Eric's decision. A layout change needs his approval of new
  screenshots before it is used.

## Dry run after the changes (2026-10-19, same day)

Eric approved the callout fix, a version with confirmed intent shown on screen, and Fix or keep as a
third view. The test kit (`docs/comprehension_kit/`: Glance, Reality stack and Fix or keep of the
published built-in example, drawn by the app with the fix) was then shown to five fresh AI readers in
the same way. The answer key was fixed before any answer arrived (see the right-answer column of
[comprehension_test.md](comprehension_test.md)).

| Reader (role played) | Q1 | Q2 | Q3 | Q4 | All four? |
|---|---|---|---|---|---|
| 1 Chief financial officer | Right (70%) | Right (Check and load) | Right (approval never recorded) | Right (restore the approval) | Yes |
| 2 Chief operating officer | Right | Right | Right | Right | Yes |
| 3 HR director | Right | Right | Right | Right | Yes |
| 4 Head of risk | Right | Right | Right | Right | Yes |
| 5 Chief executive | Right | Right | Right | Right | Yes |

Result: 5 of 5 answered all four. **This is still not the test:** it shows the kit and questions work as
intended. Only five people can pass the views.

Still confusing to all or most readers (proposals for Eric, not changed):
- **Time figures that don't obviously reconcile (5 of 5).** Glance shows "6 h a month beyond the
  designed time", while the stack shows 24 hours a month at Check and load and 32 in all. These measure
  different things (time beyond a confirmed design target vs. time beyond the manual), but nothing on
  the screen says so.
- **"0 h a month" on the item to decide first (3 of 5).** X1 is a control exposure with no measured
  hours; it reads as if it doesn't matter.
- **Nine codes in one place, eight in another (3 of 5).**
- **Small text in the drawings** (the flow on Glance, the stack, the fix-or-keep grid) and the
  **D, I, S evidence boxes** with no key (4 of 5).

## The remaining confusions, fixed (2026-10-20)

Eric asked for all four to be fixed (DECISIONS 73):
- Glance's time tile is now the same "hours a month lost to the gaps" figure as the Reality stack.
- A gap with no measured time cost reads "No time cost measured" instead of "0 h a month".
- Fix or keep lists every gap among its codes.
- The view takes the full width, "Show full size" draws it larger, and the legend explains the
  D I S boxes.

The test kit was regenerated with these changes.

### Second dry run on the fixed kit (2026-10-20)

The same five roles, as fresh AI readers, on the regenerated kit, with the same answer key.

| Reader (role played) | Q1 | Q2 | Q3 | Q4 | All four? |
|---|---|---|---|---|---|
| 1 Chief financial officer | Right | Right | Right | Right | Yes |
| 2 Chief operating officer | Right | Right | Right | Right | Yes |
| 3 HR director | Right | Right | Right | Right | Yes |
| 4 Head of risk | Right | Right | Right | Right | Yes |
| 5 Chief executive | Right | Right | Right | Right | Yes |

Result: 5 of 5. Compared with the first dry run:
- **Gone:** the 6 h vs 32 h clash and "0 h a month". Every reader quoted 32 h a month as the cost.
- **Still raised, now smaller:**
  - 32 h overall vs 24 h at the hotspot, and the stack's +53 min vs X2's +13 min. These are parts of a whole.
  - The Fix or keep grid is too small in a still picture (4 of 5).
  - Jargon (LIR, T-120) belongs to the example's domain.
- **New, for Eric (not changed):**
  - The Reality stack's fourth cost column (the whole process) has no heading in the drawing (2 of 5).
  - "70% follow the manual" beside "100% leave no record" read as a contradiction to two readers. The two figures measure different things: the route through the process, and one control's record.
