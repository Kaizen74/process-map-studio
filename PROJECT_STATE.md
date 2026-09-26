# Project State
*Last updated: 2026-09-26 — update after EVERY increment*

## What this project is
Process Map Studio is a local app for Eric (non-technical owner) that turns SME interview transcripts and process documents into an evidence-traceable current-state swimlane map. Claude drafts the map from the documents, every AI claim is checked against the sources before it can appear, and Eric reviews and publishes. The full specification is PRD_ProcessMapStudio.md (v1.5).

## Current status
Phase P0a (foundations) in progress: safety net, memory files and backend skeleton done; building the frontend placeholder next.

## This session (2026-09-26) — goal: Phase P0a, then stop and report
- [x] Increment 1 — safety net and memory files (.gitignore, .env.example, scripts/check_secrets.py, .githooks/pre-commit, scripts/check_readme.py, CLAUDE.md, state files, README.md, first run_checks.sh, tests)
- [x] Increment 2 — backend skeleton: §3.3 folders with empty layers, domain/result.py, config, FastAPI app with /api/health (router → action), architecture test, ruff/mypy/pytest set-up
- [ ] Increment 3 — IN PROGRESS: frontend placeholder: React 18 + TypeScript strict + Vite, eslint (with the components/ import restriction), tsc, vitest
- [ ] Increment 4 — launchers: scripts/setup.py, start.py, dev.py (standard library only), Setup.command, Start.command, setup.bat, start.bat, run_checks.bat; tests (stdlib-only, database backup, start serves the placeholder page)
- [ ] Increment 5 — close P0a: GUIDE.md and README.md current, tag phase-p0a, push, report card

## Done (all sessions)
- 2026-09-26 Safety net: a secret check and pre-commit hook block API keys, the .env file and the data folder from git; README check; CLAUDE.md, state files and README created; run_checks.sh (5 checks)
- 2026-09-26 Backend skeleton: the layered folders from PRD §3.3, the shared Ok/Err result type, a health endpoint (router → action), the standard error shape, serving the built frontend, and the architecture test (7 checks, 59 tests)

## Not started yet
- P0b design system, shell, Settings · P1 engagements and documents · P2 transcripts, speakers, redaction · P3 AI service and grounded extraction · P4 canonicalise, calibrate, verify, assemble · P5 layout and map view · P6 review workbench · P7 quality card, publish, exports · P8 images · P9 matrix, registers, cause library · P10 gap analysis · P11 leadership view · P12 live run, polish and handover

## How to resume (write this as if for a stranger)
1. The next task is: Increment 3 (frontend placeholder in frontend/), see list above.
2. The relevant files are: CLAUDE.md, PRD_ProcessMapStudio.md §3.2, §3.3, §3.10, §6.1–6.3, Appendix C and D.
3. Watch out for: the GitHub repository was public at kickoff; Eric made it private on 2026-09-26 (confirmed via the GitHub API). Never push if it is public again. This cloud session pushes to branch `claude/charming-davinci-sck1cq`, not `main` (see DECISIONS.md).
4. Run `./run_checks.sh` first — all lines should say PASS.

## Known issues
- None.
