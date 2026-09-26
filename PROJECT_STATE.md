# Project State
*Last updated: 2026-09-26 (session 2) — update after EVERY increment*

## What this project is
Process Map Studio is a local app for Eric (non-technical owner) that turns SME interview transcripts and process documents into an evidence-traceable current-state swimlane map. Claude drafts the map from the documents, every AI claim is checked against the sources before it can appear, and Eric reviews and publishes. The full specification is PRD_ProcessMapStudio.md (v1.5).

## Current status
Phase P0a is complete and merged into `main` by Eric (pull request #1). Phase P0b (design system, shell, Settings) in progress.

## This session (2026-09-26, session 2) — goal: Phase P0b (design system, shell, Settings), then stop and report
- [x] Increment 1 — design tokens (`shared/design_tokens.json` → `frontend/scripts/generate-tokens.mjs` → `src/styles/tokens.css`), self-hosted IBM Plex Sans/Mono, base styles; token-sync, no-raw-colour and contrast tests
- [x] Increment 2 — common components (§5.11): Button, Chip, Card, SegmentedControl, Skeleton, EmptyState, ErrorState, StateGlyph, Dialog, Popover; component tests
- [x] Increment 3 — Settings backend part 1 (contract first): `services/settings_store.py` (read_env, write_env_key, mask_key), settings actions and router (GET /settings, PUT /settings/profile, PUT /settings/key), request IDs; tests that the key is never unmasked in any response or log
- [x] Increment 4 — Settings backend part 2: `services/ai_service.py` Models API (list_models, get_model; mock mode) after verifying the anthropic SDK; POST /settings/test-connection, PUT /settings/model, GET /settings/models; tests for every test-connection path
- [x] Increment 5 — app shell and Home: TanStack Query, routing, `src/api/request.ts`, hooks, TopBar, EngagementNav, Toast, error pattern; Home with the first-run checklist
- [ ] Increment 6 — IN PROGRESS: Settings screen: your name, Claude connection (masked key, Save, Test connection), model, about
- [ ] Increment 7 — browser checks: Playwright + axe-core on Home and Settings (0 serious/critical), a Settings smoke path; added to run_checks.sh
- [ ] Increment 8 — close P0b: README (step 5 now works), GUIDE.md, state files, tag phase-p0b, push, report card

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

## Not started yet
- P1 engagements and documents · P2 transcripts, speakers, redaction · P3 AI service and grounded extraction · P4 canonicalise, calibrate, verify, assemble · P5 layout and map view · P6 review workbench · P7 quality card, publish, exports · P8 images · P9 matrix, registers, cause library · P10 gap analysis · P11 leadership view · P12 live run, polish and handover

## How to resume (write this as if for a stranger)
1. The next task is: the IN PROGRESS increment above. Phase P0b (PRD §6.3): design system first (PRD §5.2: `shared/design_tokens.json`, `frontend/scripts/generate-tokens.mjs` → `src/styles/tokens.css`, token-sync and no-raw-colour tests, self-hosted IBM Plex Sans/Mono woff2 in `frontend/public/fonts/`), then common components (§5.11), app shell, toast and error patterns, Settings screen with `services/settings_store.py` (your name, masked key, model, Test connection mocked), Home with the first-run checklist; axe on Settings and Home. Break it into ~30-minute increments here before starting.
2. The relevant files are: CLAUDE.md, PRD_ProcessMapStudio.md §3.4, §5.2–5.4, §5.10–5.11, §6.3; `frontend/src/App.tsx` (placeholder to replace); `backend/app/main.py`; API_CONTRACT.md (add the Settings endpoints first).
3. Watch out for: the GitHub repository was public at kickoff; Eric made it private on 2026-09-26 (confirmed via the GitHub API). Never push if it is public again. This cloud session pushes to branch `claude/charming-davinci-sck1cq`, not `main` (see DECISIONS.md).
4. Process trap (2026-09-26): never chain `./run_checks.sh | tail … && git commit`; the pipe hides the failure code. Run the checks alone, confirm exit code 0, then commit. Fake keys in tests must be built by concatenation (the secret check blocks key-shaped literals).
5. Before using the anthropic SDK or Models API in P0b, check the installed version and the current docs and log it in DECISIONS.md (PRD §3.4). New packages: check licences (the licence test will also catch GPL) and peer ranges; TypeScript must stay below 6.1 while typescript-eslint 8.70 is used.
6. Run `./run_checks.sh` first — all 12 lines should say PASS. If `.venv` or `frontend/node_modules` is missing (fresh cloud container), run `python3.12 scripts/setup.py --dev` first.

## Known issues
- The `phase-p0a` tag could not be pushed from the cloud session (tag pushes refused; branch pushes work). The phase's last commit is `b78f2d1` on branch `claude/charming-davinci-sck1cq`. Eric can add the tag on github.com (see DECISIONS.md). Future phase tags will need the same.
- Work is pushed to branch `claude/charming-davinci-sck1cq`; Eric merges it into `main` with a pull request (P0a merged as pull request #1).
- The Windows launchers (`setup.bat`, `start.bat`, `run_checks.bat`) and the macOS `.command` files have been checked for content and line endings by tests, but not yet run on a real Windows PC or Mac; the P12 clean-clone rehearsal covers this, and Eric's first double-click is the earlier real test.
