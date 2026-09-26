# API Contract
*Any change here requires updating BOTH backend and frontend in the SAME increment — never leave them misaligned at a checkpoint. Edit this file first (PRD §6.1 rule 12).*

Base path `/api`. JSON unless noted. The server binds to `127.0.0.1` only.

Standard error shape for every endpoint (PRD §4):
```json
{"error": {"code": "PUBLISH_BLOCKED", "message": "Plain-language explanation", "details": {}}}
```

Endpoints are added here as each phase builds them. The full planned list is PRD §4.

Every response carries an `X-Request-ID` header. Error bodies also include it as `details.request_id`, so the screen's **Copy details** can give "error code · request ID" for bug reports.

## System

### GET /api/health
Purpose: lets the launcher and tests confirm the app is running.
Request: none.
Response `200`:
```json
{"status": "ok", "app_version": "0.1.0", "prd_version": "1.5"}
```
Used by: `scripts/start.py` (waits for it before opening the browser). No screen uses it yet; the P0a placeholder page is static.

### Unknown `/api/...` path
Response `404` in the standard error shape with code `NOT_FOUND`.

## Static files (not part of `/api`)
`GET /` and any other non-API path serve the built frontend (`frontend/dist/index.html` and its assets). If the frontend has not been built yet, `GET /` returns a plain page saying "Run Setup first".

## Settings (PRD §3.4, §5.4) — phase P0b

Settings are stored in the private `.env` file in the app folder (never in the database or git) through `services/settings_store.py`, and take effect without restarting. For each setting, a non-empty value in `.env` wins, then the computer's environment variable, then the default in PRD §3.4. The API key is **never** returned: responses carry only `key_set` and `key_last4`.

### Settings object (returned by every Settings endpoint below)
```json
{"owner_name": "Owner", "model": "claude-opus-5-5", "effort": "high",
 "verifier_enabled": true, "web_research_enabled": false,
 "key_set": true, "key_last4": "x9Q2"}
```
`key_last4` is `""` when no key is set.

### GET /api/settings
Request: none. Response `200`: the settings object.
Errors: `500 IO` if the `.env` file can't be read.
Used by: Settings screen (`features/settings`), Home first-run checklist (`features/home`), via `hooks/useSettings`.

### PUT /api/settings/profile
Request: `{"owner_name": "Eric Yim"}` — 1 to 80 characters after trimming, no line breaks.
Response `200`: the settings object.
Errors: `422 VALIDATION` with a plain message (e.g. "Please enter your name (up to 80 characters)."); `500 IO` if `.env` can't be written.
Used by: Settings screen, "Your name" card.

### PUT /api/settings/key
Request: `{"anthropic_api_key": "sk-ant-..."}` — trimmed; must start with `sk-ant-`, no spaces or line breaks, 20 to 300 characters.
Response `200`: the settings object (masked: `key_set: true`, `key_last4`).
Errors: `422 VALIDATION` ("That doesn't look like a Claude API key. Keys start with sk-ant-. Copy it again from the Claude Console."); `500 IO`. Error bodies never echo the key.
Used by: Settings screen, "Claude connection" card.

### POST /api/settings/test-connection
Checks the saved key and the configured model with Anthropic's Models API (`GET /v1/models/{model}`; one retry on rate limits, never on a rejected key). Mocked in tests (`MOCK_CLAUDE=1`).
Request: none.
Response `200`:
```json
{"key_valid": true, "model_available": true,
 "capabilities": {"pdf_input": true, "structured_outputs": true},
 "message": "Connected. Your key works and claude-opus-5-5 is available."}
```
Outcomes, all `200` with a plain `message`: no key saved (`key_valid: false`, "Add your Claude API key first…"); key rejected (`key_valid: false`, "Your API key was rejected. Copy it again from the Claude Console and paste it here."); model not available (`key_valid: true, model_available: false`).
Errors: `503 AI_RATE_LIMIT` (Anthropic busy: "try again in a minute"); `500 IO` (Anthropic couldn't be reached: check the internet connection).
Used by: Settings screen, "Claude connection" card (Test connection).

### GET /api/settings/models
Lists the models available to the saved key, for the Model dropdown.
Response `200`:
```json
{"models": [{"id": "claude-opus-5-5", "display_name": "Claude Opus 5.5",
             "effort_levels": ["low", "medium", "high", "xhigh", "max"]}],
 "from_anthropic": true, "message": ""}
```
Without a key (or if the key is rejected) it returns only the configured model with `from_anthropic: false` and a message such as "Add your Claude API key to see every model available to you." `effort_levels` lists the levels the model reports as supported (from its `capabilities.effort`).
Errors: `503 AI_RATE_LIMIT`, `500 IO` as above.
Used by: Settings screen, "Model" card.

### PUT /api/settings/model
Request: `{"model": "claude-opus-5-5", "effort": "high", "verifier_enabled": true}` — `model` is a model ID (lower-case letters, digits, dots and dashes); `effort` one of `low`, `medium`, `high`, `xhigh`, `max`.
Response `200`: the settings object.
Errors: `422 VALIDATION`; `500 IO`. (The change is written to the app log now and to the audit log once the database arrives in phase P1.)
Used by: Settings screen, "Model" card.

## Engagements and roles (PRD §4, §5.4 Setup) — phase P1

An engagement is one process being mapped. Deleting it removes all its rows **and its files** (`data/sources/<id>/`, `data/images/<id>/`). Every change writes an audit row (actor = the owner name from Settings).

### Engagement object
```json
{"id": "…", "name": "Load control", "process_name": "Aircraft load control",
 "trigger": "Flight scheduled", "end_point": "Final load sheet issued",
 "in_scope_roles": ["Load controller", "Ramp"], "out_of_scope": "Fuelling",
 "process_kpi": "Load sheet issued by T-10", "industry": "Aviation ground handling",
 "adjacent_industries": ["Air cargo"], "confidential_terms": ["Acme Ground Services"],
 "status": "active", "created_at": "2026-09-26T09:00:00+00:00", "updated_at": "…"}
```
Rules: `name` 1–120 characters (required). Text fields up to 2,000 characters. List fields (`in_scope_roles`, `adjacent_industries`, `confidential_terms`): up to 50 items, each 1–120 characters, duplicates (ignoring case) removed, no line breaks. `confidential_terms` are company, client, site and system names that must never be sent to web research (PRD §3.11); they are **not** redacted from the app or internal exports.

### POST /api/engagements
Request: `{"name": "…"}` plus any scope fields. Response `201`: the engagement object.
Errors: `422 VALIDATION` with `details.field`.
Used by: Home (New engagement).

### GET /api/engagements
Response `200`: list, newest first, of the engagement object plus
`{"latest_version": null | {"label": "v0.1", "state": "draft"}, "review_progress": {"reviewed": 0, "total": 0}, "sources_count": 0}`.
Used by: Home engagement cards.

### GET /api/engagements/{id} · PATCH /api/engagements/{id} · DELETE /api/engagements/{id}
GET → `200` engagement object. PATCH → any scope fields (same rules) → `200` engagement object. DELETE → `204`, removes rows and files.
Errors: `404 NOT_FOUND` ("That engagement doesn't exist. It may have been deleted."); `422 VALIDATION`.
Used by: Setup screen (scope card), Home (delete, from P1 UI), top bar (engagement name).

### Role object
```json
{"id": "…", "engagement_id": "…", "name": "Load controller", "aliases": ["LC"],
 "is_system": false, "lane_order": 1}
```

### GET /api/engagements/{id}/roles
Response `200`: roles in lane order (1 = top lane). Used by: Setup screen (Roles and lanes).

### POST /api/engagements/{id}/roles
Request: `{"name": "…", "aliases": [], "is_system": false}` — name 1–80 characters, unique in the engagement (ignoring case). The new role goes to the bottom lane.
Response `201`: role. Errors: `404`, `409 CONFLICT` ("There is already a role called …"), `422`.

### PATCH /api/roles/{rid}
Request: any of `{"name", "aliases", "is_system", "lane_order"}`. Setting `lane_order` to *n* moves the role to lane *n* and renumbers the others (1…N, no gaps).
Response `200`: role. Errors: `404`, `409`, `422`.
Used by: Setup screen (rename, aliases, system toggle, reorder).

### PUT /api/settings/model (change)
Now also writes an audit row (`target_type: "settings"`, before/after model, effort, verifier).

## Sources (PRD §4, §5.4 Sources) — phase P1

Files are stored as `data/sources/<engagement_id>/<source_id>.<ext>` (the original file name is kept for display only). Accepted formats: `.docx`, `.pdf`, `.txt`, `.vtt`, `.srt`, up to 50 MB. In phase P1, Word and PDF files are read on upload; `.txt`, `.vtt` and `.srt` are stored with `text_status: "pending"` and read from phase P2 (transcripts). Images inside PDFs (at least 48 px) are saved to `data/images/<engagement_id>/` as **suggestions** (`status: "suggested"`, page number kept); nothing is shown on a map until Eric keeps them (P8).

### Source object
```json
{"id": "…", "engagement_id": "…", "kind": "sop", "filename": "sop_LC-07.docx",
 "format": "docx", "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
 "version_date": "2026-03-01", "owner": "Load Control", "controlled_copy": true,
 "text_status": "ready", "error": "", "segment_count": 10, "ocr_pages": [],
 "suggested_images": 0, "created_at": "…"}
```
`kind` is one of PRD B.1 (`interview_transcript`, `sop`, `manual`, `job_description`, `executed_artefact`, `other`). `text_status`: `pending` (waiting to be read) · `ready` · `failed` (with a plain `error`). `ocr_pages` lists PDF pages with almost no text, which will be read by OCR from phase P3.

### POST /api/engagements/{id}/sources (multipart form)
Fields: `file` (required); `kind` (optional: guessed from the file name if missing: `.vtt`/`.srt`/names with "transcript" or "interview" → `interview_transcript`, "sop" → `sop`, "jd"/"job description" → `job_description`, "manual" → `manual`, else `other`); `version_date` (optional, `YYYY-MM-DD`); `owner` (optional, up to 120 characters); `controlled_copy` (optional, `true`/`false`).
Response `201`: source object (already read, for Word and PDF).
Errors: `404` engagement; `422 VALIDATION` ("Process Map Studio reads .docx, .pdf, .txt, .vtt and .srt files." · "That file is larger than 50 MB." · "The file is empty." · bad kind or date). A file that can't be read is still saved with `text_status: "failed"` and a plain `error`, so Eric can see it and delete or replace it.
Used by: Sources screen (drop zone).

### GET /api/engagements/{id}/sources
Response `200`: source objects, oldest first. Errors: `404`. Used by: Sources screen (registry), readiness.

### GET /api/sources/{sid} · PATCH /api/sources/{sid} · DELETE /api/sources/{sid}
GET → source object. PATCH → any of `kind`, `version_date`, `owner`, `controlled_copy` → source object. DELETE → `204`; removes the file, its passages and its suggested images.
Errors: `404` ("That source doesn't exist. It may have been deleted."); `422`.
Used by: Sources screen (registry row edits, delete, viewer header).

### GET /api/sources/{sid}/segments
Query: `page` (1-based, default 1), `page_size` (default 200, max 500), `uncited_only` (from P9; ignored until then), `raw` (P2; ignored until then).
Response `200`:
```json
{"segments": [{"id": "…", "seq": 3, "anchor": "§3.1", "page": null, "section": "3 Load planning",
               "speaker_role": null, "text": "§3.1 The Load Controller shall …",
               "cited": false, "instruction_like": false}],
 "total": 10, "page": 1, "pages": 1, "coverage_pct": null}
```
`coverage_pct` stays `null` until a draft exists (P9). Errors: `404`, `422` for a bad page.
Used by: Sources screen (full-width source viewer).

## Readiness (PRD §4, §5.3 guided navigation, §5.4 Draft checklist) — phase P1

### GET /api/engagements/{id}/readiness
Response `200`:
```json
{"key_set": true, "transcripts_ready": false, "documents_ready": true,
 "speakers_unmapped": 0, "draft_exists": false, "blockers_count": 0,
 "nav": {"setup": "done", "sources": "attention", "draft": "not_started", "review": "not_started",
         "published": "not_started", "matrix": "not_started", "gap_analysis": "not_started",
         "registers": "not_started", "leadership": "not_started", "exports": "not_started"},
 "nav_counts": {"sources": 1},
 "next_step": "sources",
 "missing": ["Add an interview transcript"],
 "ready_to_draft": false}
```
- `transcripts_ready`: at least one `interview_transcript` source has `text_status: "ready"`.
- `documents_ready`: at least one SOP, manual, executed artefact or other document is ready (a job description alone doesn't describe the steps).
- `speakers_unmapped`: speaker labels in ready transcripts that have no role yet (from P2).
- `blockers_count`: failing hard checks on the latest draft's quality card (from P7; `0` until then).
- `missing`: plain-language list of what the draft still needs, in this order: API key · interview transcript · process document · each transcript with unmapped speakers ("Map 1 speaker in interview_transcript.txt"). Empty when `ready_to_draft` is true.
- `nav` status rules: **setup** done when trigger and end point are filled, otherwise not started. **sources** not started with no files; done when nothing source-related is missing and no file failed; otherwise attention, with `nav_counts.sources` = source items missing + failed files. **draft** done once a map version exists. **review** not started without a draft; done when every element of the latest version is reviewed and there are no blockers; otherwise attention with the number of elements left plus blockers. **published** and **leadership** done once a version is published. **matrix** and **registers** done once a draft exists (their content exists). **gap_analysis** done once a report is finalised. **exports** stays not started until exports are recorded (P7).
- `nav_counts` has an entry only for items in `attention`.
- `next_step`: the first item in nav order that isn't done, never `gap_analysis`; `null` when everything is done.

Errors: `404`. Used by: engagement navigation (top bar), Home (card click opens `next_step`; first-run checklist), Sources (readiness line), Draft (checklist, from P3).
