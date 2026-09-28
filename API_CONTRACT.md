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

### GET /api/settings/usage
The AI calls the app has made, newest first, for the "AI usage" card. Usage only: never prompt or document text.
Request: `?limit=50` (1 to 500; default 50).
Response `200`:
```json
{"items": [{"id": "…", "created_at": "…", "job_id": "…", "stage_id": "S1_extract_interview",
            "prompt_version": "1", "model": "claude-opus-5-5", "input_tokens": 5120,
            "output_tokens": 830, "duration_ms": 14200, "status": "ok"}],
 "totals": {"calls": 12, "input_tokens": 61000, "output_tokens": 9800}}
```
`status`: `ok` · `error` · `mock` (answered from the offline test answers). `totals` cover every call ever made, not just the rows returned.
Errors: `422 VALIDATION` (limit out of range). Used by: Settings screen, "AI usage" card (phase P3).

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

Files are stored as `data/sources/<engagement_id>/<source_id>.<ext>` (the original file name is kept for display only). Accepted formats: `.docx`, `.pdf`, `.txt`, `.vtt`, `.srt`, up to 50 MB. From phase P2 every file is **read by a background job** (PRD §4 "parsing runs as a job"): the upload answers straight away with `text_status: "pending"` and a `job_id`, and the file is read a moment later. How a file is read:
- `.vtt`, `.srt`: caption cues become speaker turns with start and end times.
- `.txt`: an interview transcript (`kind: "interview_transcript"`) is split into speaker turns (`Speaker: text` or `[mm:ss] Speaker: text`); any other `.txt` is split into paragraphs.
- `.docx`, `.pdf`: read as documents (paragraphs, headings as sections; PDF text per page); for an interview transcript the lines are then joined into speaker turns.
- Every passage is checked for instruction-like text (PRD §3.8 G9) and flagged `instruction_like: true`.
- Speaker labels that look like a person's name ("Priya Nair") are added to the engagement's redaction terms automatically (origin `speaker_map`, shown as "[name]" until the speaker is mapped).
- Images inside PDFs (at least 48 px) are saved to `data/images/<engagement_id>/` as **suggestions** (`status: "suggested"`, page number kept); nothing is shown on a map until Eric keeps them (P8).
- Changing a source's `kind` to or from `interview_transcript` reads a Word, PDF or text file again, unless one of its passages was corrected by hand (then the passages are kept as they are). Reading as a document removes the speaker turns and their mappings; names already on the redaction list stay hidden. When a file is read again as a transcript (for example a job run again after a restart), mappings are kept by speaker label.
- When the app starts, unfinished jobs are run again, and files still waiting to be read (for example transcripts uploaded in phase P1) are read.

### Source object
```json
{"id": "…", "engagement_id": "…", "kind": "sop", "filename": "sop_LC-07.docx",
 "format": "docx", "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
 "version_date": "2026-03-01", "owner": "Load Control", "controlled_copy": true,
 "text_status": "ready", "error": "", "segment_count": 10, "ocr_pages": [],
 "suggested_images": 0, "created_at": "…"}
```
`kind` is one of PRD B.1 (`interview_transcript`, `sop`, `manual`, `job_description`, `executed_artefact`, `other`). `text_status`: `pending` (being read) · `ready` · `failed` (with a plain `error`). `ocr_pages` lists PDF pages with almost no text, which will be read by OCR from phase P3. The upload response also carries `job_id` (the reading job); other responses have `job_id: null`. `filename` and `error` are shown with names hidden (G10), so a file called "Priya Nair interview.txt" is listed as "[name] interview.txt" or with the mapped role.

### POST /api/engagements/{id}/sources (multipart form)
Fields: `file` (required); `kind` (optional: guessed from the file name if missing: `.vtt`/`.srt`/names with "transcript" or "interview" → `interview_transcript`, "sop" → `sop`, "jd"/"job description" → `job_description`, "manual" → `manual`, else `other`); `version_date` (optional, `YYYY-MM-DD`); `owner` (optional, up to 120 characters); `controlled_copy` (optional, `true`/`false`).
Response `201`: source object with `text_status: "pending"` and `job_id`; the file is read in the background (poll the source or `GET /api/jobs/{job_id}`).
Errors: `404` engagement; `422 VALIDATION` ("Process Map Studio reads .docx, .pdf, .txt, .vtt and .srt files." · "That file is larger than 50 MB." · "The file is empty." · bad kind or date). A file that can't be read is still kept with `text_status: "failed"` and a plain `error`, so Eric can see it and delete or replace it.
Used by: Sources screen (drop zone).

### GET /api/engagements/{id}/sources
Response `200`: source objects, oldest first. Errors: `404`. Used by: Sources screen (registry), readiness.

### GET /api/sources/{sid} · PATCH /api/sources/{sid} · DELETE /api/sources/{sid}
GET → source object. PATCH → any of `kind`, `version_date`, `owner`, `controlled_copy` → source object. DELETE → `204`; removes the file, its passages and its suggested images.
Errors: `404` ("That source doesn't exist. It may have been deleted."); `422`.
Used by: Sources screen (registry row edits, delete, viewer header).

### GET /api/sources/{sid}/segments
Query: `page` (1-based, default 1), `page_size` (default 200, max 500), `uncited_only` (from P9; ignored until then), `raw` (`1` only for the owner-only correction editor).
Response `200`:
```json
{"segments": [{"id": "…", "seq": 3, "anchor": "§3.1", "page": null, "section": "3 Load planning",
               "speaker_role": null, "speaker_label": null, "text": "§3.1 The Load Controller shall …",
               "cited": false, "instruction_like": false, "corrected": false}],
 "total": 10, "page": 1, "pages": 1, "coverage_pct": null}
```
- `speaker_role`: the mapped role's name, `"Interviewer"`, or `null` when the speaker isn't mapped yet (never the label, which may be a name).
- **Names are hidden** (PRD §3.8 G10): `text` and `section` have every redaction term replaced by its replacement (the mapped role, "Interviewer" or "[name]"). With `raw=1` the text is exactly as stored and `speaker_label` is filled; this is one of the three owner-only places where names appear.
- `around=<segment_id>` (from P5): instead of `page`, return the page that holds this passage (the response's `page` says which). `404` "That passage isn't in this source." when it belongs to another source or doesn't exist.
- `coverage_pct` stays `null` until a draft exists (P9). Errors: `404`, `422` for a bad page.
Used by: Sources screen (full-width source viewer; correction editor with `raw=1`); Review detail panel (source viewer opened at a passage with `around`, P5).

### PATCH /api/segments/{segid} (correction editor, owner-only)
Request: `{"text": "…"}` — 1 to 5,000 characters. The passage is saved as typed, marked `corrected: true`, and checked again for instruction-like text.
Response `200`: the segment as with `raw=1`. Errors: `404` ("That passage doesn't exist."), `422`. Writes an audit row (without the text).

### GET /api/sources/{sid}/speakers (speaker-mapping card, owner-only)
Response `200`: one entry per speaker label, in order of first appearance:
```json
[{"label": "Interviewer", "segment_count": 1, "role_id": null, "is_interviewer": true},
 {"label": "Priya Nair", "segment_count": 8, "role_id": "…", "is_interviewer": false}]
```
Errors: `404`. A document without speakers returns `[]`.

### PUT /api/sources/{sid}/speakers (owner-only)
Request: `{"Priya Nair": "<role id>", "Interviewer": "interviewer", "Speaker 3": null}` — for each label: a role of this engagement, `"interviewer"`, or `null` to clear the mapping. Labels not sent are left as they are.
Effect: every passage of that label gets the role (or Interviewer). A label that looks like a personal name is on the redaction list, and its replacement becomes the role's name ("Interviewer", or "[name]" when cleared); if Eric removed it from the list, mapping adds it back.
Response `200`: the speakers list as for GET. Errors: `404`; `422` ("There is no speaker called … in this file." · "Choose one of this engagement's roles, or Interviewer."). Writes an audit row (counts only, no names).

## Redaction terms (PRD §4 Redaction, §3.8 G10) — phase P2

Names to hide everywhere except the three owner-only places (speaker-mapping card, redaction list, correction editor). Terms are matched as whole words, ignoring case and spacing. Confidential terms from the scope card (origin `confidential_term`) are stored in the same table but are **not** part of this list: they only restrict what is sent to web research.

### Redaction term object
```json
{"id": "…", "engagement_id": "…", "term": "Priya Nair", "replacement": "Load controller", "origin": "speaker_map"}
```
`origin`: `speaker_map` (added automatically from a name-like speaker label) or `manual` (added by Eric).

### GET /api/engagements/{id}/redaction-terms
Response `200`: terms, oldest first. Errors: `404`.

### POST /api/engagements/{id}/redaction-terms
Request: `{"term": "Priya", "replacement": "Load controller"}` — `term` 1–120 characters, one line; `replacement` optional (up to 80 characters; empty means "[name]").
Response `201`: term (`origin: "manual"`). Errors: `404`; `409 CONFLICT` ("That name is already on the list."); `422`.

### DELETE /api/redaction-terms/{tid}
Response `204`. Errors: `404` (also for confidential terms, which are edited on the scope card). Writes an audit row.

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
- `speakers_unmapped`: speaker labels in ready transcripts with no role and not marked Interviewer.
- `blockers_count`: failing hard checks on the current draft's quality card (phase P7; `0` without a draft), worked out when asked.
- `missing`: plain-language list of what the draft still needs, in this order: API key · interview transcript · process document · each transcript with unmapped speakers ("Map 1 speaker in interview_transcript.txt"). Empty when `ready_to_draft` is true. File names are shown with names hidden.
- `nav` status rules: **setup** done when trigger and end point are filled, otherwise not started. **sources** not started with no files; done when nothing source-related is missing and no file failed; otherwise attention, with `nav_counts.sources` = source items missing + failed files. **draft** done once a map version exists. **review** not started without a draft; done when every element of the latest version is reviewed and there are no blockers; otherwise attention with the number of elements left plus blockers. **published** and **leadership** done once a version is published. **matrix** and **registers** done once a draft exists (their content exists). **gap_analysis** done once a report is finalised. **exports** done once anything was exported (P7).
- `nav_counts` has an entry only for items in `attention`.
- `next_step`: the first item in nav order that isn't done, never `gap_analysis`; `null` when everything is done.

Errors: `404`. Used by: engagement navigation (top bar), Home (card click opens `next_step`; first-run checklist), Sources (readiness line), Draft (checklist, from P3).

## Jobs (PRD §4 Pipeline) — phase P2

Long work runs in one background worker inside the app, one job at a time, in the order it was started. Jobs survive a restart: when the app starts, jobs that were queued or running are run again.

### GET /api/jobs/{job_id}
Response `200`:
```json
{"id": "…", "engagement_id": "…", "type": "draft", "target_id": "<version id>",
 "status": "running", "stage": "Extracting steps from each source", "progress": 0.4,
 "message": "", "error": "",
 "usage": {"calls": 3, "input_tokens": 15400, "output_tokens": 2100},
 "claims": {"verified": 12, "rejected": 1},
 "stages": [{"id": "read", "name": "Reading the documents", "status": "done",
             "started_at": "…", "finished_at": "…"},
            {"id": "extract", "name": "Extracting steps from each source", "status": "running",
             "started_at": "…", "finished_at": null}],
 "created_at": "…"}
```
`status`: `queued` · `running` · `done` · `failed` (with a plain `error`). `type`: `read_source` (P2) · `draft` (P3). `target_id`: the source ID for `read_source`; for `draft`, the version being built (`null` until the job starts).
- `usage`: tokens used by this job's AI calls so far (`null` for jobs that make none).
- `claims`: claims of the version being built, checked so far (`verified`, `rejected`).
- `stages`: the draft's stages in order (empty for `read_source`). Stage `status`: `waiting` · `running` · `done` · `failed` · `skipped` (Independent verification when the verifier is switched off in Settings) · `later` (a stage built in a later phase; none since P4). Times are UTC ISO 8601; the screen shows the elapsed time.
Errors: `404` ("That job doesn't exist."). Used by: Sources (reading status), Draft (from P3).

## Draft (PRD §3.7 pipeline, §4, §5.4 Draft) — phase P3

Drafting is one background job of type `draft` running every stage of PRD §3.7 (phase P4): **Reading the documents** (S0: scanned PDF pages are read by Claude), **Extracting steps from each source** (S1, per source and chunk), **Checking every quote against your documents** (G3–G5 and name scrubbing G10, on every claim as it arrives), **Comparing sources** (S2 steps and merges, S3 stances and source states), **Independent verification** (S3b; `skipped` when switched off in Settings), **Building the map** (S4 phases, edges, RACI, details, confidence; then the lint rules, stored on the version) and **Writing validation questions** (S5). Every ready source of the engagement is used and recorded with the version.

The draft version (state `draft`) is created when the job starts: `v0.1` for the first draft, the next number (`v0.2` …) when it replaces an earlier draft. If any stage fails, the version and everything stored for it are deleted ("Nothing was saved."); the usage of the calls already made stays in the AI usage list. A successful draft replaces the earlier draft as long as none of its steps has been reviewed (confirmed, edited or added, from P6); a draft with reviewed steps is never replaced here (refreshing arrives with the review workbench).

### POST /api/engagements/{id}/draft
**AI.** Starts drafting. Request: none.
Response `202`: `{"job_id": "…"}`.
Errors:
- `404` engagement missing.
- `409 CONFLICT` "The draft can't start yet: <first missing item>." with `details.missing`: the readiness `missing` list (key, transcript, document, speakers).
- `409 CONFLICT` "A draft map is already being made." (a draft job is queued or running) or "This draft has steps you've already reviewed. Refresh it from the sources on the Review screen instead." (from P6, when a step is confirmed, edited or added).
- `409 CONFLICT` "This process has a published map. Reopen it as a new draft on the Published screen." (from P7, once a version is published and no draft exists: a new draft from scratch would lose the review).
Used by: Draft screen (Create draft map, Retry).

### POST /api/versions/{vid}/refresh (phase P6)
**AI.** Refresh draft from sources: runs every stage again on the engagement's ready sources and folds the result into the same draft, whose number goes up (`v0.1` → `v0.2`). Request: none. Response `202`: `{"job_id": "…"}` (job type `refresh`, target the draft; progress and stages as the draft job, shown on the Draft screen).
- Steps Eric confirmed, edited, added or rejected stay exactly as they are (constraint 8: locked steps are never written by a pipeline run; a rejection stands): same ID, fields, RACI, evidence and review status. A fresh step with the same key as one of them is dropped in its favour; the fresh lines into it point at it, and its own lines stay (a line whose other end was replaced follows the fresh step with the same key).
- Every other step, line, phase, claim (and the rejected-claims register), gap, question and merge proposal is replaced by the fresh run. A question with exactly the same wording as one already answered stays answered.
- The draft being refreshed stays visible on Review while the run builds (its temporary version has state `building` and is never listed). If a stage fails, nothing changes ("Nothing was saved.").
- An audit row "Refreshed draft from sources" records the labels before and after and how many steps were kept.
Errors: `404` ("That version doesn't exist."); `409` "Only the current draft can be refreshed." · "A draft map is already being made." · "The draft can't start yet: …" (readiness). Used by: Draft screen and Review (P6).

### GET /api/engagements/{id}/draft
The latest draft job and the current draft, so the Draft screen can pick up a running job after a reload.
Response `200`:
```json
{"job": {"…": "job object as GET /api/jobs/{job_id}"},
 "version": {"id": "…", "label": "v0.1", "state": "draft", "created_at": "…"},
 "summary": {"steps": 8, "needs_check": 0, "verified": 21, "rejected": 0,
             "open_questions": 5, "scrubbed": 0}}
```
`job` is `null` before the first draft; `version` and `summary` are `null` without a draft. `steps`: activities, decisions and approvals on the draft; `needs_check`: steps the independent verifier found only partly supported; `verified` / `rejected`: claims; `open_questions`: validation questions still open (including every gap Claude raised); `scrubbed`: names replaced by roles in Claude's answers.
`job` is the newest draft or refresh job. Errors: `404`. Used by: Draft screen.

### GET /api/versions/{vid}/graph
The version's map as the graph of PRD §3.6 (also the future `.json` export): `version`, `process` (name, trigger, end point, KPI, `cycle_time: {elapsed_min, work_min, incomplete_steps}` along the main path), `roles`, `phases`, `elements`, `edges` (`from`, `to`, `kind`, `label`).
Each element: `id, stable_key, kind, label, lane_role_id, phase_id, time: {work_min, wait_min, text}, complexity, kpi, decision: {mechanism, decider_role_id, rule_or_threshold, escalation}, handoff: {in, out}, raci: [{role_id, letter, contested}], provenance, r_reference, source_state, divergence_types, constraints: [{text, provenance, cause_type, is_key}], k_risk, ai_flag: {component, input, output, handoff, basis} | null, evidence: [{segment_id, source_id, source_kind, stance, anchor, verified, note}], confidence, confidence_breakdown: [{label, delta}], needs_check, review_status`.
- Every source the draft was made from appears in each element's `evidence`; a source that says nothing about the element is `silent` with `segment_id: null` (constraint 4).
- Names on the hidden list are replaced by roles in every text. Verbatim quotes and images are never included.
- Start and end are elements of kind `start` and `end` (from the scope card's trigger and end point) with no confidence.
Errors: `404` ("That version doesn't exist."). Used by: Review (P5), exports (P7).

### GET /api/versions/{vid}/layout
Where the UI draws the version's map (PRD §3.9), worked out on the server; the UI draws exactly these whole-pixel positions and never computes layout. The same graph always gives byte-identical JSON.
Response `200`:
```json
{"canvas": {"w": 1112, "h": 668},
 "lanes": [{"role_id": "…", "label": "Load controller", "step_count": 4, "y": 420, "h": 124}],
 "phases": [{"phase_id": "…", "label": "Plan", "time_window": "T-120 to T-90", "x": 120, "w": 372}],
 "nodes": [{"id": "…", "shape": "rounded_rect", "x": 256, "y": 442, "w": 100, "h": 44,
            "label_lines": ["Draft load plan"],
            "label_pos": {"x": 306, "y": 457, "align": "center"},
            "lens_pos": {"x": 306, "y": 492, "align": "center"}}],
 "edges": [{"id": "…", "kind": "reject", "is_back_edge": true,
            "points": [[430, 70], [430, 62], [292, 62], [292, 442]],
            "label": "Rework", "label_pos": {"x": 424, "y": 53, "align": "right"}}]}
```
- `nodes[].id` and `edges[].id` are the graph's element and edge IDs; every element is placed, rejected ones too (drawn faded).
- `shape`: `rounded_rect` (activity) · `pill` (approval) · `diamond` (decision; `w`/`h` is the box around the 36 px square turned 45°) · `circle` (start) · `double_circle` (end).
- `label_lines`: the label wrapped to at most two lines of 16 characters (ellipsis beyond); empty for start and end. `label_pos`: inside the node for activities and approvals, beneath the diamond for decisions; `y` is the top of the first line.
- `lens_pos`: where the lens line goes (`y` = its top). `align` is `left` when a line leaves or enters the node's bottom, so the text sits beside it.
- `points`: the corners of an orthogonal line from source to target. `is_back_edge`: drawn dashed along the track 14 px below the top of the upper lane.
- `label_pos` of an edge: the centre line (`y`) and left, centre or right edge (`x`, per `align`) of its label chip; `null` when the edge has no label.
Errors: `404` ("That version doesn't exist."). Used by: Review (P5).

### GET /api/versions/{vid}/lint
The lint report of PRD §3.7 (L1–L12), stored on the version when the draft is built:
```json
{"failures": [{"rule": "L4", "element_id": "…", "message": "Decision \"Deviation in limits?\" needs at least two labelled exits; it has 1."}],
 "warnings": [{"rule": "L12", "element_id": "…", "message": "Activity \"Issue load sheet\" has no time stated."}]}
```
Failures block publishing (P7); warnings are listed beneath the quality card. Since P5 the warnings include "The map has n line crossings; consider changing the lane order." (L12, more than 3 crossings in the layout). A version without a stored report is linted on request.
Errors: `404`. Used by: Draft summary (P4), Review Lint tab (P6), quality card (P7).

### GET /api/versions/{vid}/quality-card (phase P7)
The publish quality card of PRD §7.2, worked out afresh for a draft (and stored with it); a published version returns the card stored when it was published.
Response `200`:
```json
{"checks": [{"id": "Q1", "name": "Provenance green", "status": "pass", "hard": true,
             "detail": "All 8 steps are tagged O, I or R."},
            {"id": "Q10", "name": "60-minute validatable", "status": "warning", "hard": false,
             "detail": "30 steps and 5 lanes: consider splitting by phase."}],
 "warnings": ["Activity \"Issue load sheet\" has no time stated."],
 "all_green": false}
```
- `status`: `pass` · `fail` (hard checks Q1–Q9) · `warning` (Q10 only, when above 25 steps or 6 lanes). `all_green`: every hard check passes.
- Q1 every step on the map tagged O/I/R and every R with a reference · Q2 every O/I step with at least one verified passage and no unverified claim behind any step · Q3 no lint L4/L5 failure · Q4 no L6–L9 or L11 failure · Q5 no L10 failure · Q6 no unreviewed step, pending merge, open image suggestion, or unconfirmed step needing a check · Q7 the rendered Master Process Map and HTML map have exactly the three sections in order, and recommendation content (AI flag blocks, knowledge risks, external practice, questions) only in section 3 · Q8 no name from the redaction list in any rendered export (md, json, csv, html) · Q9 no image data or image reference in any rendered export.
- `warnings`: the lint warnings (steps without time, activities without KPI, AI flags outside 3–7, line crossings, large map). Rejected steps are not on the map and count for nothing. Each failing detail names what to fix; names hidden.
Errors: `404` ("That version doesn't exist."). Used by: Review banner and quality popover (P7), readiness `blockers_count`, publish.

## Views: alignment matrix, registers, cause library (PRD §4 Views, §5.4 Matrix and Registers) — phase P9

### GET /api/versions/{vid}/alignment-matrix
How each kind of source stands on each step (PRD §3.7 Stage 3: classified, never reconciled). One row per step (activity, decision, approval; not start, end or rejected steps), in process order:
`{"element_id", "label", "kind", "sop", "interview", "jd", "artefact", "state", "divergence_types": [...]}`.
- Columns: `sop` = SOPs, manuals and other documents · `interview` = interview transcripts · `jd` = job descriptions · `artefact` = executed artefacts.
- Each cell is `supports` · `contradicts` · `silent` · `not_applicable`: `contradicts` if any source of that kind contradicts the step, else `supports` if any supports it, else `silent` if the draft was made from a source of that kind (silence is never contradiction), else `not_applicable` (no source of that kind). A recommended (`R`) step is not assessed: every cell is `not_applicable`. Cells count the same stances as the step's source state.
- `state` and `divergence_types` are the step's own (B.4, B.5). Labels have names hidden. Works for drafts and published versions.
Errors: `404` ("That version doesn't exist.").

## Images (PRD §4 Images, §5.7.7 item 10, constraint 11) — phase P8

Images live only in the app: never in any export (Q9). Every image needs a caption, a type (B.16: `workplace_photo` · `system_screenshot` · `executed_artefact` · `illustrative_diagram` · `document_extract`) and the confirmation that faces, names, badge numbers and flight identifiers are removed or not shown. Metadata (EXIF, including GPS) is removed from the stored file. Changes are made on a draft version only (`409` "This version is published and can't be changed. Reopen it as a new draft."); start and end carry no images (`422`).

An image as returned: `{"id", "element_id", "caption", "image_type", "origin": "uploaded" | "extracted", "status": "suggested" | "kept" | "discarded", "redaction_confirmed", "source_name", "page", "created_at"}` — `source_name` and `page` for images suggested from a PDF (else `""` and `null`); captions and file names with names hidden.

### Suggested images from PDFs
When a PDF is read, each embedded picture at least 48 px on its shorter side is saved once for the source, already re-encoded without metadata (formats other than JPG, PNG and WebP become PNG), with a thumbnail. When a draft is made or refreshed, each such picture is suggested (`origin: "extracted"`, `status: "suggested"`, caption "Image from <file>, page <n>") on every step, decision or approval whose **verified** evidence cites a passage on the same page of the same PDF; not on start, end or rejected steps. A step never gets the same picture twice: one already kept or discarded there isn't suggested again. On a refresh, the pictures of a step that is replaced move to the fresh step with the same key (decisions carry over). Reopen copies every image row with its decision. Open suggestions on steps that aren't rejected count in Q6 and block Publish (`suggested_image`).

### POST /api/elements/{eid}/images
Upload an image to a step (multipart: `file`, `caption`, `image_type`, `redaction_confirmed`). Response `201`: the image, `origin: "uploaded"`, `status: "kept"`.
- `file`: JPG, PNG or WebP, up to 10 MB and 40 million pixels, and it must open as a picture ("Choose a JPG, PNG or WebP picture." · "Pictures can be up to 10 MB." · "Pictures can be up to 40 million pixels. Save a smaller copy and upload that." · "That picture couldn't be opened. Save it again and upload the copy."). The stored copy is re-encoded with the picture's orientation applied and no metadata; a thumbnail (longest side 480 px) is stored with it.
- `caption`: 1-300 characters, one line ("Add a caption of up to 300 characters."); a name from the redaction list is refused ("The caption contains a name from your list of names to hide. Use the role instead.").
- `image_type`: one of B.16 ("Choose what kind of picture this is.").
- `redaction_confirmed`: must be true ("Confirm that faces, names, badge numbers and flight identifiers are removed or not shown.").
Errors: `404` ("That step doesn't exist."); `409`; `422` naming the field (`details.field`). An audit row "Added image".

### GET /api/elements/{eid}/images
The step's images that aren't discarded, suggested ones first, then in the order they were added. Errors: `404`.

### PATCH /api/images/{iid}
Keep or discard a suggested image, or change a caption. Request: any of `{"status": "kept" | "discarded", "caption": "…", "image_type": "…", "redaction_confirmed": true}`.
- `kept` (a suggestion): needs its caption, a type and `redaction_confirmed: true`, the same rules as an upload. `discarded` (a suggestion): hides it; its file stays for other drafts that use it. A kept or uploaded image can't go back to suggested (`422`).
Response `200`: the image. Audit rows "Kept suggested image" · "Discarded suggested image" · "Changed image caption". Errors: `404` ("That image doesn't exist."); `409`; `422`.

### DELETE /api/images/{iid}
Remove an uploaded image (`204`). A suggestion is discarded instead (`422` "Discard a suggested picture instead of removing it."). The file is deleted when no other version still uses it. An audit row "Removed image". Errors: `404`; `409`.

### GET /api/versions/{vid}/images
Every image on the version's steps that isn't discarded (rejected steps left out), in process order (the order of the steps, then as for one step), for the map's has-images marker and the walkthrough strip. Works for drafts and published versions. Errors: `404` ("That version doesn't exist.").

### GET /api/images/{iid}/file
The stored picture (`image/jpeg`, `image/png` or `image/webp`); `?size=thumb` for the thumbnail (made on first request if missing). Only the app shows it; no export links to it. Errors: `404`.

## Versions, publish and exports (PRD §3.5 versions and locking, §5.9, §7.2, §7.3) — phase P7

### GET /api/engagements/{id}/versions
Every version of the engagement, newest first (a refresh's half-built version is never listed).
Response `200`: `[{"id", "engagement_id", "label", "state", "created_at", "published_at", "published_by", "parent_version_id"}]` — `state`: `draft` · `published` · `superseded`; `published_at`/`published_by` `null` for a draft.
Errors: `404` ("That engagement doesn't exist."). Used by: Published screen version picker, Exports screen.

### GET /api/versions/{vid}
One version with its review progress, change log and stored quality card.
Response `200`: the fields above plus `"review": {"reviewed": 8, "total": 8}` (steps; start and end don't count), `"change_log": [{"change": "confirmed", "step": "Draft load plan", "stable_key": "draft-load-plan"}]` (a published version: what was confirmed, edited, rejected or added while it was the draft, in process order; `[]` for a draft) and `"quality_card"` (the card as `GET …/quality-card`, or `null` if never worked out). Names hidden.
Errors: `404` ("That version doesn't exist."). Used by: Published screen, Review banner.

### POST /api/versions/{vid}/publish
Publish the current draft. Request: none.
- Refused with `409 PUBLISH_BLOCKED` (message "This draft can't be published yet: n things to fix.") unless the quality card's hard checks all pass; `details.blockers` lists each one: `[{"type": "unreviewed_element" | "needs_check" | "pending_merge" | "suggested_image" | "lint_failure" | "quality_check", "id": "…", "element_id": "…" | null, "message": "…"}]` — one per unreviewed step, per step needing a check, per pending merge, per suggested image, per lint failure, and per other failing check (Q1, Q2, Q7, Q8, Q9; `id` is the check ID). Names hidden.
- On success `200`: the version as `GET /api/versions/{vid}`: `state: "published"`, the next published label (`v1.0` first, then `v1.1`, `v1.2` …), `published_at` now, `published_by` the owner's name from Settings, the quality card and change log stored. The earlier published version becomes `superseded`. Published versions never change (every review endpoint answers `409`). An audit row "Published version".
Errors: `404`; `409` "Only the current draft can be published." (a published or superseded version).

### POST /api/versions/{vid}/reopen
Reopen the latest published version as a new draft. Request: none. Response `201`: the new draft as `GET /api/versions/{vid}`.
- A deep copy of the published map: phases, steps, lines, RACI, evidence links, constraints, AI flags, validation questions, image rows (files shared) and its sources. Confirmed, edited and added steps carry over as `confirmed` (locked); rejected steps stay rejected. Label: the next published number and "draft" (`v1.0` → `v1.1 draft`); `parent_version_id` the published version. Its claims, gap analyses and audit rows stay with the published version. Refreshing it keeps its label. An audit row "Reopened as new draft".
Errors: `404`; `409` "Only the latest published version can be reopened." · "There is already a draft. Review or refresh it instead."

### GET /api/versions/{vid}/export/{fmt}
Download an export of a published version; `fmt`: `md` (Master Process Map, §7.3) · `json` (graph JSON with the quality card) · `csv` (RACI) · `html` (the single-file offline map). Response `200`: the file (`text/markdown`, `application/json`, `text/csv`, `text/html`, UTF-8) with `Content-Disposition: attachment; filename="load-control-v1-0-master-map.md"` (`…-graph.json`, `…-raci.csv`, `…-map.html`). Role names only; no images, verbatim quotes or names; rejected steps left out; the stored quality card printed at the top. An audit row "Exported md" (etc.); the guided path's **Exports** step is done once anything was exported.
Errors: `404` (version, or unknown `fmt`: "Choose md, json, csv or html."); `409` "Publish a version with a green quality card first." (a draft, or a card that isn't green).

## Review (PRD §4 Review, §5.6–§5.8) — phase P5

### GET /api/elements/{eid}
One step with everything the detail panel shows (PRD §4: every element response carries these fields, so the panel renders without extra calls).
Response `200`: the element exactly as in the graph (`id, stable_key, kind, label, lane_role_id, phase_id, time, complexity, kpi, decision, handoff, provenance, r_reference, source_state, divergence_types, constraints, k_risk, ai_flag, confidence, confidence_breakdown, needs_check, review_status`), plus:
```json
{"version_id": "…", "lane_role_name": "Load controller", "phase_name": "Plan",
 "decider_role_name": "Load controller",
 "evidence": [{"segment_id": "…", "source_id": "…", "source_name": "interview_transcript.txt",
               "source_kind": "interview_transcript", "stance": "supports", "anchor": "06:40",
               "verified": true, "quote": "I build the preliminary plan…", "note": ""},
              {"segment_id": null, "source_id": "…", "source_name": "sop_RP-02.docx",
               "source_kind": "sop", "stance": "silent", "anchor": "", "verified": false,
               "quote": "", "note": ""}],
 "raci": [{"role_id": "…", "role_name": "Captain", "letter": "A", "contested": true,
           "sources": [{"source_name": "interview_transcript.txt", "source_kind": "interview_transcript", "anchor": "12:10"}]}],
 "image_count": 0, "gap_findings": []}
```
- `evidence`: the graph's evidence in the same order, each with its source's file name and the verbatim `quote` (for the in-app highlight; quotes never leave the app); silent sources have `segment_id: null` and no quote.
- `raci[].sources`: the passages behind that RACI entry (for a contested `A?`, the competing sources and anchors).
- `lane_role_name`, `phase_name`, `decider_role_name`: `""` when there is none.
- `image_count`: images on the step that aren't discarded (images arrive in P8). `gap_findings`: `[]` until P10.
- Names on the hidden list are replaced by roles in every text, including quotes and file names.
Errors: `404` ("That step doesn't exist."). Used by: Review detail panel (P5).

### POST /api/elements/{eid}/confirm · /reject · /restore (phase P6)
Review a step. Request: none. Response `200`: the element exactly as `GET /api/elements/{eid}` (with its new `review_status`).
- **confirm**: an unreviewed step (`draft`) becomes `confirmed`. A step already `confirmed`, `edited` or `added` stays as it is (nothing changes, no audit row). A `rejected` step must be restored first (`409` "This step is rejected. Restore it before confirming it.").
- **reject**: any step that isn't rejected becomes `rejected` (reversible; the map shows it faded, lint leaves it out).
- **restore**: a `rejected` step goes back to `draft` (`409` "Only a rejected step can be restored." otherwise).
- Confirmed, edited and added steps are **locked**: no pipeline run (refresh) ever writes to them.
- Only a draft version can change: `409` "This version is published and can't be changed. Reopen it as a new draft." otherwise.
- Start and end come from the scope card: `422` "Start and end come from the engagement's trigger and end point; change them on Setup."
- Each change writes an audit row (`Confirmed step`, `Rejected step`, `Restored step`, with the status before and after) and refreshes the stored lint report.
Errors: `404` ("That step doesn't exist."), `409`, `422`. Used by: Review panel actions and keyboard (P6).

### PATCH /api/elements/{eid} (phase P6)
Edit a step (the edit form and the table view's inline edits). Every field is optional; only the fields sent change.
Request:
```json
{"label": "Draft load plan", "kind": "activity", "lane_role_id": "…",
 "work_min": 20, "wait_min": 0, "duration_text": "~20 min, T-120 to T-90", "complexity": "M",
 "kpi": "Plan issued by T-90",
 "decision": {"mechanism": "rule_based", "decider_role_id": "…", "rule_or_threshold": "…", "escalation": "…"},
 "handoff": {"in": "Load forecast", "out": "Plan for approval"},
 "constraints": [{"text": "…", "cause_type": "single_point_knowledge", "is_key": true, "provenance": "O"}],
 "k_risk": "…",
 "ai_flag": {"component": "perception", "input": "…", "output": "…", "handoff": "…", "basis": "rule_based_automate_candidate"},
 "raci": [{"role_id": "…", "letter": "R", "contested": false}]}
```
Response `200`: the element as `GET /api/elements/{eid}`, with `review_status: "edited"` (an `added` step stays `added`).
Field rules (the same ones the edit form, the table view and Add step use; PRD §5.7.6):
- `label` 1–120 characters on one line; `kind` activity, decision or approval; `lane_role_id` one of the engagement's roles.
- `work_min`, `wait_min` 0–10,000 or `null`; `duration_text` ≤ 200 characters; `complexity` `L`, `M`, `H` or `null`; `kpi`, `handoff.in`, `handoff.out` ≤ 300; `rule_or_threshold`, `escalation`, `k_risk` ≤ 500.
- Decisions and approvals must be `rule_based` or `judgment` (constraint 7); `decider_role_id` one of the engagement's roles or `null`.
- `constraints` replace the list: text 1–300 characters, `cause_type` from B.9 or `null`, `provenance` O, I or R.
- `ai_flag` (or `null` to remove it): component B.11, input, output and handoff required (≤ 300), basis B.12; a judgment step can never be an automation candidate (constraint 7).
- `raci` (optional here, or `PUT …/raci`): roles of the engagement, letters R, A, C, I; at least one A, and several A's only when all are marked contested; activities need exactly one R.
- No text may contain a name on the engagement's hidden-names list (constraint 10): "…contains a name from your list of names to hide. Use the role instead."
- A rejected step must be restored before it is edited (`409`); a published version can't change (`409`); start and end come from Setup (`422`).
Errors `422` name the field (`details.field`, for example `"label"`, `"raci"`, `"ai_flag.basis"`). An audit row "Edited step" records each changed field before and after; the stored lint report is refreshed. Used by: Review edit form and table view (P6).

### PUT /api/elements/{eid}/raci (phase P6)
Replace a step's RACI. Request: `[{"role_id": "…", "letter": "A", "contested": false}]`. Same rules as `raci` above; response and effects as `PATCH`. Entries that stay (same role and letter) keep the passages behind them. Used by: Review edit form (P6).

### POST /api/versions/{vid}/elements (phase P6)
Add a missing step (Eric's own, never an AI claim).
Request: `{"kind": "activity", "label": "Check fuel figures", "lane_role_id": "…", "after_element_id": "…", "provenance": "O", "segment_ids": ["…"], "r_reference": "", "mechanism": "judgment"}`.
Response `201`: the element as `GET /api/elements/{eid}`, with `review_status: "added"` (locked).
- **Placement:** the step goes after `after_element_id` (any step or the start, not the end). The first outgoing line of that step that stays on the main path (not `no`, `reject`, `rework` or `exception`) now points at the new step, and a `sequence` line runs from the new step to where that line used to go. Without such a line, a `sequence` line joins them. The new step takes that step's phase. The layout is worked out afresh on the next `GET …/layout`.
- **Provenance:** `O` needs at least one passage (`segment_ids` from this engagement's sources; each becomes a verified "supports" evidence link) — "Pick the passage this step comes from."; `R` needs a reference (`r_reference`, 1–500 characters) — "Type the reference this recommended step comes from."; `I` is refused ("Choose Observed (with a passage) or Recommended (with a reference).").
- **RACI and decision rights:** the lane's role becomes Accountable (and Responsible for an activity; the decider for a decision or approval). `mechanism` (`rule_based` or `judgment`, default `judgment`) classifies a decision or approval (constraint 7). Everything else is added with Edit.
- Field rules as `PATCH /api/elements/{eid}` (name, kind, lane, no hidden names). Source state `not_assessed` and no confidence: the step wasn't compared across sources. An audit row "Added step".
Errors: `404` version or step; `409` published version; `422` naming the field (`after_element_id`, `segment_ids`, `r_reference`, …). Used by: Review Add step and "Add as step from this passage" (P6).

### POST /api/versions/{vid}/edges · PATCH · DELETE /api/versions/{vid}/edges/{edge_id} (phase P6)
Add, change or remove a line between two steps. Request (POST; PATCH sends any of them): `{"from": "…", "to": "…", "kind": "no", "label": "Outside limits"}`. Response: `201`/`200` `{"id", "from", "to", "kind", "label"}`; DELETE `204`.
- Both ends are steps of this version; no line into the start or out of the end, no line from a step to itself, no second line with the same ends and kind.
- `kind` from B.8 (`sequence`, `yes`, `no`, `approve`, `reject`, `rework`, `exception`); `label` up to 60 characters, required on every line leaving a decision or approval (constraint 6: every exit labelled); no hidden names.
- Audit rows "Added line", "Changed line", "Removed line"; the lint report is refreshed. Only a draft version changes (`409`).
Errors: `404` ("That line doesn't exist."), `409`, `422`. Used by: Review edit form and Add step (P6).

### GET /api/versions/{vid}/questions · PATCH /api/questions/{qid} (phase P6)
The validation questions for the offline SME session (PRD §5.7.10).
`GET` response `200`: `[{"id", "element_id", "element_label", "phase_id", "phase_name", "question", "reason", "status"}]` in the order they were written (step questions in process order, then every gap Claude raised). `reason`: contested · documented_only · inferred · partial_support · low_confidence · gap. `status`: open · answered. Names hidden.
`PATCH` request `{"status": "answered"}` (or `"open"` to reopen); response the question. Audit rows "Marked question answered" / "Reopened question". Only a draft version changes (`409`).
Errors: `404` ("That version doesn't exist." / "That question doesn't exist."), `409`, `422`. Used by: Review Questions tab (P6).

### GET /api/versions/{vid}/merge-proposals · POST /api/merge-proposals/{mid}/decision (phase P6)
Steps Claude thought might be one step described differently (PRD §5.7.10 Merge decisions, §9 assumption 8).
`GET` response `200`:
```json
[{"id": "…", "proposed_label": "Load and return LIR", "similarity": 0.86, "decision": "accepted",
  "decided_at": "…", "element_id": "…",
  "groups": [{"label": "Load aircraft", "kind": "activity", "lane_role_name": "Ramp",
              "element_id": null,
              "claims": [{"text": "Ramp loads the aircraft in about forty minutes.",
                          "source_name": "interview_transcript.txt", "anchor": "21:50",
                          "quote": "Ramp loads the aircraft, forty minutes or so"}]}]}]
```
- `decision`: `pending` (below 0.80: the steps are still separate and wait for Eric) · `accepted` (merged; at 0.80 or above this happened when drafting) · `rejected` (kept separate) · `split` (a merge undone).
- `element_id`: the merged step while the proposal is accepted; each group's `element_id`: that step while they are separate (else `null`). Claims show the claim text, source, anchor and quote; names hidden.
`POST` request `{"decision": "accepted" | "rejected" | "split"}`; response the proposal as in the list.
- **accepted** (Accept merge, from `pending` or `rejected`): the separate steps become one step named `proposed_label` in the first one's place: claims and evidence joined, lines re-pointed (loops onto itself and duplicates dropped), questions moved; its source state is worked out again from the joined evidence; it is marked Needs check and has no confidence until the next refresh works it out.
- **rejected** (Keep separate, from `pending`): nothing on the map changes.
- **split** (from `accepted`): the merged step goes back to its separate steps as drafted (label, kind, lane, claims), one after the other in its place; each step's evidence becomes the passages its own verified claims cite, as supporting it (the stances were judged against the joined step), divergences found between the joined descriptions are cleared, and each needs a check and has no confidence until the next refresh.
- A step that has been reviewed (confirmed, edited, added or rejected) is never merged or split (`409` "One of these steps has already been reviewed. Change it with Edit, Reject or Add step instead."). Keep separate on a merge in place is refused (`409` "These steps are merged. Use Split to separate them again."), and so is Split on steps that aren't merged (`409` "Only merged steps can be split."). The same decision again changes nothing. Audit rows "Accepted merge" / "Kept steps separate" / "Split merged step"; lint refreshed. Only a draft version changes.
Errors: `404` ("That merge proposal doesn't exist."), `409`, `422`. Used by: Review Merge tab (P6); pending ones block publishing (P7).

### GET /api/versions/{vid}/audit (phase P6)
The version's audit log, newest first.
Response `200`:
```json
[{"id": "…", "at": "2026-09-27T10:02:11.123456+00:00", "actor": "Eric", "action": "Confirmed step",
  "target_type": "element", "target_id": "…", "target_label": "Draft load plan",
  "before": {"review_status": "draft"}, "after": {"review_status": "confirmed"}}]
```
`target_label`: the step's current label (names hidden), `""` when the target no longer exists. Errors: `404` ("That version doesn't exist."). Used by: Review Audit tab (P6).

### GET /api/versions/{vid}/rejected-claims
The rejected-claims register (PRD §3.8 G12): claims that failed a check and never reach the map.
Response `200`:
```json
{"items": [{"id": "…", "claim_text": "The plan takes 30 min.", "source_id": "…",
            "source_name": "interview_transcript.txt", "anchor": "08:12",
            "reason": "number not found in cited text: 30", "guardrail": "G5", "stage": "S1",
            "passage_available": true, "segment_id": "…"}],
 "total": 1, "scrub_count": 1, "instruction_like_count": 1}
```
- `claim_text` and `source_name` have names on the redaction list replaced by roles.
- `anchor` and `segment_id`: the first cited passage that exists; `""` and `null` when none does (`passage_available: false`, e.g. G3 "cites a passage that wasn't provided").
- `guardrail`: B.20 (`G3` passage · `G4` quote · `G5` number or role · `G6` verifier · `G10` redaction).
- `scrub_count`: names Claude used that were replaced by roles, across all claims of the version. `instruction_like_count`: passages in the engagement's sources that looked like instructions and were treated as data.
Errors: `404` ("That version doesn't exist."). Used by: Draft screen (rejected-claims list, P3), Review workbench (P5).
