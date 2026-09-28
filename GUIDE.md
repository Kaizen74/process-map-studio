# Process Map Studio — Owner's Guide
*Updated: 2026-09-28 (build phase P7)*

This guide explains how to **use** the app. How to install, start, stop, update, move and back it up is in [README.md](README.md).

## What this app does
You give it the documents behind one process: an SME interview transcript, SOPs, job descriptions and supporting documents. Claude reads them and drafts a swimlane map of how the work is really done: steps, roles, who is responsible and accountable, decisions, approvals, timings, KPIs and constraints. Every step links to the exact passage it came from. The app checks the AI's work before you see it, and anything it can't find in your documents is thrown out and listed for you. You review every step, and nothing is published until you have.

## What you can do today
The app is being built in phases. At the moment (phase P8, finished 2026-09-28) you can start it, save your name and your Claude API key, create an engagement for each process, describe its scope and roles, upload documents and interview transcripts and read them inside the app, map each interview speaker to a role, keep a list of names the app hides, and **create a draft map**: Claude reads every source, every claim it makes is checked against your documents, and the checked claims are grouped into steps, compared source by source, checked a second time by the independent verifier and built into a draft map with questions for your SME. On **Review** you see the draft as a swimlane map or a table, open any step's details, follow each piece of evidence to the exact passage, and **review every step**: confirm it, edit it, reject it or add a step that is missing. Questions for your SME, rejected claims, the audit log, merge decisions and the map checks sit in tabs under the map. **Refresh draft from sources** redrafts only the steps you haven't reviewed. When every step is reviewed and the **quality card** is green, **Publish** the map: it becomes read-only on **Published**, and **Exports** gives it to you as the Master Process Map, a JSON file, a RACI spreadsheet and a single-file interactive map. Steps can also carry **pictures** (photos, screenshots, completed forms): you add them yourself, and pictures inside your PDFs are suggested on the steps whose evidence comes from the same page. Pictures stay inside the app and never go into an export.

**Start and stop** (full steps in [README.md](README.md)): double-click **Start.command** (Mac) or **start.bat** (Windows). Your browser opens the app at http://127.0.0.1:8000. Close the small window to stop it.

### The home screen (Engagements)
- Until you have saved a key and created an engagement, a **Get started** card lists three steps and ticks each one off: add your Claude API key, create an engagement, upload sources.
- Each engagement has a card: its name, its latest map version (or "No draft yet"), how many steps are reviewed, how many sources it has and when it last changed. Click anywhere on the card to open the engagement; the app takes you to the step that needs you next.
- **New engagement** asks for a name (usually the process, for example "Aircraft load control") and opens its Setup screen.
- **Delete** on a card asks first and says exactly what will be removed: the engagement, its source files, roles, drafts and published versions. This can't be undone.

### Inside an engagement: the guided path
When an engagement is open, the top bar shows its name and ten steps: Setup · Sources · Draft · Review · Published · Matrix · Gap analysis · Registers · Leadership · Exports. Each has a small mark and a spoken label:
- **filled circle:** done;
- **ring with a number:** needs attention (the number says how many things to resolve);
- **empty circle:** not started.

The step to do next carries a **Next** tag. Gap analysis is marked **Optional** and is never suggested as next. Screens from later build phases say which phase they arrive in.

### Setup, step by step
1. **Process scope** (left card): check the **Engagement name**, then fill in the **Trigger** (what starts the process) and **End point** (what marks it as finished). Setup counts as done once both are filled.
2. Add the other fields you know: process name, **In-scope roles**, **Out of scope**, **Process KPI**, **Industry** and **Adjacent industries**. For lists, type an entry and press Enter (or a comma); click the small × on a chip to remove it.
3. **Confidential terms:** add company, client, site and system names (for example your company's and customers' names). They are never sent to web research in the optional external analysis. They stay visible inside the app.
4. Click **Save scope**. If something is wrong, the message appears under the field concerned.
5. **Roles and lanes** (right card): add each role you already know under **Add a role**, with any other names the documents use for it (**Aliases**, for example "LC"). Tick **System role** for a system or tool rather than a person. Roles found in your sources are also added when the draft runs.
6. Put the lanes in order: drag a role onto another, or use **Move up** and **Move down**. The **Lane preview** shows the order the lanes will have on the map, top to bottom. **Edit** changes a role's name and aliases.

### Sources, step by step
1. Open **Sources** in the top bar. Drop files on the large box, or click **Choose files**. The app reads Word (.docx), PDF (.pdf), text (.txt) and subtitle (.vtt, .srt) files up to 50 MB each; anything else is refused with that list.
2. Each file appears in the table straight away with the status **Reading…**, and changes to **Ready** a moment later (or **Failed** with the reason). You don't need to wait on the screen: if you close the app while a file is being read, it finishes when you start it again. The app guesses each file's **Kind** from its name (for example "jd" → Job description, "interview" → Interview transcript); change it if the guess is wrong. Changing a file to or from **Interview transcript** reads it again the right way.
3. Fill in the **Version date**, **Owner** and **Controlled copy** where you know them. Changes save as soon as you leave the field.
4. Click a file's name (or its row) to open the **source viewer** below the table. It lists every passage with its anchor: **§3.1** (a clause), **p. 5** (a PDF page), **¶ 7** (a paragraph) or **06:40** (the time in an interview). These anchors are how each step on the map will point back to its evidence. PDF pages with almost no text (probably scanned) are listed; Claude reads them when you create the draft map. Pictures found in PDFs are saved without any hidden camera or location details and suggested on the matching steps when you create the draft map (see **Pictures on steps** below).
5. A passage that tries to give instructions to an AI (for example "ignore all previous instructions") carries the tag **Instruction-like text. Treated as data and ignored.** The app treats it as ordinary text in the document.
6. The box at the bottom says **Ready to draft** (with a link, **Go to Draft**) or lists exactly what is still needed, for example "Map 2 speakers in interview_transcript.txt".
7. **Delete** on a row removes that file and its passages after a confirmation.

### Interviews: speakers and names, step by step
The app splits an interview into who said what and when. It reads `[06:40] Name: text` or `Name: text` lines in text, Word and PDF files, and the speakers in .vtt and .srt subtitle files.
1. Add the roles on **Setup** first (for example "Load controller").
2. On **Sources**, open the interview. The **Speaker mapping** card lists each speaker as written in the file, with how many passages they have. For each, choose their **Role**, or **Interviewer** for the person asking the questions. Click **Save speakers**. The passages in the viewer now show the role next to each answer.
3. **Names to hide** (below the speaker mapping) lists the names the app keeps out of view. Speaker names that look like a person's name are added automatically, marked "from speaker label", and shown as their role once you map them (as "[name]" before that). Add anyone else who is mentioned by name, and nicknames or first names used on their own (for example "Priya" as well as "Priya Nair"), under **Name to hide**, optionally with what to show instead. The × removes a name from the list.
4. Names appear in only three places: the speaker mapping, the names list and the correction editor. Everywhere else, including file names, the app shows the role or "[name]". Names never go into the map, exports or anything sent to Claude.
5. To fix words the transcript got wrong, click **Correct the text** in the viewer, then **Correct** on a passage, change the text and click **Save correction**. Corrected passages are tagged **Corrected** and are kept if the file is read again. Click **Done correcting** to go back.

### Draft, step by step
1. Open **Draft** in the top bar (or **Go to Draft** on Sources). **Before drafting** lists four things: your Claude API key saved, at least one interview transcript read, at least one process document read (an SOP or manual), and every speaker mapped to a role. Each shows **Done** or **To do** with a link to fix it, and "Still needed" says exactly what is missing.
2. Click **Create draft map**. If something is still missing, the app says what instead of starting.
3. While Claude works you see all seven stages with their status and how long each has taken:
   - **Reading the documents** (including scanned PDF pages);
   - **Extracting steps from each source**;
   - **Checking every quote against your documents**;
   - **Comparing sources**: the claims are grouped into steps and each source is compared with them (agrees, adds detail, differs, contradicts, or says nothing);
   - **Independent verification**: each step is checked a second time against only its own evidence;
   - **Building the map**: lanes, phases, the order of steps, who is responsible and accountable, times, constraints and where AI might help;
   - **Writing validation questions** for your SME.

   If you switched off the independent verifier in Settings, that stage shows a dash and **Switched off in Settings**. Below the stages: **Claims verified**, **Rejected** and **Tokens used so far**, updating every second. You can leave the screen; drafting carries on, and the screen picks it up again when you come back.
4. When it is done, **Draft v0.1** says how many checked claims it was built from and shows **Steps drafted**, **Needs check** (steps the verifier only partly supported), **Rejected claims** and **Open questions**. **Start reviewing** takes you to Review. The home screen card and the **Review** step in the top bar now show how many steps are waiting for your review.
5. **Rejected claims** lists every claim that failed a check, struck through, with the reason in red (for example "number not found in cited text: 30"), the check that caught it (for example **G5 · S1**), the file and passage, and **Open source** (or "Passage missing" when Claude cited a passage that doesn't exist). These never reach the map. The line above the list also says how many names in Claude's answers were replaced by roles and how many instruction-like passages were ignored.
6. If drafting stops, the stage that failed is marked **Failed**, the message says what happened and that nothing was saved, with **Try again** and **Copy details**.
7. **Draft again from sources** makes a fresh draft that replaces this one, with the next number (v0.2, v0.3 …), as long as you haven't reviewed any step. Once you have, use **Refresh draft from sources** on Review instead (see below): it keeps every step you reviewed.
8. Checks behind the scenes: a step is only kept if its claims passed every check; people's names never reach the map; a source that doesn't mention a step counts as silent, never as a contradiction; job descriptions never change how well a step is supported; every decision and approval is marked rule-based or judgment, and a judgment step is never suggested for automation. Each step's confidence is worked out from its evidence, not guessed by Claude.

### Review, step by step
1. Open **Review** in the top bar (or **Start reviewing** on Draft). Without a draft it says so and links to Draft.
2. **The banner** at the top shows the draft's version (for example **Draft v0.1**), how many sources it was made from, and **n of N steps reviewed** with one small segment per step in process order: grey until reviewed, green once reviewed, darker grey when rejected. Click a segment to open that step.
3. **Four cards** show the **Trigger**, the **End point**, the **Cycle time** along the main path (work plus waiting, with a red line such as "Incomplete: 2 steps without time" when some steps have no time) and the **Process KPI** ("Not stated" if Setup has none).
4. **The map** is drawn from the backend's layout: one lane per role (lanes of approvals and exception steps sit just above the lane they come from), phases along the top, and steps in process order from left to right.
   - **Shapes:** rounded box = activity, diamond = decision (its name underneath), pill = approval, filled dot = start, double ring = end.
   - **Marks** (never more than three per step): a dashed outline = not reviewed yet; an orange dot = a key constraint; a small picture = the step has pictures.
   - **Lines:** arrows show the order. Dashed lines are loops back (rework or re-plan). Every exit of a decision or approval is labelled (Yes, No, Approve, Rework …).
   - **Lenses** change only the line under each step: **Plain** (its time, or "No time stated" in red), **Source state** (how well the sources agree, as a symbol with its name), **Confidence** (a bar and the value, orange and red below 0.60) and **Time** (work as a solid bar, waiting as a hatched bar, and the minutes). The app remembers your lens. The legend under the map explains the shapes and the current lens.
   - **Fit** shrinks the map to the width of the screen; **100%** shows it full size and lets you scroll sideways. The line above the map counts steps, lanes and phases, and turns red with "Large map: consider splitting by phase" above 25 steps or 6 lanes.
5. **Click a step** (or use Tab to move through the steps in process order and Enter to choose one). Its lines turn dark so you can follow its flow, and the panel on the right shows:
   - what kind of step it is, its phase and lane, and chips for how it was found (**Observed · O** or **Inferred · I**), how well the sources agree (**Contested** in red when they disagree), any **Divergence** (for example "threshold" or "ownership"), its **Confidence** and **Unreviewed**;
   - **Evidence:** one card per source. Cards that support or contradict the step show the quoted words and, in red, what differs (for example "Threshold divergence: 10 min in the SOP vs up to 15 min wait in practice"). A source that says nothing is shown in grey as **Silent**: silence is never counted as a contradiction;
   - **How confidence was computed:** each part of the score (for example "Observed (O) +0.60", "Capped at 0.60 while contested −0.10") and the total, which always equals the confidence shown;
   - **Role and accountability:** each role's letter (R responsible, A accountable, C consulted, I informed). When the sources disagree about who is accountable, it shows **A?** in red and names the sources on each side;
   - **Decision rights** (for decisions and approvals: rule-based or judgment, who decides, the rule and the escalation), **Handoff**, **Time**, **KPI**, **Key challenges and constraints**, **Knowledge risk** and the **AI flag**, where they apply.
6. **Click a piece of evidence** to open that source in the panel at the exact passage: the passage is framed and the quoted words highlighted. People's names are always replaced by roles. **← Back to [step]** (or Esc) returns to the step.
7. **Close details** shows **How to review** again, with **Start with the first step that needs attention**.

### Review, step by step (reviewing each step)
1. **Start with the first step that needs attention** opens the first step the verifier only partly supported, else the first unreviewed step.
2. Under the step's name you see what to do:
   - **Confirm as drafted** locks the step: refreshing the draft never changes it. A red line warns you first when the independent verifier found only partial support.
   - **Edit** opens the edit form (below).
   - **Reject step** fades it on the map; the map checks then show which steps lost their connection. **Restore** brings it back as unreviewed.
   After Confirm, Save or Reject, the next step that needs you opens by itself (steps needing a check first, then in process order). When none is left, **All steps reviewed** says so.
3. **The edit form** has every field of the step: name, kind, lane, who is Responsible, Accountable, Consulted and Informed, work and waiting minutes, time window, complexity, KPI, decision rights (rule-based or judgment, who decides, the rule, the escalation), handoffs, constraints (add or remove), knowledge risk and the AI flag. The name and an Accountable role are required, and an activity needs a Responsible role. A field that isn't right gets a red border and a message just below it, and nothing is saved until everything is right. A judgment step can never be marked as an automation candidate, and a name from your hidden-names list is refused. **Cancel** or Esc throws the changes away. Only what you changed is saved, and the step becomes **Edited** (locked).
4. **Add a missing step after this one** (at the bottom of the details), or **More → Add missing step** above the map: give it a name, kind, lane and where it goes, and say where it comes from. **Observed in a source** needs a passage: **Pick a passage**, choose the source, and click **Use this passage** next to the right one (you can pick several). **Recommended practice** needs the reference you are relying on. The new step is **Added**, locked, and placed straight into the flow.
5. **Map | Table:** the table lists every step with its kind, lane, provenance, source state, time, confidence and review status. Filter it by **Needs check**, **Unreviewed** or **Contested**. Click a row to open the step. **Edit in place** changes the name, Responsible, Accountable, minutes and KPI without leaving the table; everything else is in the full edit form.
6. **Tabs under the map:**
   - **RACI matrix:** every step against every role; **A?** marks a disputed accountable role. Click a row to open that step.
   - **Validation questions:** the questions for your SME session, grouped by phase, with why each was asked. **Go to [step]**, **Mark answered** or **Reopen**. **Copy all** puts them on the clipboard and **Download .md** saves them as a file for the session.
   - **Rejected claims:** every claim that failed a check, with the reason. **Open passage** shows the passage; if the step is real, **Add as step from this passage** starts a new step with that passage already picked.
   - **Audit log:** every change, newest first: time, what was done, which step and by whom.
   - **Merge decisions:** where Claude thought two descriptions might be the same step, side by side with their quotes. **Accept merge**, **Keep separate**, or **Split** a merge again.
   - **Map checks:** what must be fixed before publishing (for example a decision with an unlabelled exit) and what is worth a look, each with **Go to step**.
7. **Keyboard:** **J** and **K** move to the next and previous step, **C** confirms, **E** edits, **R** rejects, **1** to **4** switch lens, **Esc** closes the source or a form, and **?** shows the list. They do nothing while you are typing in a field.
8. **More → Refresh draft from sources** (for example after adding a source): Claude reads every source again and redrafts only the steps you haven't reviewed. Steps you confirmed, edited, added or rejected stay exactly as they are, questions you marked answered stay answered, and the draft gets the next number (v0.2). The Draft screen shows its progress.

### Pictures on steps, step by step
Pictures help you and your SMEs see what a step looks like. They stay inside the app: no export ever includes them, and every picture is saved without its hidden camera and location (GPS) details.
1. Open a step on **Review**. Its details end with **Images** ("In-app only · never exported · metadata stripped").
2. **Add image to this step** opens a short form: choose the picture (JPG, PNG or WebP, up to 10 MB), write a caption using role names rather than people's names, choose what kind of picture it is (workplace photo, system screenshot, completed form or record, illustrative diagram or extract from a document) and tick **Faces, names, badge numbers and flight identifiers are removed or not shown**. All four are needed; **Add picture** tells you what is still missing and saves nothing until it is all there. A caption containing a name from your hidden-names list is refused.
3. **Suggested pictures:** when you create or refresh a draft, a picture inside one of your PDFs is suggested on each step whose checked evidence comes from the same PDF page. A suggestion has a dashed border and says which file and page it came from. **Keep** asks for its type and the privacy tick (the caption is filled in for you, and you can change it); **Discard** hides it for good. Publishing waits until every suggestion is kept or discarded (the quality card's "Fully reviewed" check counts them). A step you reject stops counting.
4. **Remove** takes away a picture you added, after asking you first.
5. **On the map**, a step with pictures has a small picture mark at its top-left corner. Under the map, the **Visual walkthrough** shows every kept picture in process order ("Step 3 · Draft load plan" and the caption); click a card to open that step.
6. On **Published**, pictures and the walkthrough are shown but can't be changed. **Reopen as new draft** keeps them.

### Quality card and publishing, step by step
1. The Review banner shows **Quality card: n of 9 green** with a dot (orange until everything is green). Click it to see all ten checks: provenance, verified evidence, labelled exits, lanes and ownership, AI flags, fully reviewed, facts/interpretation/recommendation kept apart, no hidden names in the exports, no images in the exports, and map size (a size warning never stops you publishing). A failing check says in red what to fix; warnings such as steps without a time are listed beneath.
2. Click **Publish**. If anything still stops it, the same box opens as **Publish blocked** and lists every item (for example "“Draft load plan” hasn't been reviewed yet"). Click an item to go straight to its step.
3. When everything is green, **Publish** makes the first published version **v1.0** (then v1.1, v1.2 …), records you as the validator and opens the **Published** screen. A published version never changes.

### Published, step by step
1. **Published** shows the published map exactly like Review, but read-only: no review buttons, no outlines, no editing, and no Merge or Map checks tabs. The banner says who validated it and when.
2. **Version** switches between published versions; earlier ones are marked **superseded**.
3. **Changes in this version** lists what was confirmed, edited, rejected or added while it was the draft.
4. **Reopen as new draft** (on the latest version) makes a new draft, for example **v1.1 draft**, with every step you reviewed still locked, and opens it on Review. Review it, then publish it as v1.1. While a draft is open, the button becomes a link to it.

### Exports, step by step
1. **Exports** offers four downloads of a published version (choose the **Version** at the top): **Master Process Map (.md)** (the full write-up in three sections: facts, interpretation, recommendation), **Graph (.json)** (the map as data, for other tools), **RACI (.csv)** (opens in a spreadsheet) and **Interactive map (.html)** (the swimlane map in one file that opens in any browser, even offline; click a step to jump to its details).
2. Every export uses role names only and leaves out images, verbatim quotes and the names on your hidden-names list. Rejected steps are left out. The quality card is printed at the top.
3. Before anything is published, the screen explains that you need a published version with a green quality card first.

### Settings, step by step
1. Click **Settings** (top right), or **Add your Claude API key** on the home screen.
2. **Claude connection:** paste your key into **Claude API key** and click **Save key**. The box empties and the card shows "Saved key ••••••••" followed by the key's last 4 characters. That is all the app will ever show of it. To get a key: sign in at platform.claude.com → API keys → Create key → copy it once.
3. Click **Test connection**. You'll see a line for each check: **Key valid**, **Model available**, **PDF input**, **Structured outputs**. You want **Pass** or **Yes** on every line. If the key was rejected, copy it again from the Claude Console and save it again.
4. **Your name:** type your name and click **Save name**. It appears as the validator on published maps and exports.
5. **Model:** the list shows the Claude models your key can use (default: Claude Opus 5.5). **Effort** controls how hard Claude thinks; **High** is recommended. Leave **Independent verifier** ticked: it checks every step a second time against only its evidence. If you untick it, the card warns that confidence scores will be lower. Click **Save model settings**.
6. **AI usage** lists every call the app has made to Claude, newest first: when, which stage (for example "Extracting steps (interview)"), the model, input and output tokens, how long it took and whether it worked, with all-time totals above the table. Only these numbers are kept, never your documents. Before your first draft it says "No AI calls yet".
7. **About** shows the app and PRD versions (useful when reporting a problem).

A short message in the bottom-left confirms each save. If anything goes wrong, the app says what happened in plain words and offers **Copy details** for a bug report. Settings take effect straight away; there is no need to restart.

One Settings card arrives later: **Web research** (for the optional external best-practice analysis, phase P10).

| Screen | What it will do | Arrives in |
|---|---|---|
| Home (Engagements) | Your engagements, with a three-step first-run checklist | Now |
| Settings | Your name, your Claude API key, model choice, connection test, AI usage log | Now (web research P10) |
| Setup | The process scope card, roles and lanes | Now |
| Sources | Upload and read documents and interviews, map speakers to roles, hide names, correct transcripts; scanned pages read while drafting (now); coverage (P9) | Now, P9 |
| Draft | Create a draft map and watch all seven stages; its steps, checks, rejected claims and open questions | Now |
| Review | The draft map and table, the detail panel, evidence opened at the passage; confirm, edit, reject and add steps; questions, rejected claims, audit, merges and map checks; refresh the draft | Now |
| Published and Exports | Read-only published maps with versions, change log and Reopen; Markdown, JSON, CSV and HTML exports | Now |
| Matrix and Registers | Source alignment and the registers | P9 |
| Gap analysis (optional) | Documents vs practice, and external best practice | P10 |
| Leadership | Where the process jams and why | P11 |

## How to use it
Step-by-step workflows (set up, upload, draft, review, publish, gap analysis, export) are added here as each screen is built.

## What changed recently
- 2026-09-28 (phase P8): **Pictures on steps.** Add a photo, screenshot or form to any step with a caption, a type and the privacy tick; the app removes the hidden camera and location details before saving it. Pictures inside your PDFs are suggested on the matching steps for you to keep or discard, and publishing waits until you have. Steps with pictures carry a small mark on the map, and the new **Visual walkthrough** under the map shows them in process order. Pictures never go into an export. Also fixed: the **Names to hide** list on Sources now updates as soon as a transcript has been read. The approved Review screenshots did not change.
- 2026-09-28 (phase P7): **Publishing.** The Review banner shows the quality card (ten checks) and **Publish**; if something is missing, Publish lists every item and each one opens its step. Published maps are read-only on the new **Published** screen, with a version picker, what changed, and **Reopen as new draft**. The new **Exports** screen downloads the Master Process Map, JSON, a RACI spreadsheet and a single-file interactive map, all without images, quotes or names. You approved the new Review screenshots.
- 2026-09-27 (phase P6): **Review** is now the review workbench. Confirm, edit, reject or restore each step, and the next one opens by itself. Add a missing step from a passage or a reference. Switch between the map and a table (with filters and editing in place). Tabs under the map hold the validation questions (copy or download them for the SME session), rejected claims, the audit log, merge decisions and the map checks. Keyboard shortcuts (press ?). **Refresh draft from sources** keeps every step you reviewed. You approved the new Review screenshots, which are checked automatically at every run.
- 2026-09-27 (phase P5): **Review** draws the draft as a swimlane map with four lenses, Fit and 100%, a progress bar per step and the process cards. Clicking a step shows its evidence (with the quoted words), how its confidence was worked out, who is responsible and accountable (disputes marked A?), decision rights, time, constraints and AI flags; each piece of evidence opens the source at the exact passage. A RACI matrix sits under the map. The Review screen you approved is now checked automatically at every run, so an accidental change to how the map looks is caught.
- 2026-09-27 (phase P4): The draft now becomes a map. After the claims are checked, Claude groups them into steps, compares every source with them, the independent verifier checks each step again, and the map is built with lanes, phases, responsibilities, times, constraints and validation questions. **Draft** shows steps drafted, steps to check, rejected claims and open questions; the home card and the **Review** step count the steps waiting for you. Viewing the map arrives in phase P5.
- 2026-09-26 (phase P3): Drafting. On **Draft**, create a draft: Claude reads every source (and scanned PDF pages) and every claim it makes is checked against your documents; claims whose passage, quote, numbers or roles can't be found are rejected with the reason and listed. Watch each stage live; **Settings → AI usage** logs every call with its tokens.
- 2026-09-26 (phase P2): Interviews. Transcripts in text, Word, PDF and subtitle files are split into who said what and when; map each speaker to a role on **Sources**; a **Names to hide** list keeps people's names out of view everywhere except three owner-only places; fix transcript text with **Correct the text**; passages that try to instruct an AI are tagged. Files are now read in the background ("Reading…").
- 2026-09-26 (phase P1): Engagements. Create, open and delete engagements from the home screen; describe the process and its roles and lanes on **Setup**; upload Word and PDF documents on **Sources** and read them passage by passage with their anchors. The guided path in the top bar shows what is done and what to do next.
- 2026-09-26: The app has its look and feel (calm colours, IBM Plex fonts stored inside the app), a top bar, the home screen with the **Get started** checklist, and the **Settings** screen: save your name and API key, test the connection, choose the model. Every screen is checked automatically for accessibility.
- 2026-09-26: Project foundations (phase P0a). The app can be installed and started with double-click files, backs up its database before any update, and a safety check stops your API key and your data folder from ever reaching GitHub.

## Glossary
- **Engagement:** one process you are mapping, with its documents and map versions.
- **SME:** subject-matter expert; the person interviewed about how the work is done.
- **Swimlane map:** a process map with one horizontal lane per role.
- **Provenance (O / I / R):** where a step came from: observed in a source, inferred from a source, or recommended from external practice (added only by you).
- **API key:** the password-like code that lets the app use Claude on your Anthropic account. It stays on your computer.
- **Fixture:** illustrative sample data used to test the app. It is not real SATS data.
- **Model:** the version of Claude that reads your documents (for example Claude Opus 5.5).
- **Effort:** how much thinking Claude does on each task; higher is more thorough, slower and costs more.
- **Independent verifier:** a second check of every drafted step against only its own evidence.
- **Copy details:** a button on error messages that copies a short code for a bug report.
- **Anchor:** the short reference to a passage in a source, such as §3.1, p. 5 or ¶ 7.
- **Lane:** one horizontal band of the map, for one role.
- **Confidential terms:** names that must never be sent to web research.
- **Speaker mapping:** telling the app which role each speaker in an interview has (or that they are the interviewer).
- **Names to hide (redaction list):** people's names the app replaces with their role or "[name]" everywhere except three owner-only places.
- **Instruction-like text:** a passage that reads like an instruction to an AI; it is kept as ordinary text and never followed.
- **Source state:** how well a step is supported: corroborated (interview and documents agree), practiced only (interview only), documented only (documents only), contested (sources disagree) or trace contradicted (a record of the work disagrees).
- **Needs check:** a step the independent verifier found only partly supported by its evidence.
- **Lens:** a way of reading the map that changes only the line under each step (time, source agreement, confidence).
- **Divergence:** a difference between sources about a step, such as a time threshold (threshold) or who owns it (ownership).
- **RACI:** Responsible, Accountable, Consulted, Informed: who does, owns, advises on and hears about each step.
- **Validation question:** a question for your SME about a step whose sources disagree, that only one kind of source describes, or that nobody could answer from the documents.
