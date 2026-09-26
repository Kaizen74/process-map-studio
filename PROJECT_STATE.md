# Project State
*Last updated: 2026-09-26 (session 3) — update after EVERY increment*

## What this project is
Process Map Studio is a local app for Eric (non-technical owner) that turns SME interview transcripts and process documents into an evidence-traceable current-state swimlane map. Claude drafts the map from the documents, every AI claim is checked against the sources before it can appear, and Eric reviews and publishes. The full specification is PRD_ProcessMapStudio.md (v1.5).

## Current status
Phase P0b is complete and merged into `main` by Eric (pull request #2). Phase P1 (engagements and documents) in progress.

## This session (2026-09-26, session 3) — goal: Phase P1 (engagements and documents); likely continues next session
- [ ] Increment 1 — IN PROGRESS: database foundation: SQLAlchemy 2 + Alembic (verify versions and licences), `app/db.py`, Appendix B enums in `domain/enums.py`, migration 0001 with every §3.5 table, `app/manage.py` reports real pending migrations and upgrades; tests (all tables created, downgrade removes only its own tables, Start backs up before an update)
- [ ] Increment 2 — engagements backend (contract first): repositories, engagement and scope-card actions (incl. industry, adjacent industries, confidential terms), roles and lane order, DELETE removes files; list summary fields; audit rows for model changes
- [ ] Increment 3 — document parsing service: `parsing.parse_docx` (paragraphs, headings as sections, anchors), `parse_pdf_text` (text per page, anchors, short pages flagged for OCR in P3), `extract_pdf_images` (suggestions with page numbers); A.2–A.4 fixture documents; parser anchor tests
- [ ] Increment 4 — sources backend (contract first): upload (multipart) into `data/sources/`, registry (list, patch metadata, delete), parse on upload, suggested images stored in `data/images/`, GET segments with anchors
- [ ] Increment 5 — readiness endpoint and guided-nav status logic (done / attention / not started, next step, plain "missing" list)
- [ ] Increment 6 — UI: Home engagement cards and New engagement (creates it and opens Setup)
- [ ] Increment 7 — UI: Setup screen (process scope card with chips, roles and lanes with lane order, mini lane preview) and the guided engagement nav in the top bar
- [ ] Increment 8 — UI: Sources screen (drop zone, registry table with kind select and status chips, full-width source viewer)
- [ ] Increment 9 — browser checks (axe on the new screens, smoke path extended), GUIDE/README, close P1 (tag phase-p1, push, report card)

## Done (all sessions)
- 2026-09-26 Safety net: a secret check and pre-commit hook block API keys, the .env file and the data folder from git; README check; CLAUDE.md, state files and README created; run_checks.sh (5 checks)
- 2026-09-26 Backend skeleton: the layered folders from PRD §3.3, the shared Ok/Err result type, a health endpoint (router → action), the standard error shape, serving the built frontend, and the architecture test (7 checks, 59 tests)
- 2026-09-26 Frontend placeholder: React 18 + TypeScript strict + Vite page served by the backend; eslint with the components import rule (tested), tsc, vitest; licence test covers frontend packages (11 checks)
- 2026-09-26 Launchers: Setup.command/setup.bat and Start.command/start.bat call scripts/setup.py and start.py (standard library only); Start backs up the database before any update, starts one server on 127.0.0.1:8000, opens the browser and stops cleanly; scripts/dev.py for developers; run_checks.bat (11 checks, 99 backend tests)
- 2026-09-26 Design system: tokens JSON → generated tokens.css, self-hosted IBM Plex fonts, token-based base styles; token-sync, no-raw-colour, contrast and font tests (12 checks)
- 2026-09-26 Common components: Button, Chip, Card, SegmentedControl, Skeleton, EmptyState, ErrorState (Copy details), StateGlyph, Dialog, Popover with focus trapping; component tests and axe (60 frontend tests)
- 2026-09-26 Settings storage: GET /api/settings, PUT /api/settings/profile and /key; the key is saved only to the private .env (owner-only file), never returned or logged (only its last 4 characters); request IDs on every response (148 backend tests)
- 2026-09-26 Test connection: ai_service Models API calls (anthropic 1.8.0, verified), mock fixtures, POST /api/settings/test-connection, GET /api/settings/models, PUT /api/settings/model (185 backend tests, 97% coverage on services and actions)
- 2026-09-26 App shell and Home: TanStack Query + React Router, typed request wrapper with Copy details, top bar, guided engagement nav component, toasts, Home with the first-run checklist, not-found page (77 frontend tests)
- 2026-09-26 Settings screen: your name, Claude connection (masked key, Save, Test connection results), model/effort/verifier, about; shared form fields and validation (103 frontend tests)
- 2026-09-26 Browser checks: Playwright + axe (WCAG 2.1 AA, incl. real colour contrast) on Home, Settings and not-found, fonts load locally, no external requests, first-run smoke path (13 checks; 7 browser tests)
- 2026-09-26 Phase P0b closed: README first-start step now matches the app; GUIDE explains Home and Settings step by step

## Not started yet
- P1 engagements and documents · P2 transcripts, speakers, redaction · P3 AI service and grounded extraction · P4 canonicalise, calibrate, verify, assemble · P5 layout and map view · P6 review workbench · P7 quality card, publish, exports · P8 images · P9 matrix, registers, cause library · P10 gap analysis · P11 leadership view · P12 live run, polish and handover

## How to resume (write this as if for a stranger)
1. The next task is: the IN PROGRESS increment above. Phase P1 (PRD §6.3): migration 0001 creating all §3.5 tables (Alembic; `app/manage.py` then reports real pending migrations so Start backs up before updating), repositories, engagement and scope-card actions, readiness endpoint, `parsing` for DOCX and PDF text with anchors, PDF image suggestions; UI: Engagements home cards, Setup screen, Sources screen (drop zone, registry, full-width source viewer), guided nav status (the `EngagementNav` component already exists). Also in P1: audit rows for model changes (logged only, for now) and the AI usage card once `ai_calls` exists. Break it into ~30-minute increments here before starting; P1 will likely need two sessions.
2. The relevant files are: CLAUDE.md, PRD_ProcessMapStudio.md §3.3, §3.5, §4 (Engagements, Sources, Readiness), §5.4 (Home, Setup, Sources), §6.3; `backend/app/manage.py`, `backend/app/db.py`, `frontend/src/features/home/`, `frontend/src/components/shell/EngagementNav.tsx`, API_CONTRACT.md (add endpoints first).
3. Watch out for: the GitHub repository was public at kickoff; Eric made it private on 2026-09-26 (confirmed via the GitHub API). Never push if it is public again. This cloud session pushes to branch `claude/charming-davinci-sck1cq`, not `main` (see DECISIONS.md).
4. Process trap (2026-09-26): never chain `./run_checks.sh | tail … && git commit`; the pipe hides the failure code. Run the checks alone, confirm exit code 0, then commit. Fake keys in tests must be built by concatenation (the secret check blocks key-shaped literals).
5. Before using the anthropic SDK or Models API in P0b, check the installed version and the current docs and log it in DECISIONS.md (PRD §3.4). New packages: check licences (the licence test will also catch GPL) and peer ranges; TypeScript must stay below 6.1 while typescript-eslint 8.70 is used.
6. Run `./run_checks.sh` first — all 13 lines should say PASS. If `.venv` or `frontend/node_modules` is missing (fresh cloud container), run `python3.12 scripts/setup.py --dev` first.

## Known issues
- The `phase-p0b` tag was never pushed (cloud sessions can't push tags); P0b's last commit is `0c2c0e5`, merged into `main` in pull request #2.
- Model changes are written to the app log, not yet to an audit table (arrives with the database in P1).
- The `phase-p0a` tag was never pushed (cloud sessions can't push tags); P0a's last commit is `b78f2d1`, merged into `main` in pull request #1.
- Work is pushed to branch `claude/charming-davinci-sck1cq`; Eric merges it into `main` with a pull request (P0a: #1, P0b: #2).
- The Windows launchers (`setup.bat`, `start.bat`, `run_checks.bat`) and the macOS `.command` files have been checked for content and line endings by tests, but not yet run on a real Windows PC or Mac; the P12 clean-clone rehearsal covers this, and Eric's first double-click is the earlier real test.
