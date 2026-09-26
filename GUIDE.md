# Process Map Studio — Owner's Guide
*Updated: 2026-09-26 (build phase P2)*

This guide explains how to **use** the app. How to install, start, stop, update, move and back it up is in [README.md](README.md).

## What this app does
You give it the documents behind one process: an SME interview transcript, SOPs, job descriptions and supporting documents. Claude reads them and drafts a swimlane map of how the work is really done: steps, roles, who is responsible and accountable, decisions, approvals, timings, KPIs and constraints. Every step links to the exact passage it came from. The app checks the AI's work before you see it, and anything it can't find in your documents is thrown out and listed for you. You review every step, and nothing is published until you have.

## What you can do today
The app is being built in phases. At the moment (phase P2, finished 2026-09-26) you can start it, save your name and your Claude API key, create an engagement for each process, describe its scope and roles, upload documents and interview transcripts and read them inside the app, map each interview speaker to a role, and keep a list of names the app hides. Drafting the map arrives in phase P3.

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
4. Click a file's name (or its row) to open the **source viewer** below the table. It lists every passage with its anchor: **§3.1** (a clause), **p. 5** (a PDF page), **¶ 7** (a paragraph) or **06:40** (the time in an interview). These anchors are how each step on the map will point back to its evidence. PDF pages with almost no text (probably scanned) are listed; they will be read in phase P3. Pictures found in PDFs are kept as suggestions for you to review in phase P8.
5. A passage that tries to give instructions to an AI (for example "ignore all previous instructions") carries the tag **Instruction-like text. Treated as data and ignored.** The app treats it as ordinary text in the document.
6. The box at the bottom says **Ready to draft** or lists exactly what is still needed, for example "Map 2 speakers in interview_transcript.txt".
7. **Delete** on a row removes that file and its passages after a confirmation.

### Interviews: speakers and names, step by step
The app splits an interview into who said what and when. It reads `[06:40] Name: text` or `Name: text` lines in text, Word and PDF files, and the speakers in .vtt and .srt subtitle files.
1. Add the roles on **Setup** first (for example "Load controller").
2. On **Sources**, open the interview. The **Speaker mapping** card lists each speaker as written in the file, with how many passages they have. For each, choose their **Role**, or **Interviewer** for the person asking the questions. Click **Save speakers**. The passages in the viewer now show the role next to each answer.
3. **Names to hide** (below the speaker mapping) lists the names the app keeps out of view. Speaker names that look like a person's name are added automatically, marked "from speaker label", and shown as their role once you map them (as "[name]" before that). Add anyone else who is mentioned by name, and nicknames or first names used on their own (for example "Priya" as well as "Priya Nair"), under **Name to hide**, optionally with what to show instead. The × removes a name from the list.
4. Names appear in only three places: the speaker mapping, the names list and the correction editor. Everywhere else, including file names, the app shows the role or "[name]". Names never go into the map, exports or anything sent to Claude.
5. To fix words the transcript got wrong, click **Correct the text** in the viewer, then **Correct** on a passage, change the text and click **Save correction**. Corrected passages are tagged **Corrected** and are kept if the file is read again. Click **Done correcting** to go back.

### Settings, step by step
1. Click **Settings** (top right), or **Add your Claude API key** on the home screen.
2. **Claude connection:** paste your key into **Claude API key** and click **Save key**. The box empties and the card shows "Saved key ••••••••" followed by the key's last 4 characters. That is all the app will ever show of it. To get a key: sign in at platform.claude.com → API keys → Create key → copy it once.
3. Click **Test connection**. You'll see a line for each check: **Key valid**, **Model available**, **PDF input**, **Structured outputs**. You want **Pass** or **Yes** on every line. If the key was rejected, copy it again from the Claude Console and save it again.
4. **Your name:** type your name and click **Save name**. It appears as the validator on published maps and exports.
5. **Model:** the list shows the Claude models your key can use (default: Claude Opus 5.5). **Effort** controls how hard Claude thinks; **High** is recommended. Leave **Independent verifier** ticked: it checks every step a second time against only its evidence. If you untick it, the card warns that confidence scores will be lower. Click **Save model settings**.
6. **About** shows the app and PRD versions (useful when reporting a problem).

A short message in the bottom-left confirms each save. If anything goes wrong, the app says what happened in plain words and offers **Copy details** for a bug report. Settings take effect straight away; there is no need to restart.

Two Settings cards arrive later: **AI usage** (a log of every AI call, once drafting exists) and **Web research** (for the optional external best-practice analysis, phase P10).

| Screen | What it will do | Arrives in |
|---|---|---|
| Home (Engagements) | Your engagements, with a three-step first-run checklist | Now |
| Settings | Your name, your Claude API key, model choice, connection test | Now (usage log P3, web research P10) |
| Setup | The process scope card, roles and lanes | Now |
| Sources | Upload and read documents and interviews, map speakers to roles, hide names, correct transcripts (now); read scanned pages (P3); coverage (P9) | Now, P3, P9 |
| Draft | Create the draft map and watch each stage | P3, P4 |
| Review | The workbench: map, lenses, detail panel, evidence, review actions | P5, P6 |
| Published and Exports | Read-only published maps; Markdown, JSON, CSV and HTML exports | P7 |
| Matrix and Registers | Source alignment and the registers | P9 |
| Gap analysis (optional) | Documents vs practice, and external best practice | P10 |
| Leadership | Where the process jams and why | P11 |

## How to use it
Step-by-step workflows (set up, upload, draft, review, publish, gap analysis, export) are added here as each screen is built.

## What changed recently
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
