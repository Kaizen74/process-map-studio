# Project State
*Last updated: 2026-09-26 (session 4) — update after EVERY increment*

## What this project is
Process Map Studio is a local app for Eric (non-technical owner) that turns SME interview transcripts and process documents into an evidence-traceable current-state swimlane map. Claude drafts the map from the documents, every AI claim is checked against the sources before it can appear, and Eric reviews and publishes. The full specification is PRD_ProcessMapStudio.md (v1.5).

## Current status
Phase P1 is complete and merged into `main` (pull request #3). Phase P2 (transcripts, speakers, redaction) in progress.

## This session (2026-09-26, session 4) — goal: Phase P2 (transcripts, speakers, redaction)
P1 was merged into `main` by Eric (pull request #3); the working branch was restarted from `main`.
- [x] Increment 1 — transcript parsing and grounding basics: `parsing.parse_transcript_text` (`Speaker:` and `[mm:ss] Speaker:`), `parse_vtt`, `parse_srt`, `detect_speakers` (Word and PDF transcripts), `looks_like_name`; `grounding.detect_instruction_like`, `redact_text`, `scan_redaction_terms`; A.1 transcript fixture plus VTT, SRT, Word and PDF versions; tests (speakers and timestamps per format, A.3 §9 flagged)
- [x] Increment 2 — jobs worker (contract first): migration 0002 (`source_segments.is_interviewer`), in-process worker thread, `GET /api/jobs/{id}`, uploads read as a job (all formats; instruction-like flag; name-like speaker labels become redaction terms), restart recovery and reading of P1 transcripts left pending
- [ ] Increment 3 — IN PROGRESS: speakers, redaction terms, corrections (contract first): `GET/PUT /api/sources/{sid}/speakers`, `GET/POST /api/engagements/{id}/redaction-terms`, `DELETE /api/redaction-terms/{tid}`, `PATCH /api/segments/{segid}`, `?raw=1`; names replaced in every other response (segments, sources, readiness); readiness ignores Interviewer
- [ ] Increment 4 — UI: "Reading…" status with automatic refresh; speaker-mapping card; redaction list (owner-only places)
- [ ] Increment 5 — UI: correction editor; "Instruction-like text" tag; speaker roles in the viewer
- [ ] Increment 6 — browser checks (privacy scan of rendered pages, smoke path with the transcript and speaker mapping, axe), latency for new endpoints, GUIDE/README, close P2 (tag phase-p2, report card)

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
- 2026-09-26 Database foundation: SQLAlchemy + Alembic, migration 0001 with all 27 PRD tables, Appendix B enums, Start backs up an older database before updating it (tested end to end), tests can never touch the real data folder
- 2026-09-26 Engagements backend: create/list/get/edit/delete engagements (delete removes files), scope card with confidential terms, roles and lane order, audit rows (incl. model changes)
- 2026-09-26 Document parsing: Word and PDF split into anchored passages (§3.2, p. 5), scanned pages flagged for OCR, PDF images found as suggestions; PRD sample documents as fixtures
- 2026-09-26 Sources backend: upload Word/PDF/transcript files (up to 50 MB), read Word and PDF on upload, registry list/edit/delete, paged passages with anchors, PDF images saved as suggestions
- 2026-09-26 Readiness: one endpoint tells each screen what is done, what needs attention (with a count), the next recommended step and exactly what the draft still needs
- 2026-09-26 Home: engagement cards (version, review progress, sources, last updated), New engagement opens Setup, Delete with a confirmation naming what goes; opening an engagement goes to its next step, with the guided path in the top bar
- 2026-09-26 Setup screen: process scope (with chips for roles, industries and confidential terms), roles and lanes (add, edit, system role, reorder by drag or Move up/down) and a lane preview
- 2026-09-26 Sources screen: drop zone and Choose files, registry table with editable kind, date, owner and controlled copy, status with reasons, delete with confirmation, full-width source viewer with anchors, and the "Before drafting" line
- 2026-09-26 Phase P1 closed: latency gate on every non-AI endpoint (p95 4–70 ms against a 200 ms budget), axe on Home cards, Setup and Sources, smoke path through a whole engagement, GUIDE and README updated
- 2026-09-26 Transcript reading: plain text, VTT, SRT, Word and PDF interviews become speaker turns with times (the PRD sample interview gives the same nine turns in every format); name-like speaker labels are recognised; names can be hidden (whole words, any case); instruction-like text such as the A.3 test line is flagged
- 2026-09-26 Background reading: uploads answer at once and a worker reads each file ("Reading…" on screen until done); transcripts in every format become speaker turns; name-like speaker labels become hidden names; unfinished work and P1 transcripts are read when the app starts; database update 0002

## Not started yet
- P2 transcripts, speakers, redaction · P3 AI service and grounded extraction · P4 canonicalise, calibrate, verify, assemble · P5 layout and map view · P6 review workbench · P7 quality card, publish, exports · P8 images · P9 matrix, registers, cause library · P10 gap analysis · P11 leadership view · P12 live run, polish and handover

## How to resume (write this as if for a stranger)
1. The next task is: the IN PROGRESS increment above. Phase P2 (PRD §6.3): `parsing` for TXT (`Speaker:` and `[mm:ss] Speaker:`), VTT, SRT, DOCX and PDF transcripts; speaker detection; `GET/PUT /sources/{sid}/speakers`; redaction terms (auto from name-like labels, manual); redacted text in all other responses; `grounding.detect_instruction_like`; the jobs worker. UI: speaker-mapping card, redaction list, correction editor, "instruction-like" tag. Break it into ~30-minute increments here before starting. Transcripts uploaded in P1 are stored with `text_status: "pending"`; P2 must read them (on upload and for files already stored).
2. The relevant files are: CLAUDE.md, PRD_ProcessMapStudio.md §3.7 (S0, speaker mapping), §3.8 G10, §4 (Sources, speakers), §5.4 Sources, Appendix A.1 (the transcript fixture), §6.3; `backend/app/services/parsing.py`, `backend/app/actions/sources.py`, `backend/app/actions/readiness.py`, `frontend/src/features/sources/`, API_CONTRACT.md (add endpoints first).
3. Watch out for: the GitHub repository was public at kickoff; Eric made it private on 2026-09-26 (confirmed via the GitHub API). Never push if it is public again. This cloud session pushes to branch `claude/charming-davinci-sck1cq`, not `main` (see DECISIONS.md).
4. Phase P2 must record "Interviewer" speaker mappings so readiness does not count them as unmapped (readiness counts speaker labels without a role).
5. Process trap (2026-09-26): never chain `./run_checks.sh | tail … && git commit`; the pipe hides the failure code. Run the checks alone, confirm exit code 0, then commit. Fake keys in tests must be built by concatenation (the secret check blocks key-shaped literals).
6. Before using the anthropic SDK or Models API in P0b, check the installed version and the current docs and log it in DECISIONS.md (PRD §3.4). New packages: check licences (the licence test will also catch GPL) and peer ranges; TypeScript must stay below 6.1 while typescript-eslint 8.70 is used.
7. Run `./run_checks.sh` first — all 13 lines should say PASS. If `.venv` or `frontend/node_modules` is missing (fresh cloud container), run `python3.12 scripts/setup.py --dev` first.

## Known issues
- The `phase-p1` tag was created locally but could not be pushed (cloud sessions can't push tags); P1's last commit is on branch `claude/charming-davinci-sck1cq`. Eric can create the tag on GitHub (Releases → Draft a new release → tag `phase-p1`) after merging.
- The `phase-p0b` tag was never pushed (cloud sessions can't push tags); P0b's last commit is `0c2c0e5`, merged into `main` in pull request #2.
- The `phase-p0a` tag was never pushed (cloud sessions can't push tags); P0a's last commit is `b78f2d1`, merged into `main` in pull request #1.
- Work is pushed to branch `claude/charming-davinci-sck1cq`; Eric merges it into `main` with a pull request (P0a: #1, P0b: #2).
- The Windows launchers (`setup.bat`, `start.bat`, `run_checks.bat`) and the macOS `.command` files have been checked for content and line endings by tests, but not yet run on a real Windows PC or Mac; the P12 clean-clone rehearsal covers this, and Eric's first double-click is the earlier real test.
