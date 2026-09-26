# Process Map Studio — Owner's Guide
*Updated: 2026-09-26 (build phase P0a)*

This guide explains how to **use** the app. How to install, start, stop, update, move and back it up is in [README.md](README.md).

## What this app does
You give it the documents behind one process: an SME interview transcript, SOPs, job descriptions and supporting documents. Claude reads them and drafts a swimlane map of how the work is really done: steps, roles, who is responsible and accountable, decisions, approvals, timings, KPIs and constraints. Every step links to the exact passage it came from. The app checks the AI's work before you see it, and anything it can't find in your documents is thrown out and listed for you. You review every step, and nothing is published until you have.

## What you can do today
The app is being built in phases. At the moment (phase P0a, finished 2026-09-26) it installs and starts on your own computer:

1. Set it up once with **Setup.command** (Mac) or **setup.bat** (Windows). The window ends with "Setup complete. You can now start Process Map Studio." (Full steps: [README.md](README.md), "One-time setup".)
2. Start it with **Start.command** (Mac) or **start.bat** (Windows). A small window says "Process Map Studio is running at http://127.0.0.1:8000 — Close this window to stop it."
3. Your browser opens a simple page titled **Process Map Studio** that says the foundations are in place and that the look and feel and the Settings screen come next.
4. To stop the app, close the small window.

There is nothing to click on the page yet. The screens below are added in later phases.

| Screen | What it will do | Arrives in |
|---|---|---|
| Home (Engagements) | Your engagements, with a three-step first-run checklist | P0b, P1 |
| Settings | Your name, your Claude API key, model choice, connection test | P0b |
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
- 2026-09-26: Project foundations (phase P0a). The app can be installed and started with double-click files, backs up its database before any update, and a safety check stops your API key and your data folder from ever reaching GitHub.

## Glossary
- **Engagement:** one process you are mapping, with its documents and map versions.
- **SME:** subject-matter expert; the person interviewed about how the work is done.
- **Swimlane map:** a process map with one horizontal lane per role.
- **Provenance (O / I / R):** where a step came from: observed in a source, inferred from a source, or recommended from external practice (added only by you).
- **API key:** the password-like code that lets the app use Claude on your Anthropic account. It stays on your computer.
- **Fixture:** illustrative sample data used to test the app. It is not real SATS data.
