# Process Map Studio 1.0.0: release notes

*Released 2026-09-29. The first complete version.*

## What the app does
Process Map Studio turns the documents behind one process (SME interview transcripts, SOPs, manuals and job descriptions) into a current-state swimlane map you can trust. Claude drafts the map, and every claim it makes is checked against your own documents before you see it. Anything it can't back with a passage is thrown out and listed. You review every step, and nothing is published until you have. Everything runs on your own computer; only the text of your documents goes to Claude to draft the map.

## How to install
Follow [README.md](../README.md), "One-time setup", click by click (about 30 minutes). You need Python 3.12, Node.js LTS, GitHub Desktop and a Claude API key. To start: double-click **Start.command** (Mac) or **start.bat** (Windows). To use the app, see [GUIDE.md](../GUIDE.md).

## What's in 1.0.0
- **Engagements:** one per process, with its scope, roles and lanes.
- **Sources:** Word, PDF, text and subtitle files are read into passages with anchors (§3.1, p. 5, 06:40). Interviews are split by speaker, each speaker is mapped to a role, and a list of names keeps people's names out of view everywhere except three owner-only places.
- **Draft map:** Claude extracts steps from each source, and each claim's passage, quote, numbers and roles are checked. Sources are compared (agree, differ, contradict or silent), an independent verifier checks every step a second time, and the map is built with responsibilities, times, constraints and questions for your SME.
- **Review:** the swimlane map or a table, with evidence opened at the exact passage. Confirm, edit, reject or add steps; steps you have reviewed are never overwritten by a redraft.
- **Publish and exports:** a quality card must be green first. Published versions are read-only. You can download the Master Process Map (Markdown), the map as data (JSON), a RACI spreadsheet (CSV) and a single-file interactive map (HTML). Exports use role names only and contain no images or quotes.
- **Pictures on steps** (inside the app only, with hidden camera and location details removed).
- **Matrix, Registers and the cause library:** where sources agree and differ, knowledge risks, AI flags, constraints and questions.
- **Gap analysis (optional):** documents compared with practice, and (if you switch on web research and approve a generic brief) your map compared with published practice. It is advisory and never changes the map by itself.
- **Leadership view:** facts, interpretation and recommendation for a published map, with every figure opening the steps behind it.

## How it was checked
- 13 automated checks run after every change, and all pass. They cover code quality, the design system, accessibility on every screen, a privacy scan for hidden names, the golden baselines G1 to G7, the approved Review screenshots, a browser run through the whole journey, and a secret check that keeps your key and data out of GitHub.
- **Clean install rehearsal:** a fresh copy of the app was set up and started exactly as the README says, and the sample engagement was drafted. It passed after three small fixes, recorded in DECISIONS.md.
- **Live evaluation with the real Claude model:** the harness is ready. It runs when you ask, with your key; its results are recorded in DECISIONS.md.

## Known limits
- The Windows launchers and the macOS prompts have been checked by tests and by the rehearsal on Linux, but not yet on a real Windows PC or Mac. Your first double-click is the real test, and the README's "If something goes wrong" table covers the known prompts.
- The sample engagement in the app's tests is illustrative, not real data.
- One user on one computer; no sign-in, no sharing, no cloud storage (by design).
