# Project State
*Last updated: 2026-09-26 — update after EVERY increment*

## What this project is
Process Map Studio is a local app for Eric (non-technical owner) that turns SME interview transcripts and process documents into an evidence-traceable current-state swimlane map. Claude drafts the map from the documents, every AI claim is checked against the sources before it can appear, and Eric reviews and publishes. The full specification is PRD_ProcessMapStudio.md (v1.5).

## Current status
Phase P0a (foundations) is complete and tagged `phase-p0a`: the app installs, starts and shows a placeholder page, and nothing secret can reach GitHub. Next: phase P0b.

## This session (2026-09-26) — goal: Phase P0a, then stop and report
- [x] Increment 1 — safety net and memory files (.gitignore, .env.example, scripts/check_secrets.py, .githooks/pre-commit, scripts/check_readme.py, CLAUDE.md, state files, README.md, first run_checks.sh, tests)
- [x] Increment 2 — backend skeleton: §3.3 folders with empty layers, domain/result.py, config, FastAPI app with /api/health (router → action), architecture test, ruff/mypy/pytest set-up
- [x] Increment 3 — frontend placeholder: React 18 + TypeScript strict + Vite, eslint (with the components/ import restriction), tsc, vitest
- [x] Increment 4 — launchers: scripts/setup.py, start.py, dev.py (standard library only), Setup.command, Start.command, setup.bat, start.bat, run_checks.bat; tests (stdlib-only, database backup, start serves the placeholder page)
- [x] Increment 5 — close P0a: GUIDE.md and README.md current, tag phase-p0a, push, report card

## Done (all sessions)
- 2026-09-26 Safety net: a secret check and pre-commit hook block API keys, the .env file and the data folder from git; README check; CLAUDE.md, state files and README created; run_checks.sh (5 checks)
- 2026-09-26 Backend skeleton: the layered folders from PRD §3.3, the shared Ok/Err result type, a health endpoint (router → action), the standard error shape, serving the built frontend, and the architecture test (7 checks, 59 tests)
- 2026-09-26 Frontend placeholder: React 18 + TypeScript strict + Vite page served by the backend; eslint with the components import rule (tested), tsc, vitest; licence test covers frontend packages (11 checks)
- 2026-09-26 Launchers: Setup.command/setup.bat and Start.command/start.bat call scripts/setup.py and start.py (standard library only); Start backs up the database before any update, starts one server on 127.0.0.1:8000, opens the browser and stops cleanly; scripts/dev.py for developers; run_checks.bat (11 checks, 99 backend tests)

## Not started yet
- P0b design system, shell, Settings (next session)
- P1 engagements and documents · P2 transcripts, speakers, redaction · P3 AI service and grounded extraction · P4 canonicalise, calibrate, verify, assemble · P5 layout and map view · P6 review workbench · P7 quality card, publish, exports · P8 images · P9 matrix, registers, cause library · P10 gap analysis · P11 leadership view · P12 live run, polish and handover

## How to resume (write this as if for a stranger)
1. The next task is: Phase P0b (PRD §6.3): design system first (PRD §5.2: `shared/design_tokens.json`, `frontend/scripts/generate-tokens.mjs` → `src/styles/tokens.css`, token-sync and no-raw-colour tests, self-hosted IBM Plex Sans/Mono woff2 in `frontend/public/fonts/`), then common components (§5.11), app shell, toast and error patterns, Settings screen with `services/settings_store.py` (your name, masked key, model, Test connection mocked), Home with the first-run checklist; axe on Settings and Home. Break it into ~30-minute increments here before starting.
2. The relevant files are: CLAUDE.md, PRD_ProcessMapStudio.md §3.4, §5.2–5.4, §5.10–5.11, §6.3; `frontend/src/App.tsx` (placeholder to replace); `backend/app/main.py`; API_CONTRACT.md (add the Settings endpoints first).
3. Watch out for: the GitHub repository was public at kickoff; Eric made it private on 2026-09-26 (confirmed via the GitHub API). Never push if it is public again. This cloud session pushes to branch `claude/charming-davinci-sck1cq`, not `main` (see DECISIONS.md).
4. Before using the anthropic SDK or Models API in P0b, check the installed version and the current docs and log it in DECISIONS.md (PRD §3.4). New packages: check licences (the licence test will also catch GPL) and peer ranges; TypeScript must stay below 6.1 while typescript-eslint 8.70 is used.
5. Run `./run_checks.sh` first — all 11 lines should say PASS. If `.venv` or `frontend/node_modules` is missing (fresh cloud container), run `python3.12 scripts/setup.py --dev` first.

## Known issues
- Work is pushed to branch `claude/charming-davinci-sck1cq`; `main` on GitHub still has only the PRD until Eric merges it (see DECISIONS.md).
- The Windows launchers (`setup.bat`, `start.bat`, `run_checks.bat`) and the macOS `.command` files have been checked for content and line endings by tests, but not yet run on a real Windows PC or Mac; the P12 clean-clone rehearsal covers this, and Eric's first double-click is the earlier real test.
