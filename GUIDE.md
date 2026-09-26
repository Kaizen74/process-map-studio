# Process Map Studio — Owner's Guide
*Updated: 2026-09-26 (build phase P0b)*

This guide explains how to **use** the app. How to install, start, stop, update, move and back it up is in [README.md](README.md).

## What this app does
You give it the documents behind one process: an SME interview transcript, SOPs, job descriptions and supporting documents. Claude reads them and drafts a swimlane map of how the work is really done: steps, roles, who is responsible and accountable, decisions, approvals, timings, KPIs and constraints. Every step links to the exact passage it came from. The app checks the AI's work before you see it, and anything it can't find in your documents is thrown out and listed for you. You review every step, and nothing is published until you have.

## What you can do today
The app is being built in phases. At the moment (phase P0b, finished 2026-09-26) you can start it, save your name and your Claude API key, and check the connection with Anthropic. Setting up engagements and uploading documents arrive in phase P1.

**Start and stop** (full steps in [README.md](README.md)): double-click **Start.command** (Mac) or **start.bat** (Windows). Your browser opens the app at http://127.0.0.1:8000. Close the small window to stop it.

### The home screen (Engagements)
- A **Get started** card lists three steps and ticks each one off when it's done: add your Claude API key, create an engagement, upload sources. Steps 2 and 3 say "Available from build phase P1" for now.
- **New engagement** explains that creating engagements arrives in phase P1.
- The top bar is on every screen: **Process Map Studio** (back to the home screen), **Engagements** and **Settings**.

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
| Home (Engagements) | Your engagements, with a three-step first-run checklist | Checklist now; engagements P1 |
| Settings | Your name, your Claude API key, model choice, connection test | Now (usage log P3, web research P10) |
| Setup | The process scope card, roles and lanes | P1 |
| Sources | Upload transcripts and documents; map speakers to roles; hide names | P1, P2 |
| Draft | Create the draft map and watch each stage | P3, P4 |
| Review | The workbench: map, lenses, detail panel, evidence, review actions | P5, P6 |
| Published and Exports | Read-only published maps; Markdown, JSON, CSV and HTML exports | P7 |
| Matrix and Registers | Source alignment and the registers | P9 |
| Gap analysis (optional) | Documents vs practice, and external best practice | P10 |
| Leadership | Where the process jams and why | P11 |

## How to use it
Step-by-step workflows (set up, upload, draft, review, publish, gap analysis, export) are added here as each screen is built.

## What changed recently
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
