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
 "system_records_enabled": false, "gap_analysis_enabled": true, "value_enabled": false,
 "reality_views_enabled": false,
 "currency": "SGD", "default_timezone": "Asia/Singapore",
 "key_set": true, "key_last4": "x9Q2"}
```
`key_last4` is `""` when no key is set. Optional modules (decision A; a module switched off hides its screens and never deletes data): `system_records_enabled` (R7, 2026-10-08), the System records module, **off** by default (`SYSTEM_RECORDS_ENABLED`); `gap_analysis_enabled` (R10, 2026-10-13), the Gap analysis screen, **on** by default as before (`GAP_ANALYSIS_ENABLED`); `value_enabled` (R10), the value calculator with step dispositions (the panel's "Disposition and value" section and the Registers' "Disposition and value" list), **off** by default (`VALUE_ENABLED`); `reality_views_enabled` (P13a, 2026-10-13), the Reality views (P13), **off** by default (`REALITY_VIEWS_ENABLED`; its Settings switch arrives with the Reality screen in P13b). Regional (R10): `currency`, an ISO 4217 code for the value calculator (`CURRENCY`, default `SGD`); `default_timezone`, the time zone a new system log starts with (`DEFAULT_TIMEZONE`, default `Asia/Singapore`).

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

### PUT /api/settings/research (phase P10)
Turns external research (gap analysis B, PRD §3.11.2) on or off. Request `{"web_research_enabled": true}`. Response `200`: the settings object. Off by default; while off, nothing is ever sent to web search. Errors: `422` (field `web_research_enabled`: "Choose on or off."); `500 IO`.

### PUT /api/settings/modules (R7, 2026-10-08; PRD §5.4 Settings "Optional modules", decision A)
Switches optional modules on or off. Request any of `{"system_records_enabled": true, "gap_analysis_enabled": true, "value_enabled": true, "reality_views_enabled": true}` (a field left out keeps its value; R10 added the middle two, P13a the last, 2026-10-13). Each change is written to the audit log. Response `200`: the settings object. Switching off hides the module's screens and lenses and never deletes data. Errors: `422` (field named: "Choose on or off."); `500 IO`.

### PUT /api/settings/regional (R10, 2026-10-13; PRD §3.4 Settings item 9, §5.4 Settings "Regional")
Request any of `{"currency": "SGD", "default_timezone": "Asia/Singapore"}` (a field left out keeps its value). `currency`: three letters A–Z after trimming, upper-cased (an ISO 4217 code; the app does not convert amounts, it only labels them). `default_timezone`: an IANA time zone the computer knows (Python `zoneinfo.available_timezones()`). Response `200`: the settings object. Errors: `422 VALIDATION` with the field named ("Enter a three-letter currency code, for example SGD." · "Choose a time zone from the list, for example Asia/Singapore."); `500 IO`. Used by: Settings screen, "Regional" card. The System records upload form starts with `default_timezone`; a log's own time zone can still be changed.

### POST /api/settings/test-web-search (phase P10)
Checks that web search works for this key: one small search with a generic question ("published guidance on aircraft load control"), `max_uses` 1 (billed as one search by Anthropic). Mocked in tests. Response `200`: `{"available": true, "message": "Web search works for your Anthropic organisation."}`, or `available: false` with a plain message: no key saved; "Web search isn't enabled for your Anthropic organisation. See the README, 'If something goes wrong'." (the organisation has web search switched off in the Claude Console: Anthropic answers 400 saying web search is not enabled); key rejected. Errors: `503 AI_RATE_LIMIT`; `500 IO` (Anthropic couldn't be reached).

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
`status`: `ok` · `error` · `mock` (answered from the offline test answers) · `invalid` (the answer didn't match the format; a repair call follows) · `repaired` (the repair call's answer matched) · `truncated` (the answer was cut off at the length limit) · `refused` (Claude declined to answer). Shown on the card as OK, Failed, Test answer, Wrong format, Repaired, Cut off and Declined. `totals` cover every call ever made, not just the rows returned.
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
 "conventions": {"granularity": "standard", "label_style": "standard", "phase_naming": "sme"},
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
**Mapping conventions** (C7a, 2026-10-06; PRD Appendix E tier 2, §5.4 Setup, criterion 58): the engagement object also has `"conventions": {"granularity": "standard", "label_style": "standard", "phase_naming": "sme"}` (these defaults until Eric sets them). `granularity`: `coarse` (8–12 steps) · `standard` (12–20) · `fine` (20–25); `label_style`: `standard` (verb + object, at most 5 words) · `sme` (the SME's own everyday name for the step, where there is one; added to the glossary with a plain meaning); `phase_naming`: `sme` · `standard`. PATCH sends the whole `conventions` object (`422` naming `conventions.<field>` for an unknown value); a change writes the "Edited process scope" audit row. They take effect at the next draft or refresh: S2 (canonicalise) and S4 (assemble) receive `<conventions granularity="…" label_style="…" phase_naming="…"/>` with their data when any setting differs from the defaults (with the defaults nothing extra is sent: the codebook already states them), and follow them, departing only with a stated reason.
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

Files are stored as `data/sources/<engagement_id>/<source_id>.<ext>` (the original file name is kept for display only). Accepted formats: `.docx`, `.pdf`, `.txt`, `.vtt`, `.srt`, and since P10b R11 (2026-10-13) `.xlsx`, `.csv` and `.eml`, up to 50 MB. From phase P2 every file is **read by a background job** (PRD §4 "parsing runs as a job"): the upload answers straight away with `text_status: "pending"` and a `job_id`, and the file is read a moment later. How a file is read:
- `.vtt`, `.srt`: caption cues become speaker turns with start and end times.
- `.txt`: an interview transcript (`kind: "interview_transcript"`) is split into speaker turns (`Speaker: text` or `[mm:ss] Speaker: text`, or an Otter.ai export: the speaker and time on their own line, e.g. `Speaker 1  0:06`, the words on the lines below, the "Transcribed by https://otter.ai" footer dropped); any other `.txt` is split into paragraphs.
- `.docx`, `.pdf`: read as documents (paragraphs, headings as sections; PDF text per page); for an interview transcript the lines are then joined into speaker turns.
- `.xlsx` (R11; openpyxl, read only, the values Excel last calculated): one passage per filled row, sheet by sheet; the sheet name is the passage's `section` and the anchor is the row's cell in column A, written as Excel writes it (`Load plan!A5`, `'Shift log'!A12`). The first row whose filled cells are all text (at least two) is the header row; each row below it reads `Header: value | Header: value` (a cell under no header keeps its value only); rows above it are kept as they are. Numbers are written without a trailing `.0`, dates as `2026-03-02` (or `2026-03-02 09:14` with a time). More than 5,000 filled rows is refused ("This spreadsheet has more than 5,000 filled rows. If it is a system export, import it under System records; otherwise save only the rows that matter and upload again."); a workbook with no filled cell is refused ("The spreadsheet has no filled cells."). `.xls` and `.xlsm` are not read (save as `.xlsx`).
- `.csv` (R11; UTF-8 or Windows-1252; comma, semicolon, tab or bar): as one sheet, the anchor `row 5` (the record's number, the header row being row 1); the same header rule and limits.
- `.eml` (R11; the standard library `email`): one email, plus any email attached to it as a message. Each email gives a header passage (`From: … · To: … · Cc: … · Sent: 2026-03-03 09:14 +08:00 · Subject: …`, without a speaker) and its body as paragraph passages (plain text, else the HTML part as text), `section` "Email 1" (2, 3 … for attached emails). The sender is the `speaker_label` of their own paragraphs, so senders are mapped to roles like transcript speakers (the speaker-mapping card, without the Interviewer choice). The quoted part of a reply ("On … wrote:", "-----Original Message-----", an Outlook `From:`/`Sent:` block, `>` lines) is kept with `section` "Earlier in the thread", attributed to the sender its quote line names, or to no one when none is named. A signature (after a `-- ` line) is left out. Attachments other than emails are not read: save them and upload them as sources of their own. Every address, and every display name that looks like a person's name (the speaker-label rule; not a team such as "LC Ops Desk" or one of the engagement's roles), in the From, To, Cc, Bcc, Reply-To and Sender headers (and in quoted `From:`/`To:`/`Cc:` lines and "… wrote:" lines) is added to the engagement's redaction terms with origin `email_header` ("Tan, Wei Ming" also as "Wei Ming Tan"), so they are hidden everywhere outside the owner-only places. A file with no From, Subject or Date header is refused ("This .eml file doesn't look like an email.").
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
`kind` is one of PRD B.1 (`interview_transcript`, `sop`, `manual`, `job_description`, `executed_artefact`, `working_spreadsheet`, `email_thread`, `other`; `working_spreadsheet` and `email_thread` since R11). Working spreadsheets and email threads are **artefacts** (criterion 92): like executed artefacts they are a trace of work as done, so they count with them for source state (`trace_contradicted`, PRD §3.7), the alignment matrix's artefact column, the practice side of Analysis A, readiness (a process document) and signal strength (Moderate without an SOP or manual). `text_status`: `pending` (being read) · `ready` · `failed` (with a plain `error`). `ocr_pages` lists PDF pages with almost no text, which will be read by OCR from phase P3. The upload response also carries `job_id` (the reading job); other responses have `job_id: null`. `filename` and `error` are shown with names hidden (G10), so a file called "Priya Nair interview.txt" is listed as "[name] interview.txt" or with the mapped role.

### POST /api/engagements/{id}/sources (multipart form)
Fields: `file` (required); `kind` (optional: guessed from the file name if missing: `.xlsx`/`.csv` → `working_spreadsheet`, `.eml` → `email_thread` (R11), `.vtt`/`.srt`/names with "transcript" or "interview" → `interview_transcript`, "sop" → `sop`, "jd"/"job description" → `job_description`, "manual" → `manual`, else `other`); `version_date` (optional, `YYYY-MM-DD`); `owner` (optional, up to 120 characters); `controlled_copy` (optional, `true`/`false`).
Response `201`: source object with `text_status: "pending"` and `job_id`; the file is read in the background (poll the source or `GET /api/jobs/{job_id}`).
Errors: `404` engagement; `422 VALIDATION` ("Process Map Studio reads .docx, .pdf, .txt, .vtt, .srt, .xlsx, .csv and .eml files." · "That file is larger than 50 MB." · "The file is empty." · bad kind or date). A file that can't be read is still kept with `text_status: "failed"` and a plain `error`, so Eric can see it and delete or replace it.
Used by: Sources screen (drop zone).

### GET /api/engagements/{id}/sources
Response `200`: source objects, oldest first. From P9 each source object also has `coverage_pct` (as on the passages page below: the share of its passages the current map cites, or `null`). Errors: `404`. Used by: Sources screen (registry), readiness.

### GET /api/sources/{sid} · PATCH /api/sources/{sid} · DELETE /api/sources/{sid}
GET → source object. PATCH → any of `kind`, `version_date`, `owner`, `controlled_copy` → source object. DELETE → `204`; removes the file, its passages and its suggested images.
Errors: `404` ("That source doesn't exist. It may have been deleted."); `422`.
Used by: Sources screen (registry row edits, delete, viewer header).

### GET /api/sources/{sid}/segments
Query: `page` (1-based, default 1), `page_size` (default 200, max 500), `uncited_only` (P9: `1` lists only the passages no verified claim of the current map cites, interviewer turns left out; `total` and `pages` then count those; can't be combined with `around`: `422` field `uncited_only`), `raw` (`1` only for the owner-only correction editor).
Response `200`:
```json
{"segments": [{"id": "…", "seq": 3, "anchor": "§3.1", "page": null, "section": "3 Load planning",
               "speaker_role": null, "speaker_label": null, "text": "§3.1 The Load Controller shall …",
               "cited": false, "instruction_like": false, "corrected": false,
               "question_id": null}],
 "total": 10, "page": 1, "pages": 1, "coverage_pct": null}
```
- `question_id` (2026-10-01, PRD §3.12.10 step A): for an interview transcript, once a draft has been made, the guide question each turn asks (interviewer) or answers (the SME's turns until the next matched question); matched by an explicit tag such as `[M2.2]` (any question-bank ID) or by wording similarity ≥ 0.60 against the engagement's guide (until tailored guides exist: the standard Practice template's questions); `null` before the first matched question, for free conversation before it, and for documents.
- `speaker_role`: the mapped role's name, `"Interviewer"`, or `null` when the speaker isn't mapped yet (never the label, which may be a name).
- **Names are hidden** (PRD §3.8 G10): `text` and `section` have every redaction term replaced by its replacement (the mapped role, "Interviewer" or "[name]"). With `raw=1` the text is exactly as stored and `speaker_label` is filled; this is one of the three owner-only places where names appear.
- `around=<segment_id>` (from P5): instead of `page`, return the page that holds this passage (the response's `page` says which). `404` "That passage isn't in this source." when it belongs to another source or doesn't exist.
- **Coverage (G11, P9):** the *current map* is the engagement's draft, else its latest published version. A passage is `cited` when a verified claim of the current map cites it (the map's own claims, or the claims behind its steps, which a reopened draft keeps from the version it came from). `coverage_pct` = cited passages ÷ all passages except interviewer turns, as a percentage with one decimal; `null` when there is no current map or the map wasn't made from this source (for example a source added after the draft). Errors: `404`, `422` for a bad page.
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
Errors: `404`. A document without speakers returns `[]`; an email thread's speakers are its senders (R11).

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
`origin`: `speaker_map` (added automatically from a name-like speaker label), `email_header` (R11: added automatically from an email's headers or quoted header lines) or `manual` (added by Eric). Mapping a speaker whose label is on the list (any origin) shows it as the mapped role.

### GET /api/engagements/{id}/redaction-terms
Response `200`: terms, oldest first. Errors: `404`.

### POST /api/engagements/{id}/redaction-terms
Request: `{"term": "Priya", "replacement": "Load controller"}` — `term` 1–120 characters, one line; `replacement` optional (up to 80 characters; empty means "[name]").
Response `201`: term (`origin: "manual"`). Errors: `404`; `409 CONFLICT` ("That name is already on the list."); `422`.

### DELETE /api/redaction-terms/{tid}
Response `204`. Errors: `404` (also for confidential terms, which are edited on the scope card). Writes an audit row.

## Interview templates (PRD v1.10 Appendix F.9, §4 Interview and sensemaking, §5.4) — phase P1

Standard templates generated deterministically (no AI, no engagement data) from `backend/app/prompts/question_bank.json`, stamped with its version. Available before any engagement exists. The question bank is Appendix F word for word (a test compares them); wording changes need the PRD to change or a logged decision.

### GET /api/templates/data-request?format=docx|md|csv (R1, 2026-10-07; PRD §3.13.2, criterion 82)
The data request template Eric sends to the system owner (IT) to ask for an event-log extract. No engagement and no AI: the same file every time, with [bracketed] placeholders for the process, scope and dates. `docx` (Word, editable), `md` (`text/markdown; charset=utf-8`): 1 purpose in plain words ("to measure volumes and waiting times in [process]; no individual performance analysis"); 2 process scope with the start and end events; 3 the date window (3–6 months recommended, at least 4 weeks); 4 the column table (B.40: case_id, activity, timestamp, end_timestamp, resource, role, system, case attributes) marking the required ones, with one sample row; 5 privacy requirements (role rather than user IDs; user IDs, if any, converted to roles on import and discarded; no free-text comments; no customer personal data); 6 format (CSV UTF-8 or Excel, one file per system); 7 data owner approval (name, role, date ☐) and the retention promise ("stored only on the analyst's computer and deleted with the engagement"). `csv` (`text/csv; charset=utf-8`): the header row only, `case_id,activity,timestamp,end_timestamp,resource,role,system`, ready to fill. Filenames `data-request-template.docx|md` and `data-request-header.csv`. Errors: `422` for another format. Used by: System records screen (R7).

### GET /api/templates/interview/plans
What the home screen and the Interview screen show for each template (added 2026-09-30 so the screens never hold their own copy of the minute plans).
Response `200`: `[{"type": "landscape" | "practice" | "follow_up", "title": "Landscape", "minutes": 60, "who": "…", "purpose": "…", "plan": [{"label": "Opener and framing", "minutes": 3}, …], "question_count": 16, "bank_version": "1.0"}]` in the order Landscape, Practice, Follow-up. Minute plans sum to 60 / 60 / 30.

### GET /api/templates/interview?type=landscape|practice|follow_up&format=docx|md
The template file. `docx`: Word (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`, made with python-docx, editable); `md`: Markdown (`text/markdown; charset=utf-8`). Both carry the same content in the F.9 layout: 1 title with the question-bank version; 2 header table to fill in (Engagement / process · Interviewee role · Stakeholder group · Date · Interviewer · Referred by (role) · Recording consent ☐); 3 [RECORD THE SESSION] and the F.3 opener with [bracketed] placeholders; 4 the minute plan; 5 interviewer principles (F.1); 6 one table per movement or plan section: ID · Question · Probes · Minutes · Notes (story sections repeat the signifier questions under each story); 7 coverage checklist with tick boxes; 8 close and next steps; 9 the question-ID footer ("Say or note the question ID (e.g. [M2.2]) when you ask it …"), on every page in Word and at the end in Markdown.
- Minutes per question are the plan section's minutes shared in half minutes, core questions (never dropped, F.8 rule 6) counting double, so each section adds up exactly; a story's minutes include its signifier questions (their rows say "in story").
- `Content-Disposition: attachment; filename="interview-template-practice.docx"` (or `.md`; `landscape`, `follow-up`).
Errors: `422 VALIDATION` ("Choose landscape, practice or follow_up." · "Choose docx or md."). No personal names, no SOP claims before M6, no banned words (tests).

## Interviewee profiles (PRD §4 Interview and sensemaking, §3.12.8, Appendix F.8 rule 1) — phase P4c (2026-10-05, C5a)

Who a tailored interview guide is for: a role, function or stakeholder group, never a person (constraint 10). The generator (C5b) picks the interview type and fills the opener's brackets from it.

### Profile object
```json
{"id": "…", "engagement_id": "…", "role_id": "…" | null, "role_name": "Load controller" | "",
 "stakeholder_group": "Ramp", "interview_type": "landscape" | "practice" | "follow_up",
 "referred_by_role": "Ramp duty manager", "previous_profile_id": "…" | null, "created_at": "…"}
```

### POST /api/engagements/{id}/profiles · GET /api/engagements/{id}/profiles
POST request: `{"role_id", "stakeholder_group", "interview_type", "referred_by_role", "previous_profile_id"}` — `interview_type` required (B.38); `role_id` one of the engagement's roles or `null`; `stakeholder_group` and `referred_by_role` up to 120 characters on one line; a role or a stakeholder group is required ("Say whose interview this is: choose a role or name the stakeholder group."); `previous_profile_id` another profile of this engagement or `null` (the earlier session a follow-up builds on). No text may contain a name on the hidden-names list ("…contains a name from your list of names to hide. Use the role instead."). Response `201`: profile, and an audit row "Added interviewee profile". GET response `200`: the engagement's profiles, oldest first.
Errors: `404` (engagement), `422` naming the field (`details.field`).

### PATCH /api/profiles/{pid}
Any of the POST fields; the same rules (a profile can't name itself as its previous session). Response `200`: profile; audit row "Edited interviewee profile" with the changed fields. Errors `404`, `422`.
Used by: Interview screen, Guides tab (C5a).

## Tailored interview guides (PRD §4 Interview and sensemaking, §3.12.8, Appendix F.8–F.9, criterion 80) — 2026-10-06, G1

A guide for one interviewee profile, in the same F.9 layout as the standard templates, exported to Word and Markdown. G1 builds it **deterministically** (no AI) from the question bank, the profile and the engagement: the parts of the F.8 tailoring rules that need no AI. Wording from the bank is never changed; filled-in brackets and added probes are the only differences from the standard template. The AI tailoring (`IG_generate`: role modules, reworded probes) comes with P4c C5b and will make the POST a background job.

### Guide object
```json
{"id": "…", "engagement_id": "…", "profile_id": "…", "interview_type": "practice",
 "version": 2, "edited": false, "created_at": "…",
 "document": {"kind": "practice", "title": "Practice interview guide: Ramp agent · Ramp", "stamp": "…",
              "header_fields": ["Engagement / process", …], "header_values": {"Engagement / process": "Load control", …},
              "record": "…", "opener": ["…"], … the InterviewDocument of the templates …}}
```
Each question row of `document.tables[].rows[]`: `{"id", "lead_in", "wording", "note", "probes", "minutes", "signifier", "movement", "targets", "priority", "held_back"}` (C5b-1, F.8 rule 9): `movement`, `targets` (what the question is for: the bank's targets, or its translation for the F-series and the framing line) and `priority` (`core` · `standard`) come from the bank and are not printed in the files; `held_back` holds the SOP-derived probes of M6.5 (rule 5), printed after the bank's probes and shown by the editor as "held back to avoid anchoring the SME". Rows the interviewer fills in have an empty `id`.

### POST /api/engagements/{id}/interview-guide
Request: `{"profile_id": "…"}`. Since C5b (2026-10-06) a background job (was a synchronous `201` in G1): response `202` `{"job_id": "…", "profile_id": "…"}`; follow it with `GET /api/jobs/{job_id}` (type `interview_guide`, stages `gather` "Reading the scope, roles and map" · `generate` "Drafting role-module questions" · `check` "Checking every question" · `save` "Saving the guide"; `usage` like the gap-analysis jobs). When it is `done` the new version (1, 2, …) is what `GET …/interview-guide?profile_id=` returns and the job `message` says what was made. What is filled in (F.8):
- **Rule 1** the interview type is the profile's; title "<Type> interview guide: <role · group>".
- **Rule 2** header values: Engagement / process (process name), Interviewee role, Stakeholder group, Referred by (role); Date, Interviewer and Recording consent stay blank. Opener brackets: `[end-to-end scope …]` → "<process> process, from <trigger> to <end point>" (the opener already says "the"), `[business]` → the engagement name, `[area]` → the stakeholder group (else the role), `[referrer role]` → Referred by; a bracket with nothing to fill stays as it is.
- **Rule 3** (Landscape, AI, `IG_generate`): the role-module rows get 3–5 questions for the interviewee's stakeholder group (else role), each based on L3, L4 or L5 and naming that group's interfaces from the scope card, the roles and the latest map's handoffs (names hidden before sending). Each is checked by the app: based on L3–L5; one line ending with "?"; 1–3 one-line probes; no banned (blaming) word, no claim about what the documents say, no name on the hidden-names list (wording and probes); no repeats. Kept questions get IDs `RM1`… in order, the targets of the L-question they are based on, movement `L`, priority `standard`, and the module's 8 minutes shared among them (the plan still sums to 60). Fewer than four kept → the rest stay blank rows. No key, Anthropic unreachable, an answer in the wrong format twice, or no question passing → the rows stay blank and `document.generation_note` says why in plain words; the guide is still made (the job is `done`). Nothing else in the guide comes from the AI.
- **Rule 5** (Practice): M6.5 gets one probe per step of the engagement's latest map that only the documents describe ("The procedure mentions “<step>”. Where does that happen in practice?"), at most five, in process order, in the row's `held_back` list; none before a draft exists. They appear only in M6 (no SOP claims before M6).
- **Rule 7** (Follow-up; criterion 68, changed in C5d 2026-10-06): the blank reflective-probe rows are filled taking one question in turn from each of four lists, until the rows are full: the latest map's F2 probes (the SME's own words), its coverage report's follow-up questions for thin or missing dimensions (their bank ID and wording; the step they are about, if any, as the row's note "about <step>"), its open validation questions (F6), its "not described" questions (F5) and its lane-boundary findings (F4 or F1, C8), each list in its own order; an empty list is skipped; `[topics]` in the opener → the dimensions the latest map's coverage report shows as covered, when the profile names an earlier interview (profiles are not linked to sources, so the map's report stands for what earlier interviews covered).
- **Rule 8**: nothing with a banned (blaming) word or a name on the hidden-names list is filled in (left as the bracket or the blank row). Minutes and question IDs are those of the standard template (rule 6, F.9 plan).
Audit row "Made interview guide" (after: profile_id, version, interview_type, role_module: `drafted` · `left blank` · `not asked`). Errors on the POST: `404` (engagement), `422` (`details.field: "profile_id"`, a profile of another engagement or none). A failed job (`status: failed`, `error` in plain words) makes no version.

### GET /api/engagements/{id}/interview-guides
Each interviewee's latest guide, without its content (the Interviewees list, G2): `[{"id", "profile_id", "interview_type", "version", "created_at"}]`, in the order the guides were first made. `404` (engagement).

### GET /api/engagements/{id}/interview-guide?profile_id=
The latest version. `404` "No guide yet for this interviewee." when none.

### PATCH /api/engagements/{id}/interview-guide?profile_id= (C5c, 2026-10-06)
Eric's edits to the latest version, saved in place (`edited: true`; "Make new version" later starts again from the template and keeps this one as it is). Request: every section in order with every row in order, each row `{"id", "wording", "probes", "held_back"}`:
```json
{"tables": [{"label": "M0 — Framing", "rows": [{"id": "M0.1", "wording": "…", "probes": [], "held_back": []}, …]}, …]}
```
Rules (the first problem is refused with `422` naming the field, e.g. `details.field: "tables[3].rows[2].wording"`):
- Sections and rows can't be added, moved or removed (`tables`); minutes are not editable, so the minute plan still sums to the type's total.
- A question keeps its ID (`…id`) and can't be emptied (`…wording`), except Eric's own questions.
- A blank row with wording becomes Eric's own question `E1`, `E2`, … (no targets); emptying an own question makes the row blank again.
- One line each: wording up to 300 characters, at most 5 probes of up to 200; `held_back` only on rows that had held-back probes (M6.5).
- No banned (blaming) word; no name on the hidden-names list; no claim about what the documents say before M6 in a Practice guide or anywhere in a Landscape guide (a Follow-up may).
Response `200`: the guide. Audit row "Edited interview guide" (after: version, the IDs of the questions changed); nothing changed → no row. Errors `404` (engagement, or no guide yet).

### GET /api/engagements/{id}/interview-guide/export?profile_id=&format=docx|md
The latest version as a file (`document.generation_note` is not printed), in the F.9 layout (Word made with python-docx, or Markdown), the same renderer as the templates: the header table shows the filled-in values. `Content-Disposition: attachment; filename="interview-guide-practice-ramp-agent.docx"`. Errors `404` (no guide), `422` ("Choose docx or md.").
Used by: Interview screen, Interviewees: **Make guide**, then **Download Word** / **Download Markdown** (G2).

## System records: event logs (PRD §4 System records, §3.13.3, criteria 83 and 84, constraint 24) — phase P10b (2026-10-07, R3)

Importing a system's event-log extract, deterministic and without AI. The uploaded file is **held in memory only**, never written to disk or the database, until it is imported or deleted, because it may carry user IDs: the import turns them into roles and then forgets them (constraint 24). If the app restarts before the import, the file is gone and Eric uploads it again (`409 FILE_NOT_HELD`). A CSV file (UTF-8; comma, semicolon, tab or bar) or, since R11 (2026-10-13), an Excel workbook (.xlsx, recognised by its content, read in memory with openpyxl through defusedxml): its **first sheet**, the first filled row as the header (empty header cells at the end left out), each later filled row a record; date cells are written as `2026-03-02 09:14:00` (the log's time zone applies as for CSV), whole numbers without `.0`. Other sheets are not read.

### Log object
```json
{"id": "…", "engagement_id": "…", "name": "DCS extract", "system": "DCS",
 "timezone": "Asia/Singapore", "window_start": "2026-03-02" | null, "window_end": "2026-04-26" | null,
 "status": "uploaded" | "mapped" | "imported" | "failed",
 "column_map": {"case_id": "case_id", "Region": "case_attribute", "Comment": null},
 "timestamp_format": "%Y-%m-%d %H:%M:%S" | null, "file_held": true,
 "resources": [{"value": "LC07", "events": 152, "suggested_role_id": "…" | null}],
 "role_map": {"LC07": "…" | null},
 "validation_report": {…} | null,
 "approved_by_role": "", "approved_at": null, "created_at": "…"}
```
- `column_map`: every header of the file, in file order → a B.40 field or `null` (left out). Each field other than `case_attribute` at most once.
- `timestamp_format`: Eric's correction, or `null` to use the detected format (named in the report).
- `resources` and `role_map` come from memory and exist only while the file is held (empty otherwise, always empty once imported). `suggested_role_id`: the engagement role named most often for that user ID in the file's role column, else a role whose name is the value itself, else `null`. `role_map` values: a role ID or `null` (Unknown role).
- `validation_report` (§3.13.3 step 4): `{rows_read, rows_kept, cases, activities, date_from, date_to (UTC), dropped: {unparseable_time, missing_case_or_activity, duplicate}, dropped_share, single_event_cases, outside_window, unknown_role_events, timestamp_format, missing_columns, refused, refusal}`. A preview while mapping, the final report after the import. Counts only: never a row, a case's events or a user ID. A role column value that is not an engagement role or alias (matched ignoring case) is passed over for the role Eric gave that user ID, if any; otherwise the event has an unknown role.
- The upload is kept in memory by the web layer too (no temporary file, whatever its size).
- `status`: `uploaded` (suggested column map) → `mapped` (Eric confirmed it) → `imported`; `failed` when the import job could not finish (the file is then gone; upload again).

### POST /api/engagements/{id}/event-logs (multipart: file, name, system, timezone, window_start, window_end)
`name` required, `system` optional (each one line, up to 120 characters); `timezone` an IANA name, default `Asia/Singapore` (the Settings Regional default comes with R10); window dates `YYYY-MM-DD` or empty, start not after end. Response `201`: log (`uploaded`) with the suggested column map, the user IDs with suggested roles, and the preview report. Audit row "Uploaded system log" (name and system only).
Errors: `404` (engagement); `422` naming the field: "Give the log a name.", "The file is empty.", "The file is larger than 100 MB.", "The file has no header row.", "The Excel file could not be opened. Save it again as .xlsx, or as CSV, and upload it again.", "Two columns have the same name: Status. Rename one and upload again.", "Choose a time zone from the list, for example Asia/Singapore.", "Use a date like 2026-03-02.", "The window starts after it ends.".

### GET /api/engagements/{id}/event-logs
`200`: the engagement's logs, oldest first. Errors `404`.

### GET /api/event-logs/{lid} · DELETE /api/event-logs/{lid}
GET `200`: log. DELETE `204`: removes the log, its events (and, later, its metrics and alignment) and the held file; audit row "Deleted system log". Errors `404`.

### PUT /api/event-logs/{lid}/column-map
`{"columns": {header: field | null}, "timestamp_format": null | "%d/%m/%Y %H:%M", "timezone": "Asia/Singapore"}` (`timezone` optional since R7: the wizard's time-zone step; left out, the log keeps its own). Every header of the file exactly once; fields are B.40; a field other than `case_attribute` used twice is refused ("Each field can be used for one column only: timestamp."). Response `200`: log, status `mapped`, with a new preview report (which may say the import would be refused, and why). Audit row "Confirmed column map".
Errors: `404`; `409 ALREADY_IMPORTED`; `409 FILE_NOT_HELD`; `409 IMPORT_RUNNING` while its import job runs; `422` naming `columns` or `timestamp_format` ("Choose a date format from the list.").

### PUT /api/event-logs/{lid}/role-map
`{"roles": {user ID: role_id | null}}`: the file's user IDs only (others refused), each to one of the engagement's roles or `null` (Unknown role). Held in memory with the file; never saved. Response `200`: log with a new preview report (`unknown_role_events`). Errors as for the column map (`422` names `roles`: "Choose one of this engagement's roles.", "That user ID isn't in the file.").

### POST /api/event-logs/{lid}/import (job)
`{"approved_by_role": "Head of ground operations", "confirm_approval": true}`. Response `202`: `{"job_id": "…", "log_id": "…"}`. The job (`event_log_import`) reads the held file with the confirmed maps, writes the events (case, activity, start, end, role, case attributes: never a user ID), stores the final report, works out and stores the metrics (below), sets the log `imported` with `approved_by_role` and `approved_at`, then forgets the file and the role map. Audit row "Imported system log" (counts and the approver's role). If the file has gone (restart) the job fails in plain words and the log becomes `failed`.
**Progress (R12, 2026-10-13; criterion 94):** the job reports its `stage`, `progress` (0–1) and `message` as it goes, each saved on its own so `GET /api/jobs/{id}` answers throughout: `reading` (0.05, "Reading the extract and turning user IDs into roles."), `figures` (0.25, "Working out the figures from 500,000 events."), then `saving` after each batch of 25,000 events (0.35 to 0.95, "Saving events: 250,000 of 500,000."); done: progress 1.0 and "Imported 500,000 events from 100,000 cases.". The log becomes `imported` only in the last step, so a log is never shown half imported; if the job fails part-way, the events and figures saved so far are removed and the log is `failed`. Start reuses the report worked out at the last step (the file is not read again unless the column map, date format, time zone, window, user-ID roles or the engagement's roles changed). A 500,000-event log imports in well under a minute on the build machine and every metric endpoint then meets p95 < 200 ms (`tests/latency/test_large_import.py`).
Errors, checked in this order: `404`; `409 ALREADY_IMPORTED`; `409 FILE_NOT_HELD`; `409 IMPORT_RUNNING`; `409 APPROVAL_REQUIRED` without `confirm_approval: true` or without an approver's role ("Tick that the data owner approved this extract for this purpose, and give the approver's role."); `422` (field `approved_by_role`) when the role is longer than 120 characters or contains a name on the hidden-names list; `409 COLUMN_MAP_NOT_CONFIRMED` while the log is `uploaded`; `422` (field `roles`) when a user ID has neither a role nor Unknown role ("Choose a role or Unknown role for every user ID (3 left)."); `422 IMPORT_REFUSED` with the report's refusal when required columns are missing, there are no rows, or more than 20% of rows were dropped.
Used by: System records screen (R7).

### GET /api/event-logs/{lid}/metrics?scope=activity|transition|case|variant|role (R4, 2026-10-07; PRD §3.13.5, criteria 85 and 94)
The log's metrics, worked out once by the import job (§3.13.3 step 6) and stored; this endpoint only reads them. Deterministic formulas, no AI. Times in minutes (one decimal); median and 90th percentile (linear interpolation between the closest ranks); months are the log's own calendar months (its time zone).
Response `200`: `{"log_id", "scope", "minimum_cases": 5, "groups": [{"key", "label", "case_count", "metrics": {…}}], "too_few": 2}`. A group based on fewer than 5 cases is never returned, only counted in `too_few` (the screen says "too few cases to show"); a month with fewer than 5 cases is left out of `months` and counted in `months_too_few`. Role-level only: no metric ever names a person (constraint 24).
- `activity` (by events, most first): `{activity, events, cases, cases_per_week, cases_per_month, months: [{month: "2026-03", events, cases}], months_too_few, work: spread | null, wait_before: spread | null, basis, rework_cases, rework_share}`. `work` = end − start (only when the log has end times); `wait_before` = this start − the previous event's end in the case (or − its start without end times). `cases_per_week` = cases ÷ the whole weeks from the log's first to last day; `cases_per_month` = that × 52 ÷ 12. `basis`: `"wait"` with end times, `"not_separable"` without ("working and waiting (not separable)").
- `transition` (consecutive events A → B in a case; most frequent first): `{from_activity, to_activity, count, cases, elapsed: spread, basis, handoffs}`; `elapsed` = B start − A end (or − A start); `handoffs` = how many of these moves changed role (both roles known).
- `case` (one group, key `all`): `{cases, events, activities, date_from, date_to, weeks, cycle_time: spread, basis, rework_cases, rework_share, handoffs, handoffs_per_case, variants, exception_share}`; cycle time = first event start to last event end (or start); rework = cases where any activity occurs more than once; exception share = cases not following the most common variant.
- `variant` (top 10, most common first; key = rank): `{rank, activities: [...], cases, share, cumulative_share}` (shares of all cases).
- `role` (by events; key and label = the role name, or "Unknown role"): `{role, events, cases, activities: [...], work: spread | null}`.
- `spread`: `{median_min, p90_min, n}`.
Errors: `404` (log); `409 NOT_IMPORTED` ("Import the log first: its figures are worked out during the import."); `422` ("Choose activity, transition, case, variant or role.").

### Case-key maps: linking two logs (R11c, 2026-10-13; PRD §3.13.1, §4)
When two systems give the same case different IDs (a flight number in one, a turnaround reference in the other), a case-key map links their imported logs. Without one, each log is analysed on its own; with one, the app also works out the **end-to-end time across both systems** for the linked cases. Deterministic, no AI. Case IDs identify work items, not people; the map stores only the two IDs per pair.

A map object (one per linked pair of logs):
```json
{"from_log_id": "…", "from_log_name": "DCS extract", "to_log_id": "…", "to_log_name": "Ramp log",
 "pairs": 200, "from_found": 200, "to_found": 198, "linked_cases": 198,
 "end_to_end": {"median_min": 104.2, "p90_min": 131.0, "n": 198} | null,
 "basis": "wait" | "not_separable", "minimum_cases": 5, "created_at": "…"}
```
- `pairs`: distinct pairs in the file; `from_found` / `to_found`: pairs whose ID is a case of that log; `linked_cases`: pairs found in both.
- `end_to_end` (measured): per linked case, from the earliest event start in either log to the latest event end (or start) in either log, in minutes; median and 90th percentile as for the metrics. `null` when fewer than 5 cases are linked (never shown for fewer, constraint 24). `basis`: `"wait"` when both logs have end times, else `"not_separable"`.

#### POST /api/engagements/{id}/case-key-maps (multipart: file, from_log_id, to_log_id)
The file: CSV or .xlsx (first sheet), read in memory like a log extract. Its first row is the header (any names); the **first column** holds the first log's case IDs and the **second column** the second log's. Other columns are ignored and never stored; rows with either ID empty are left out, and repeated pairs count once. Both logs must be **imported** logs of this engagement and different. A new file for the same two logs (in either order) replaces the earlier map. Response `201`: the map object. Audit row "Linked system logs" (the two log names and the counts; no case ID).
Errors: `404` (engagement); `422` naming the field: (`from_log_id`/`to_log_id`) "Choose two different imported logs of this engagement."; (`file`) "The file is empty.", "The file is larger than 100 MB.", "The Excel file could not be opened. Save it again as .xlsx, or as CSV, and upload it again.", "The file needs two columns: the first log's case IDs, then the second log's.", "Give the two columns different names, for example DCS case and Ramp case.", "The file has no pairs of case IDs.".

#### GET /api/engagements/{id}/case-key-maps
`200`: the engagement's maps, oldest first. Errors `404`.

#### DELETE /api/engagements/{id}/case-key-maps?from_log_id=…&to_log_id=…
`204`: removes the map between the two logs (in either order). Audit row "Removed case-key map". Errors `404` ("Those two logs aren't linked."). Deleting a log removes its maps.

Used by: System records screen, **Linked logs** card (shown once two logs are imported).

### Alignment of log activities to map steps (R5a, 2026-10-07; PRD §3.13.4, criterion 86)
Matches the activities an imported log records to the steps of the engagement's current map (the draft, or else the latest published version). Nothing is applied until Eric confirms: the app's own matches and Claude's are only proposals, and only confirmed rows are used by the map (R5b).

#### Alignment object
```json
{"log_id": "…", "version_id": "…",
 "rows": [{"activity": "Plan created", "element_id": "…", "element_label": "Draft load plan",
           "status": "proposed", "confirmed": false, "proposed_by": "app",
           "reason": "Same words: plan. Same role: Load controller.", "events": 200, "cases": 200}],
 "summary": {"activities": 7, "matched": 6, "hidden_work": 1, "no_system_record": 5, "waiting": 12}}
```
- One row per log activity (in the log's order of volume), then one row per step that no activity is matched to, in map order (`activity: ""`, `events` and `cases` 0).
- `status` (B.43): `proposed` or `confirmed` (activity → step); `hidden_work` (an activity with no step: a *hidden work* candidate); `no_system_record` (a step with no activity: *offline / not recorded*). `confirmed` tells a decision from a proposal.
- `proposed_by`: `app` (the deterministic pass, worked out on every read and never stored), `claude` (a stored suggestion from the AI pass) or `eric` (confirmed). Several activities may be matched to one step (for example a revision activity as rework into the step it repeats); an activity is matched to at most one step.
- The deterministic pass compares words (lower case, simple word endings removed, small words ignored) between the activity name and each step's label and the SME terms linked to that step in the glossary, and adds weight when the activity's most frequent role is the step's lane role. The best step is proposed when the match is strong enough (shared words over the shorter name, plus 0.25 for the same role, more than 0.5); otherwise the activity is proposed as hidden work. `reason` says which words and role matched.
- `summary.waiting`: rows still waiting for Eric's decision.
- Confirmed rows survive a new map version: they are matched to the new version's steps by the step's stable key; a confirmed row whose step no longer exists drops back to a proposal.

#### GET /api/event-logs/{lid}/alignment
`200`: alignment. Errors: `404` (log); `409 NOT_IMPORTED`; `409 NO_MAP` ("Draft the map first: the log's activities are matched to its steps.").

#### PUT /api/event-logs/{lid}/alignment
`{"rows": [{"activity": "Plan created", "element_id": "…", "status": "confirmed"}, {"activity": "Manual weight override", "element_id": null, "status": "hidden_work"}, {"activity": "", "element_id": "…", "status": "no_system_record"}]}`: Eric's decisions, each replacing any earlier decision or suggestion for that activity (or, for `no_system_record`, that step). `confirmed` needs an activity of the log and a step of the current map; `hidden_work` an activity and no step; `no_system_record` a step and no activity. A step can't be both matched and marked as having no system record ("Issue load sheet has a system record: Load sheet issued is matched to it."). Response `200`: alignment. Audit row "Confirmed system alignment" (the decisions as activity → step label). Errors: as GET, plus `422` naming `rows` ("That activity isn't in the log.", "Choose a step of the current map.", "Choose confirmed, hidden_work or no_system_record.").

#### POST /api/event-logs/{lid}/alignment/suggest (AI job)
Claude's pass (`SR_align`) for the activities the deterministic pass could not match and Eric hasn't decided. Claude sees only those activity names (with volumes and their most frequent role), the current map's steps (stable key, label, kind, lane role) and the glossary terms, names on the hidden-names list replaced; no events, no case IDs, no figures per person. Each suggestion must name an activity that was sent and a step that exists, with a reason; any other is left out (counted in the job message, never shown). Kept suggestions are stored as `proposed_by: "claude"` proposals, replacing earlier ones for those activities; confirmed rows are never touched. Response `202`: `{"job_id", "log_id"}`; the job (`event_log_alignment`) ends with a message such as "Claude suggested 1 match. 1 suggestion was left out: it named an activity or step that isn't in the log or on the map.". AI usage is shown on the job like the gap analyses.
Errors: `404`; `409 NOT_IMPORTED`; `409 NO_MAP`; `409 NOTHING_TO_SUGGEST` ("Every activity already has a match or a decision."); the job fails in plain words without a key, when Anthropic is busy or after a format failure (nothing saved).
Used by: System records screen (R7).

### System trace on the map (R5b, 2026-10-07; PRD §3.13.4, §3.12.7, Appendix E tier 2, criterion 87)
What Eric's **confirmed** alignment rows (any imported log of the engagement) do to a map. Deterministic, no AI. A draft reflects the current confirmed alignment every time it is read; publishing freezes what the draft showed into the published version (stored), so a published version never changes afterwards. Unconfirmed proposals and Claude's suggestions never change a map. A step with no system record is the system being **silent**: it never contradicts anything (constraint 4).
- **Edges** (`GET /versions/{vid}/graph` and everything built on it: layout, lint, exports): a line from step A to step B, both matched, gets `sequence_basis: "system_trace"` (B.34, now the strongest basis) when the log records an activity of A directly followed by an activity of B in at least 5 cases, and in more cases than the reverse.
- **Contradiction:** when the log records B directly followed by A in at least 5 cases and more often than A followed by B, the line's order is contradicted: B's `source_state` becomes `trace_contradicted` (when it had any support) and `sequence` is added to its `divergence_types`; the line keeps its own basis.
- **Corroboration:** a matched step recorded in at least 5 cases is supported by the trace layer: `practiced_only` and `documented_only` become `corroborated` (the trace confirms the account). Other states are unchanged.

#### GET /api/versions/{vid}/system-traces
The system-trace evidence of a version's steps (no quotes: a trace is figures, not words). `200`: `[{"element_id", "label", "stance": "supports" | "contradicts", "log_id", "log_name", "system", "window_start", "window_end", "cases", "events", "cases_per_week", "rework_cases", "rework_share", "activities": [{"activity", "cases", "events", "work": spread | null, "wait_before": spread | null, "basis"}], "note"}]`, one item per step and log, in map order. Only steps recorded in at least 5 cases are listed. `cases` = cases with any activity matched to the step; `rework_cases` = cases where those activities occur more than once (on A.11, Draft load plan: `Plan created` then `Plan revised`, 40 cases, 20%); `note` gives a contradiction in words ("The system records Special loads OK? before Draft load plan in 6 cases."). Errors `404`.
Used by: panel section 4e and the Volume and wait lens (R8).
- **Step summary (R8, 2026-10-08; added fields, older frozen items read them as empty):** `"cases_per_month"` (cases per week × 52 ÷ 12), `"main_activity"` (the step's activity in the most cases), `"work"` and `"wait_before"` (that activity's spreads, or `null`), `"basis"` (its time basis), `"variants"` (how many of the log's top variants, each of at least 5 cases, pass through any of the step's activities) and `"variant_share"` (the share of all cases those variants hold). The Volume and wait lens reads `cases_per_month` and `wait_before.median_min`; panel 4e reads them all and sets the step's stated times (SME, documented) beside the measured median work.

#### GET /api/versions/{vid}/system-variants (R8, 2026-10-08; PRD §5.6 Variants tab, §3.13.4, criterion 89)
The system's variants of each imported log, read through Eric's **confirmed** matches and compared with the version's As done and As documented paths; and each log's hidden work. Deterministic, no AI, figures from the stored metrics only (top 10 variants, each of at least 5 cases). Advisory: nothing here changes the map. Worked out on every read, for drafts and published versions alike (the comparison uses the version's own steps, matched by stable key).
`200`:
```json
{"logs": [{"log_id": "…", "log_name": "DCS extract", "cases": 200, "too_few": 0,
           "variants": [{"rank": 1, "cases": 141, "share": 0.705, "cumulative_share": 0.705,
                         "path": [{"activity": "Plan created", "element_id": "…", "label": "Draft load plan", "status": "matched"},
                                  {"activity": "Manual weight override", "element_id": null, "label": "", "status": "hidden_work"}],
                         "views": {"done": {"fits": true, "notes": []},
                                   "documented": {"fits": false, "notes": ["Busy wave? isn't in the As documented view."]}}}],
           "hidden_work": [{"activity": "Manual weight override", "cases": 23, "share": 0.115, "role_id": "…" | null,
                            "after_element_id": "…" | null, "after_label": "Deviation in limits?",
                            "before_element_id": "…" | null, "before_label": "Issue load sheet"}]}],
 "too_few_steps": ["…"]}
```
- `path`: the variant's activities in order; `status` `matched` (Eric confirmed a step), `hidden_work` (confirmed as no step) or `not_matched` (no decision yet).
- `views.<view>.fits` is true when every matched step is in that view and, for each two steps one after the other on the path (a step repeated straight after itself counts once), the view's lines lead from the first to the second. `notes` say in words what doesn't fit: "X isn't in the As done view.", "The As done view has no way from X to Y.", "Z is hidden work: no step on the map.", "Z isn't matched to a step yet.". A variant with no matched step has `fits: false` and the note "No activity of this variant is matched to a step yet.".
- `hidden_work`: the activities Eric confirmed as hidden work that are recorded in at least 5 cases, with the share of the log's cases, the engagement role that records it most (`role_id`, from the import's role mapping), and the matched steps it most often directly follows and precedes. Used to fill in **Add as step**.
- `too_few_steps`: steps with a confirmed match recorded in fewer than 5 cases in every log (the lens says "too few cases"; no figure is given).
Errors `404`. Used by: the Variants tab and the Volume and wait lens (R8).

## Step disposition (PRD §3.15, criterion 91, constraint 7) — phase P10b (2026-10-08, R9a)

Every step gets a disposition (B.41): `delete` (Delete) · `automate_rules` (Automate (rules)) · `ai_assisted` (AI-assisted) · `human_approves` (Human approves) · `keep_human` (Keep human). The app **suggests** one deterministically, with its reason, every time it is read (no AI; nothing stored); Eric **chooses** (drafts only), and his choice is kept: it is copied when a version is reopened and carried to the redrafted step when a draft is refreshed (like a confirmed work type). Dispositions feed the value calculator (R9b), the AI-flag register, the leadership Recommendation panel and the Master Process Map (R10).

**Suggestion rules**, the first that applies:
1. **Delete** — a kept gap finding on the step (not dismissed) of type `dead_control_candidate` or with gap class `obsolete_rule` ("Gap finding: <title>."); or a documented-only decision or approval that Eric confirmed has no system record in an imported log and that has no KPI and no constraint (no stated purpose): "The documents describe it, no interview mentions it, the <log> log has no record of it and no purpose is stated."
2. **Keep human** — work type complex or chaotic ("<Complex> work: it needs human judgment."); or knowledge risk High with heuristics or experience at least half of its know-how items ("High knowledge risk, mostly heuristics and experience.").
3. **Human approves** — an approval ("An approval: a person authorises it."); or a step with a risk flag ("Carries a <financial> risk: a person authorises it.").
4. **AI-assisted** — work type complicated ("Complicated work: an AI agent can prepare it with expert oversight."); or a clear activity whose AI flag reads its input (component `perception`: "Clear work that needs documents read: …").
5. **Automate (rules)** — work type clear and, for a decision, rule-based ("Clear, rule-based work.").
6. Otherwise **Keep human** ("Work type not confirmed yet: kept human until it is.").
For AI-assisted and Automate the reason adds " Needs a complete AI flag before you can choose it." when the step has none (L10).

### GET /api/versions/{vid}/dispositions
`200`: one row per step (start and end left out; rejected steps too) in map order:
```json
[{"element_id": "…", "label": "Approve load plan", "kind": "approval", "suggested": "delete",
  "reason": "The documents describe it, …", "disposition": null, "note": "", "risk_flag": "none",
  "allowed": ["delete", "human_approves", "keep_human"],
  "not_allowed": [{"disposition": "automate_rules", "reason": "Complex work can't be automated or AI-assisted."}]}]
```
`disposition` is Eric's choice (or `null`); `allowed` lists what he may choose for this step (the rules below); `not_allowed` (R10b, 2026-10-13) gives each other disposition with the reason it is refused, in B.41 order, so the panel explains instead of disabling a choice. Errors `404`.

### PUT /api/elements/{eid}/disposition
`{"disposition": "human_approves" | null, "note": "…", "risk_flag": "none" | "financial" | "safety" | "regulatory"}` (`risk_flag` optional: left out, it keeps its value; `null` disposition clears Eric's choice). Rules (`422` naming the field):
- a step of a **draft** (`409` otherwise), not the start or the end;
- `disposition` one of B.41 ("Choose one of the five dispositions.");
- `automate_rules` and `ai_assisted` are refused for complex or chaotic work ("<Complex> work can't be automated or AI-assisted.") and need a complete AI flag: component, input, output, handoff and basis ("Add a complete AI flag first: component, input, output, handoff and basis.");
- `automate_rules` is refused on a judgment decision or approval ("A judgment step can't be automated by rules.", constraint 7);
- `note` one line, up to 300 characters, no name on the hidden-names list.
Response `200`: the step's row as in `GET …/dispositions`. Audit row "Chose disposition" (before and after: disposition, note, risk flag; and the suggestion at the time). The stored lint report is refreshed.
**Lint L10** (hard failure) now also fails a step whose chosen disposition is `automate_rules` or `ai_assisted` without a complete AI flag, or on complex or chaotic work.

## Value calculator (PRD §3.14, criterion 90, constraint 24) — phase P10b (2026-10-08, R9b)

Indicative hours and cost per step and phase, and what each disposition could release. Deterministic, no AI. Every figure carries its evidence label (B.42: `measured` · `estimated` · `mixed` · `assumed`); scenarios are labelled "Potential, not committed"; money is per step, phase and disposition, never per person. The currency is the `CURRENCY` setting (default `SGD`; the Settings Regional card comes with R10).

### GET · PUT /api/engagements/{id}/role-costs
GET `200`: `{"currency": "SGD", "rows": [{"role_id", "role_name", "hourly_cost": 48.0 | null, "note"}]}`, one row per role of the engagement (not the system roles), in lane order. PUT `{"rows": [{"role_id", "hourly_cost": 48.0 | null, "note": ""}]}`: each row replaces that role's cost (`null` removes it); roles left out keep theirs. Rules (`422` naming the field): a role of this engagement ("Choose one of this engagement's roles."); a loaded hourly cost of 0 to 100,000 ("Give an hourly cost from 0 to 100,000."); `note` one line, up to 200 characters, no name on the hidden-names list. Response `200`: as GET. Audit row "Set role costs" (role names and costs). Errors `404`. Used by: Registers, "Disposition and value" (Role costs form, R10c).

### GET · PUT /api/engagements/{id}/value-assumptions
GET `200`: the five dispositions in B.41 order: `[{"disposition": "automate_rules", "reduction_pct": 80.0, "note": "", "default": true}]` (defaults: Delete 100 · Automate (rules) 80 · AI-assisted 50 · Human approves 30 · Keep human 0). PUT `{"rows": [{"disposition", "reduction_pct", "note"}]}`: each row replaces that disposition's assumption; `reduction_pct` 0 to 100 ("Give a reduction from 0 to 100 percent."). Response `200`: as GET. Audit row "Set value assumptions". Errors `404`, `422`. Used by: Registers, "Disposition and value" (Assumptions form, R10c).

### PUT /api/elements/{eid}/value-override
`{"time_min": 12.0 | null, "volume_month": 400.0 | null, "note": "From the shift roster"}`: Eric's own time per case and volume per month for a step (provenance `R`, used only where nothing is measured or stated, §3.14's order). A step of a draft (`409` otherwise), not the start or end; `time_min` above 0 and at most 10,000 minutes, `volume_month` above 0 and at most 1,000,000; a note is required while either is set ("Say where the figure comes from."), one line up to 300 characters, no hidden name. `null` for both clears them. Response `200`: the step's value row as in `GET …/value`. Audit row "Set value override". Kept on refresh and reopen like the disposition.

### GET /api/versions/{vid}/value?view=done|documented
Default `done`. `200`:
```json
{"currency": "SGD", "view": "done", "potential": "Potential, not committed",
 "steps": [{"element_id", "label", "phase_id", "phase_name", "role_name",
            "time": {"value": 23.9, "label": "measured", "source": "DCS extract: median work 19.9 min, 1.2 times per case"} | null,
            "volume": {"value": 108.3, "label": "measured", "source": "DCS extract: 25 cases a week"} | null,
            "hours_per_month": 43.1 | null, "cost_per_month": 2068.8 | null, "evidence": "measured" | null,
            "missing": ["No hourly cost for Load controller."],
            "disposition": "ai_assisted", "chosen": false, "reduction_pct": 50.0,
            "hours_released": 21.6 | null, "cost_released": 1034.4 | null}],
 "phases": [{"phase_id", "name", "hours_per_month", "cost_per_month", "evidence", "steps_counted", "steps_missing", "steps_without_cost"}],
 "totals": {"hours_per_month", "cost_per_month", "evidence", "steps_counted", "steps_missing", "steps_without_cost"},
 "scenarios": [{"disposition", "reduction_pct", "steps", "hours_per_month", "hours_released", "cost_released"}]}
```
- **Time per case** (minutes of work): measured = the step's main activity's median work × how many of its activities a case has (events ÷ cases; rework counts), from the busiest log matched to it; else the SME's estimate = the step's stated work minutes (from its verified evidence) → `estimated`; else Eric's override → `assumed`.
- **Volume per month**: measured = the step's cases per month from the system records; else Eric's override → `assumed` (no source states volumes).
- **Hours per month** = time × volume ÷ 60 (one decimal); **cost per month** = hours × the lane role's hourly cost (none when the role has no cost: `missing` says so). The step's `evidence` is the inputs' label when they agree, else `mixed`; a phase's and the total's likewise over the steps counted. A step without both inputs has no figure and says what is missing; a phase's and the total's cost sum only the steps with a role cost, and `steps_without_cost` says how many counted steps have hours but no cost (so a partial cost is never shown as the whole).
- **Scenarios**: each step's disposition (Eric's choice, else the suggestion; `chosen` says which) × that disposition's reduction gives the hours and cost it could release; per disposition, summed. Always labelled potential.
- Steps of the view only (start, end and rejected steps left out). Errors `404`, `422` (`view`).
- Used by: the step panel's "Disposition and value" section (R10b) and the Registers' "Disposition and value" list (R10c; As done / As documented switch), only while `value_enabled`.

## Intent (PRD §3.16, §4 Intent and Reality, constraint 25, G16) — phase P13a (2026-10-13)

What the organisation intends: quoted from a `policy_or_charter` source (proposed by S1 intent, P13a-2) or stated by an owner and typed in by Eric. Intent is evidence: it is never drawn from interviews, never inferred from what the process does, and never invented. Nothing proposed counts until Eric confirms it. The Reality views module switch (`reality_views_enabled`, `REALITY_VIEWS_ENABLED`, off by default, decision A) hides the screens; these endpoints work whatever it says, like the other modules' endpoints.

Sources of kind `policy_or_charter` (B.1; guessed from a file name containing "charter" or "policy") are read like any document but are **never drafted from**: the draft and refresh leave them out (they state intent, not how the process runs), so they don't count for source state, readiness or signal strength.

### Intent statement object
```json
{"id": "…", "engagement_id": "…", "scope": "step", "element_stable_key": "…", "element_label": "Approve load plan",
 "phase_name": null, "kind": "control_objective", "origin": "document",
 "text": "Every load plan is approved before release to Ramp.",
 "metric": null, "comparator": null, "target_value": null, "unit": null,
 "source_id": "…", "source_name": "charter_load_control.docx", "anchor": "§2", "quote": "Every load plan is approved before release to Ramp.",
 "owner_role_id": null, "owner_role_name": "", "stated_on": null,
 "label": "Quoted from charter_load_control.docx §2",
 "verification_status": "verified", "rejection_guardrail": null, "status": "confirmed", "note": "", "created_at": "…"}
```
- `scope` `process` · `phase` (with `phase_name`) · `step` (with `element_stable_key`; `element_label` from the current map, `""` when the step isn't on it any more). `kind` B.44; `origin` B.45; `metric` B.49 or `null`, then `comparator` `at_most` · `at_least` · `equals`, `target_value` (a number) and `unit` `min` · `pct` · `count` (all four set or all `null`).
- `label`: "Quoted from <file> <anchor>" for a document, "Target set by <role>, <d Mon yyyy>" for an owner-stated statement (never presented as a quote).
- `text`, `quote`, `label` and `source_name` are shown with names hidden (G10). `verification_status` B.18 (owner-stated: `verified`); `rejection_guardrail` B.20 for a proposal the checks turned down (it can't be confirmed). `status` `proposed` · `confirmed` · `dismissed` (owner-stated statements start `confirmed`: Eric typed them).

### GET /api/engagements/{id}/intent
`200`: the engagement's statements, oldest first, every status. Errors `404`.

### POST /api/engagements/{id}/intent (owner-stated)
`{"scope": "step", "element_stable_key": "…", "phase_name": null, "kind": "policy_rule", "text": "Weight deviations outside tolerance are decided by the Load control lead.", "metric": null, "comparator": null, "target_value": null, "unit": null, "owner_role_id": "…", "stated_on": "2026-10-01"}`. Rules (`422` naming the field): `kind` B.44 ("Choose promise, target, control objective or policy rule."); `scope` ("Choose process, phase or step."); a step scope needs a step of the current map ("Choose a step of the current map."), a phase scope a phase of it ("Choose a phase of the current map."); `text` 1 to 200 characters on one line ("Describe the intent in one line of up to 200 characters.") with no name on the hidden-names list ("Use role names, not people's names."); `metric` B.49; with a metric, `comparator`, `target_value` (0 or more) and `unit` are all required and the unit fits the metric (`*_min` → `min`, `*_pct` → `pct`) ("Give the comparison, the target value and its unit."); without one, all three are left out ("A target value needs a metric."); `owner_role_id` a role of this engagement ("Choose the owner's role."); `stated_on` a date `YYYY-MM-DD`, not in the future ("Give the date the target was set, for example 2026-10-01."). Response `201`: the statement (`origin: "owner_stated"`, `status: "confirmed"`, `verification_status: "verified"`). Audit row "Added intent statement".

### PATCH /api/intent/{iid}
`{"status": "confirmed" | "dismissed" | "proposed", "note": "…", "edits": {"text"?, "scope"?, "element_stable_key"?, "phase_name"?, "kind"?, "metric"?, "comparator"?, "target_value"?, "unit"?, "owner_role_id"?, "stated_on"?}}` (each part optional). Edits follow the POST rules; for a document statement a target value must appear in its quote ("The target value must be in the quoted text.", G5) and the owner and date can't be set. A statement turned down by the checks can't be confirmed (`409` "This statement failed the checks, so it can't be used. Add it yourself as an owner-stated target if it holds."). `note` one line, up to 300 characters. Response `200`: the statement. Audit row "Confirmed intent statement" · "Dismissed intent statement" · "Edited intent statement" (before and after). Errors `404` ("That intent statement doesn't exist."), `409`, `422`.

### DELETE /api/intent/{iid}
`204` for an owner-stated statement. A statement quoted from a document is dismissed instead, so it stays on record (`409` "Dismiss a statement quoted from a document instead; it stays on record."). Audit row "Deleted intent statement". Errors `404`.

### POST /api/engagements/{id}/intent/extract (AI, job; PRD §3.16, G16) — P13a-2
Claude's pass (`S1_extract_intent`) over each ready `policy_or_charter` source, and over the purpose clauses of ready SOPs and manuals (passages containing "to ensure", "so that" or "in order to"); one call per source. Claude sees only those passages (names hidden), the current map's steps (stable key, label) and phase names; never an interview. Each proposal carries `kind`, `text`, a `scope` (with `element_stable_key` or `phase_name`), optionally `metric`, `comparator`, `target_value` and `unit`, the cited passage refs and a verbatim `quote`.
- Checks (G16), in order: G3 the cited passages were sent with that source; G4 the quote is found in them; G5 every number in the text, and the target value, is found in the quote, and every role named is found in the passages; a target is all four fields or none, its unit fits the metric, the text is one line of up to 200 characters. A proposal failing a check is **rejected** with that guardrail. A scope naming a step or phase not on the current map covers the process instead.
- Then `IX_verify` (when the verifier is on in Settings): `not_supported` → rejected `IXV`.
- Stored as document statements: kept ones `status: "proposed"`, `verification_status: "verified"`; rejected ones `verification_status: "rejected"` with `rejection_guardrail`, listed so Eric sees what was turned down (they can't be confirmed). A rerun replaces earlier document statements that are still proposed; confirmed and dismissed ones are never touched, and a proposal repeating one of them (same source and text) is not added again.
- Response `202`: `{"job_id", "engagement_id"}`; the job (`intent_extract`) ends with a message such as "Claude proposed 6 intent statements: 4 passed the checks; 2 were turned down and are listed as rejected.". AI usage is shown on the job.
- Errors: `404`; `409` "Add a policy or charter and wait for it to be read first." when no ready source has anything to read.

### POST /api/versions/{vid}/intent/compare (AI, job; PRD §3.16 design gaps, G16) — P13a-2
Claude's pass (`IX_compare`) pairing **confirmed** intent statements with the documented process: the statements (text, and quote or owner label) and the passages of the engagement's ready SOPs and manuals, names hidden. Each proposal names one statement, the documented passages, a quote from each side and the conflict in at most 25 words.
- Checks (G16): `IX1` both quotes are given and the conflict is 1 to 25 words; G3 the statement was sent and is confirmed, and the documented passages were sent; G4 the intent quote is found in the statement's quote (its text for an owner-stated statement) and the documented quote in the cited passages; G5 every number and role in the conflict is found on one of the two sides. Then `IX_verify` (verifier switch): `not_supported` → rejected `IXV`.
- Stored on the version as proposals (rejected ones too, with the guardrail); a rerun replaces this version's proposals that are still proposed; confirmed and dismissed ones are kept, and a proposal for the same statement and passages is not added again. A proposal counts (D13) only after Eric confirms it.
- Response `202`: `{"job_id", "version_id"}`; the job (`intent_compare`) ends with a message such as "Claude proposed 1 design gap: it passed the checks." or "… 1 was turned down and is listed as rejected.".
- Errors: `404` ("That version doesn't exist."); `409` "This version is published and can't be changed. Reopen it as a new draft." · "Confirm at least one intent statement first." · "Add an SOP or manual and wait for it to be read first.".

### GET /api/versions/{vid}/intent/conflicts — P13a-2
`200`: the version's design-gap proposals, oldest first, every status:
```json
{"id": "…", "version_id": "…", "intent_id": "…", "intent_text": "Screening is proportionate to the client's risk tier.",
 "intent_label": "Quoted from policy_screening.docx §2", "intent_quote": "Screening is proportionate to the client's risk tier.",
 "segment_ids": ["…"], "source_name": "sop_KYC-01.docx", "anchor": "§3.1", "quote": "Every case is screened in full.",
 "conflict_text": "The policy screens by risk tier; the SOP screens every case in full.",
 "verifier_verdict": "supported", "verification_status": "verified", "rejection_guardrail": null,
 "status": "proposed", "note": "", "created_at": "…"}
```
`source_name` and `anchor` are the first documented passage's. Text fields are shown with names hidden (G10). Errors `404`.

### PATCH /api/intent-conflicts/{cid} — P13a-2
`{"status"?: "confirmed" | "dismissed" | "proposed", "note"?: "…"}`. A proposal the checks turned down can't be confirmed (`409` "This design gap failed the checks, so it can't be used."). `note` one line, up to 300 characters ("A note is one line of up to 300 characters."). Response `200`: the conflict. Audit row "Confirmed design gap" · "Dismissed design gap" · "Reopened design gap" · "Noted design gap". Errors `404` ("That design gap doesn't exist."), `409`, `422`.

## Discrepancies (PRD §3.17, §4 Intent and Reality, constraint 26) — phase P13a

Every difference between intent, documents, belief and practice on a version, worked out by fixed rules from facts the app holds (`REALITY_RULES_VERSION`, G15); no AI call is made. Like the intent endpoints, these work whatever the Reality views switch says.

### GET /api/versions/{vid}/discrepancies?view=done
`200`:
```json
{"rules_version": "1", "view": "done",
 "items": [
  {"item_id": "…", "code": "X1", "status": "seen", "types": ["D1", "D11"],
   "location": {"kind": "step", "keys": ["approve-load-plan"]}, "title": "Approve load plan",
   "delta": {"value": 100.0, "unit": "pct", "kind": "measured", "label": "never recorded; 100% of cases"},
   "deltas": [{"type": "D1", "value": 100.0, "unit": "pct", "kind": "measured", "label": "never recorded; 100% of cases"},
              {"type": "D11", "value": 100.0, "unit": "pct", "kind": "measured", "label": "Approve load plan: 100% of cases without a record"}],
   "incidence": 1.0, "cases": 200, "hours_per_month": 0.0, "shown": true,
   "impact_class": "control_exposure", "impact_note": "potential control exposure, for the control owner to confirm",
   "verdict": {"suggested": "correct", "reason": "The control objective is not met: restore the control or remove the cause.",
               "decided": null, "note": "", "decision_owner_role_id": null},
   "evidence": {"documents": 1, "interviews": 0, "system_cases": 200},
   "element_ids": ["…"], "intent_ids": ["…"]}],
 "intents": [{"intent_id": "…", "result": "not_met", "actual": null, "label": "measured", "met_share": 0.0, "cases": 200,
              "documented": null, "documented_meets": null}]}
```
- `view`: `done` only (the As done view; a `documented` value is refused with `422` "Discrepancies are worked out on the As done view.").
- `items`: one per location, in code order, then the process-level types (D9 parallel routes, D10 belief gap) with `code: null`, `impact_class: null` and no verdict. `location.kind`: `step` · `run` (a contiguous run of added steps) · `activity` (a hidden-work log activity; `keys` holds its name) · `order` (D3, two steps) · `design` (D13, always its own code) · `process`.
- `code`: `X1`, `X2` … given the first time a location is seen in the engagement, in order of impact class, then hours a month, then process order; kept for that location in every later version and never reused. A location coded earlier but not found now is listed with `status: "not_seen"` (no figures). Locations not drawn (below 5% of cases and not a control exposure) get no code and are left out.
- `delta`: the first type's figure; `deltas` every type's. `kind` is the figure label (B.50). `hours_per_month`: hours the discrepancy accounts for, from measured figures only (0 when none).
- `impact_class` B.46; `impact_note` "potential control exposure, for the control owner to confirm" on control exposures. `verdict.suggested` B.47 with its reason; `verdict.decided` Eric's verdict, which always wins.
- `intents`: each confirmed statement's evaluation (§3.16): `met` · `not_met` · `unknown`.
- Errors: `404` ("That version doesn't exist.").

### PUT /api/discrepancy-items/{item_id}/verdict
`{"verdict": "codify" | "correct" | "rewrite" | "ask" | null, "note": "…", "decision_owner_role_id": "…" | null}`. `null` clears Eric's verdict (the suggestion shows again). Rules (`422` naming the field): `verdict` ("Choose codify, correct, rewrite or ask."); `note` one line, up to 300 characters ("A note is one line of up to 300 characters."); `decision_owner_role_id` a role of this engagement ("Choose the decision owner's role."). Response `200`: `{"item_id", "code", "verdict_decided", "verdict_note", "decision_owner_role_id"}`. Audit row "Decided discrepancy verdict" (before and after). Errors `404` ("That discrepancy doesn't exist."), `422`. The path uses the item's ID (`item_id` in the GET) because codes repeat across engagements.

## Readiness (PRD §4, §5.3 guided navigation, §5.4 Draft checklist) — phase P1

### GET /api/engagements/{id}/readiness
Response `200`:
```json
{"key_set": true, "transcripts_ready": false, "documents_ready": true,
 "speakers_unmapped": 0, "draft_exists": false, "blockers_count": 0,
 "nav": {"setup": "done", "interview": "done", "sources": "attention", "draft": "not_started", "review": "not_started",
         "published": "not_started", "matrix": "not_started", "gap_analysis": "not_started",
         "registers": "not_started", "leadership": "not_started", "exports": "not_started"},
 "nav_counts": {"sources": 1},
 "next_step": "sources",
 "missing": ["Add an interview transcript"],
 "recommended": [],
 "signal": null,
 "ready_to_draft": false}
```
- `transcripts_ready`: at least one `interview_transcript` source has `text_status: "ready"`.
- `documents_ready`: at least one SOP, manual, executed artefact or other document is ready (a job description alone doesn't describe the steps).
- `speakers_unmapped`: speaker labels in ready transcripts with no role and not marked Interviewer.
- `blockers_count`: failing hard checks on the current draft's quality card (phase P7; `0` without a draft), worked out when asked.
- `missing`: plain-language list of what the draft still needs, in this order: API key · interview transcript · a process document still being read ("Wait for the process document to be read (…)") · each transcript with unmapped speakers ("Map 1 speaker in interview_transcript.txt"). Empty when `ready_to_draft` is true. File names are shown with names hidden.
- `recommended` (from P12, Eric's decision 2026-09-29): what would make the map stronger but doesn't stop the draft: "Add a process document such as an SOP or manual" (or the job-description variant, or a document that couldn't be read). A draft from interviews alone is allowed.
- `signal`: the signal strength of a draft made now, from the ready sources (`null` until an interview transcript is ready): `{"level": "strong" | "moderate" | "limited", "label": "Strong" | "Moderate" | "Limited", "score": 3 | 2 | 1, "detail": "…"}`. **Strong**: an interview and an SOP or manual. **Moderate**: an interview with only job descriptions, executed artefacts or other documents. **Limited**: interview transcripts only ("Built from interviews only. Every step is 'practiced only': confirm it with a document or another SME before relying on it.").
- `nav` status rules: **setup** done when trigger and end point are filled, otherwise not started. **interview** (PRD v1.10 §5.3, nav order Setup · Interview · Sources …; from 2026-09-30) done once an interview transcript has been uploaded (the interview has happened), otherwise not started; never attention. Until tailored guides exist (phase P4c) the Interview screen offers the standard templates. **sources** not started with no files; done when nothing source-related is missing and no file failed; otherwise attention, with `nav_counts.sources` = source items missing + failed files. **draft** done once a map version exists. **review** not started without a draft; done when every element of the latest version is reviewed and there are no blockers; otherwise attention with the number of elements left plus blockers. **published** and **leadership** done once a version is published. **matrix** and **registers** done once a draft exists (their content exists). **gap_analysis** done once a report is finalised. **exports** done once anything was exported (P7).
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
`status`: `queued` · `running` · `done` · `failed` (with a plain `error`). `type`: `read_source` (P2) · `draft` (P3) · `refresh` (P6) · `gap_internal` and `gap_external` (P10; `target_id` the analysis, `usage` its AI calls, `stages` as in Gap analysis) · `interview_guide` (P4c) · `event_log_import` and `event_log_alignment` (P10b) · `intent_extract` (P13a; `target_id` the engagement) and `intent_compare` (P13a; `target_id` the version), each with `usage`. `target_id`: the source ID for `read_source`; for `draft`, the version being built (`null` until the job starts).
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
- An audit row "Refreshed draft from sources" records the labels before and after, how many steps were kept, the run records before and after (below) and `changes` (below).
- **What the refresh changed (anti-drift, 2026-09-30):** among the steps Eric hadn't reviewed, compared by step key with the draft before the refresh: `{"kept": 4, "new_steps": ["Check fuel figures"], "no_longer_drafted": ["Brief the crew"], "renamed": [{"before": "Issue load sheet", "after": "Issue final load sheet"}]}` (activities, decisions and approvals only; labels in process order, names hidden). It is in the audit row's `after.changes`, in the job's message, and on `GET /engagements/{id}/draft` as `last_refresh` so the Draft screen shows it.
Errors: `404` ("That version doesn't exist."); `409` "Only the current draft can be refreshed." · "A draft map is already being made." · "The draft can't start yet: …" (readiness). Used by: Draft screen and Review (P6).

**Run record (anti-drift, 2026-09-30).** Every draft and refresh stamps its version with how it was made: `{"model": "claude-…", "effort": "high" | null, "verifier": true, "instructions": {"S1_extract_interview": "1", …, "question_bank": "1.0"}, "app_version": "1.0.0"}` — `effort` as used (`null` when the model has no effort setting), `verifier` whether the independent verifier (S3b) ran, `instructions` the version of every stage prompt and of the question bank (each version pinned to its wording by the instruction lock). A draft made before this record existed has none (`null`).

### GET /api/versions/{vid}/refresh-check
What a refresh would do differently from the run that made this version, so drift between runs made at different times is visible before Eric starts one (warn, never block). Request: none; no AI call (the model's own capabilities aren't looked up).
Response `200`:
```json
{"made_with": {"model": "claude-opus-5-5", "effort": "high", "verifier": true,
               "instructions": {"S1_extract_interview": "1"}, "app_version": "1.0.0"},
 "now": {"model": "claude-sonnet-5-5", "effort": "high", "verifier": false,
         "instructions": {"S1_extract_interview": "1"}, "app_version": "1.0.0"},
 "changes": ["The model changed: this draft was made with claude-opus-5-5; a refresh now uses claude-sonnet-5-5.",
             "The independent verifier checked this draft, but it is now switched off in Settings, so fresh suggestions would reach the map without that second check."]}
```
`made_with` is the version's run record (`null` for a version drafted before run records existed, with `changes` then holding one line saying it can't be compared); `now` is what a refresh would use from Settings and the app's instructions today (`effort` as set in Settings); `changes` is `[]` when both match. Effort is compared only when both are known. Errors: `404` ("That version doesn't exist."). Used by: the Refresh draft dialog on Review.

### GET /api/engagements/{id}/draft
The latest draft job and the current draft, so the Draft screen can pick up a running job after a reload.
Response `200`:
```json
{"job": {"…": "job object as GET /api/jobs/{job_id}"},
 "version": {"id": "…", "label": "v0.1", "state": "draft", "created_at": "…"},
 "summary": {"steps": 8, "needs_check": 0, "verified": 21, "rejected": 0,
             "open_questions": 5, "scrubbed": 0},
 "last_refresh": null}
```
`job` is `null` before the first draft; `version` and `summary` are `null` without a draft. `steps`: activities, decisions and approvals on the draft; `needs_check`: steps the independent verifier found only partly supported; `verified` / `rejected`: claims; `open_questions`: validation questions still open (including every gap Claude raised); `scrubbed`: names replaced by roles in Claude's answers.
`job` is the newest draft or refresh job. `last_refresh` (2026-09-30): what the refresh changed, as in the refresh audit row's `after.changes`, when `job` is a finished refresh of the current draft; otherwise `null`. Errors: `404`. Used by: Draft screen.

### GET /api/versions/{vid}/graph
The version's map as the graph of PRD §3.6 (also the future `.json` export): `version`, `process` (name, trigger, end point, KPI, `cycle_time: {elapsed_min, work_min, incomplete_steps}` along the usual route — X5, 2026-10-06: no exception exit, loop back or variation step; where the usual route splits, the longest way in minutes, then in steps; the combined map uses the As done view's), `roles`, `phases`, `elements`, `edges` (`from`, `to`, `kind`, `label`, `sequence_basis`, `view_membership`, `information_payload`, `typical`, `provenance`).
- `?view=done|documented` (2026-10-01, B5): only that view's steps and the lines between them (a line is in a view when its membership is `both` or that view's, and both its ends are). Without it, every step and every line. Any other value: `422`.
- Edge `provenance` (2026-10-01): `O`, or `I` for a line the translation added where one view leaves out the other view's steps. Until each view is drawn on its own (V1), the layout, lint, quality card, exports and leadership read the **combined** map: every step, and every line except those `I` lines with a view membership.
Each element: `id, stable_key, kind, label, lane_role_id, phase_id, time: {work_min, wait_min, text}, complexity, kpi, decision: {mechanism, decider_role_id, rule_or_threshold, escalation}, handoff: {in, out}, raci: [{role_id, letter, contested}], provenance, r_reference, source_state, divergence_types, constraints: [{text, provenance, cause_type, is_key}], k_risk, ai_flag: {component, input, output, handoff, basis} | null, evidence: [{segment_id, source_id, source_kind, stance, anchor, verified, note}], confidence, confidence_breakdown: [{label, delta}], needs_check, review_status, account_summary: {official, lived, unclear}, practice_described, variants, view_membership, work_type, constraint_type, work_type_basis, work_type_status, level, parent_element_id`.
- `work_type` (2026-10-01, C2, PRD §3.12.4, B.29): clear · complicated · complex · chaotic · confused · not_classified; `constraint_type` (B.30) follows from it (clear rigid, complicated governing, complex enabling, chaotic absent; null for confused or not classified); `work_type_basis`: the quoted cues `[{"segment_ids": [...], "quote": "..."}]`, each found in the passages it cites; `work_type_status`: proposed · confirmed · not_classified (no cue passed the checks). Steps Eric reviewed keep theirs. A complex or chaotic step is never an automation candidate (S4 drops such a flag; lint L10 fails one). Null on maps drafted before v1.10.
- `view_membership` (2026-10-01, PRD §3.12.11, B.35) on every element and edge: `both` · `done_only` · `documented_only`. Elements: corroborated, contested, trace-contradicted and not-assessed steps (and start and end) → `both`; practiced-only → `done_only`; documented-only and every `R` element → `documented_only`. Edges: the views both ends are in, except that a line both views could draw is `documented_only` where practice goes another way between the same steps (and `done_only` the other way round). `null` on maps drafted before v1.10 and on lines Eric added.
- `sequence_basis` (2026-10-01, PRD §3.12.10, B.34) on every edge, strongest first: `explicit_order` (the lived account states the order, "first … then", or the line is a stated exit, loop, trigger or end point) · `document_order` (one document describes the steps in that order) · `dependency` (what one step hands over is what the next takes in) · `narration_order` (only the order of mentioning; raises a validation question with reason `sequence`).
- The draft adds the lines each view needs where the other view's steps are left out (rules 1 and 7): in As documented a line of the same kind; in As done a `sequence` line when the lived account states the order, otherwise a **"not described" connector**: `kind: "gap"`, `label: "Not described"`, `view_membership: "done_only"`, with a validation question (reason `not_described`) naming the documented steps in between. No step is ever invented.
- `information_payload` (2026-10-01, C3, rule 8): what passes across a line, in the SME's terms (for example "loading report"), when what one step passes on is what the next receives; the stitching adds a **candidate line** (`provenance: I`, `sequence_basis: dependency`, in the views both ends are in) between steps in different lanes with no line yet, even when the two sides come from different interviews. Information passed on that no step receives, or received from no step, becomes a validation question (reason `information`). `typical` (a judgment step's typical response) stays `null` for now.
- `variants` (2026-10-01, PRD §3.12.11): where practice and the documents describe the same step differently, both values, `{"done": {"owner"?, "threshold"?, "time"?, "trigger"?}, "documented": {…}}` (only the attributes that differ; each value checked like every S4 field: an owner must be a known role the step's claims name, numbers must appear in its claims); `null` when nothing differs.
- `account_summary` (2026-10-01, PRD §3.12.3): how many of the step's verified interview claims give the official account (how it is meant to work), the lived account (what the SME does or did) or neither; `practice_described`: `true` when a lived claim describes the step, `false` when only the official account does (shown as "Practice not described"), `null` when the interview gives no account of it.
- `level` and `parent_element_id` (2026-10-06, K2; PRD §3.12.10 rule 9, §3.9 rule 10, B.39): a step whose verified interview claims all answer Landscape questions (`L1`–`L7`, by question ID) and that no document describes is `landscape` (team-level); every other step is `practice`. A practice step in the same lane and phase as a landscape **activity** is linked to it through `parent_element_id` (with several such activities, the one whose label shares most words with the step's; none on a tie). Both are `null` on a map with no landscape step (one level). With `?view=`, the layout, lint and graph of a view draw the **finest level**: a landscape activity with practice steps under it is left out, and its lines go to the practice steps where its own flow starts (those with no line in from another of its steps) and come from those where it ends (no line out to another of its steps); a landscape activity with no practice steps is drawn as a normal activity. The panel shows "Part of: …" and the table view groups the practice steps under it.
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
- **Per view** (2026-10-01, PRD §3.12.11, V1): `?view=done|documented` lays out only that view's steps and lines (G2a: As done, G2b: As documented); `&show_other=true` also places the steps only in the other view, with `ghost: true` on them and on the lines only the other view draws (the UI draws them at 20% opacity with a dashed outline and the label "Only in the documented version" or "Only in practice"; no marker is added). Without `view`, the combined map (both views' steps, without the lines added for one view) as before. The response carries `view` (`"done"`, `"documented"` or `null`); every node and edge carries `ghost` (false unless `show_other`). A `gap` edge ("not described" connector, As done only) is drawn dashed with its label. Any other `view` value: `422`.
Errors: `404` ("That version doesn't exist."). Used by: Review (P5).

### GET /api/versions/{vid}/lint
The lint report of PRD §3.7 (L1–L12), stored on the version when the draft is built:
```json
{"failures": [{"rule": "L4", "element_id": "…", "message": "Decision \"Deviation in limits?\" needs at least two labelled exits; it has 1."}],
 "warnings": [{"rule": "L12", "element_id": "…", "message": "Activity \"Issue load sheet\" has no time stated."}]}
```
Each issue also has `view` (2026-10-01, B5): `null` for a check on the map as one; `"done"` or `"documented"` for a view's own flow checks (PRD §3.12.11), with the message starting "As done:" or "As documented:". Per view: every step reachable from the start (L9), every step but the end with a way out (L9), every exit the view draws labelled (L4 decisions, L5 approvals); "not described" connectors are an L12 warning per view. On the map as one, each line whose sequence basis is `narration_order` is an L12 warning ("The line from "A" to "B" rests only on the order the sources mention them."), with its validation question. The same report feeds the quality card and the publish blockers. Failures block publishing (P7); warnings are listed beneath the quality card. Since P5 the warnings include "The map has n line crossings; consider changing the lane order." (L12, more than 3 crossings in the layout). A version without a stored report is linted on request.
2026-10-06 (K3, PRD v1.10 L12): two more warnings on the map as one: "n decisions, approvals or judgment steps without a confirmed work type: "…", "…", "…" and n more." (`element_id` the first of them; none on maps drafted before v1.10) and, when the version was drafted from at least one interview, "Fewer than three kinds of story: none yet about a time it went well (M5.1); a time it went badly (M5.2); a time something surprised (M5.3)." naming only the kinds missing.
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
- 2026-10-06 (K3, PRD v1.10–1.11 §7.2): **Q11** "Work types confirmed" (warning): every decision, approval and judgment step (mechanism judgment, or complex or chaotic work) has a work type Eric confirmed (`PUT /elements/{eid}/work-type`); detail "n decisions, approvals or judgment steps without a confirmed work type: “…”, “…”, “…” and n more."; passes on maps drafted before v1.10 (no work types). **Q12** "System alignment complete" (warning) is on the card only when the engagement uses system records (P10b): every imported log activity aligned or marked hidden work. Checks are always in order Q1…Q11(, Q12).
- Q1 every step on the map tagged O/I/R and every R with a reference · Q2 every O/I step with at least one verified passage (an `O` step added from hidden work may instead rest on its system trace: a confirmed match recorded in at least 5 cases, R8) and no unverified claim behind any step · Q3 no lint L4/L5 failure · Q4 no L6–L9 or L11 failure · Q5 no L10 failure · Q6 no unreviewed step, pending merge, open image suggestion, or unconfirmed step needing a check · Q7 the rendered Master Process Map and HTML map have exactly the three sections in order, and recommendation content (AI flag blocks, knowledge risks, external practice, questions) only in section 3 · Q8 no name from the redaction list in any rendered export (md, json, csv, html) · Q9 no image data or image reference in any rendered export.
- `warnings`: the lint warnings (steps without time, activities without KPI, AI flags outside 3–7, line crossings, large map), and, for a map drafted from interviews only, "Signal strength: Limited. Built from interviews only; confirm the steps with a document or another SME before relying on them." (a warning, never a blocker). Rejected steps are not on the map and count for nothing. Each failing detail names what to fix; names hidden.
Errors: `404` ("That version doesn't exist."). Used by: Review banner and quality popover (P7), readiness `blockers_count`, publish.

## Views: alignment matrix, registers, cause library (PRD §4 Views, §5.4 Matrix and Registers) — phase P9

### GET /api/versions/{vid}/alignment-matrix
How each kind of source stands on each step (PRD §3.7 Stage 3: classified, never reconciled). One row per step (activity, decision, approval; not start, end or rejected steps), in process order:
`{"element_id", "label", "kind", "sop", "interview", "sme_official", "sme_lived", "jd", "artefact", "state", "divergence_types": [...]}`.
- **SME official · SME lived** (P9u-2, 2026-10-07; PRD §6.3 P9 "four layers", §3.12.3): the interview column split by the account the interview gives of the step. A layer takes the `interview` cell when the step's verified interview claims include that account (official: how it is meant to work; lived: what the SME does or did); it is `silent` when the interview speaks of the step but only with the other account; `account_unclear` when the interview speaks of it only with claims whose account is unclear (neither layer can claim it; never guessed); and the `interview` cell itself when that is `silent` or `not_applicable`.
- Columns: `sop` = SOPs, manuals and other documents · `interview` = interview transcripts · `jd` = job descriptions · `artefact` = executed artefacts.
- Each cell is `supports` · `contradicts` · `silent` · `not_applicable`: `contradicts` if any source of that kind contradicts the step, else `supports` if any supports it, else `silent` if the draft was made from a source of that kind (silence is never contradiction), else `not_applicable` (no source of that kind). A recommended (`R`) step is not assessed: every cell is `not_applicable`. Cells count the same stances as the step's source state.
- `state` and `divergence_types` are the step's own (B.4, B.5). Labels have names hidden. Works for drafts and published versions.
Errors: `404` ("That version doesn't exist.").

### GET /api/versions/{vid}/registers
Everything a register lists for one version (PRD §4 Views, §5.4 Registers), from its own steps (not rejected ones), names hidden:
```json
{"k_risk": [{"element_id", "label", "lane", "k_risk"}],
 "ai_flags": [{"element_id", "label", "lane", "mechanism", "component", "input", "output", "handoff", "basis"}],
 "constraints_by_cause": [{"cause_type": "single_point_knowledge" | … | null,
                           "constraints": [{"element_id", "label", "text", "is_key", "provenance"}]}],
 "external_practice": [{"element_id", "label", "r_reference"}],
 "questions": [question objects as GET /versions/{vid}/questions],
 "rejected_claims": {rejected claims as GET /versions/{vid}/rejected-claims}}
```
Steps in process order. `constraints_by_cause`: one group per cause type that has constraints, in B.9 order, then `null` (no cause type recorded); key constraints first within a group. `lane` is the lane role's name; `mechanism` the step's decision mechanism (so a judgment step's flag reads as support only). Errors: `404` ("That version doesn't exist.").

### Cause library (PRD §3.5 `cause_library`, §3.11)
Engagement-level entries, one per step and divergence type, pending until Eric confirms or refutes them. When a draft is made or refreshed, an entry is added (never twice for the same step key and divergence type; existing entries and their validation are kept) for each step on the map whose source state is `contested` or `trace_contradicted`:
- `pattern`: the divergence notes on the step's contradicting evidence (for example "Threshold divergence: 10 min in SOP vs up to 15 min in practice"), else "The sources disagree about “<step>”." Observed fact, provenance `O`.
- `inferred_cause` and `cause_type`: only from a constraint recorded on the same step with a cause type (key constraints first), provenance `I`; otherwise empty, meaning "not known yet: ask your SME". No AI call and no guess.
An entry as returned: `{"id", "element_stable_key", "element_id", "element_label", "divergence_type", "pattern", "inferred_cause", "cause_type", "provenance", "validation_result": "pending" | "confirmed" | "refuted", "created_at"}` — `element_id` and `element_label` are the step with that key on the current map (`null` and the last known label if it is no longer there); names hidden.

### GET /api/engagements/{id}/cause-library
All entries, in the order they were added. Errors: `404` ("That engagement doesn't exist. It may have been deleted.").

### PATCH /api/cause-library/{cid}
Request `{"validation_result": "pending" | "confirmed" | "refuted"}` → the entry. Audit rows "Confirmed cause" · "Refuted cause" · "Reopened cause". Errors: `404` ("That cause-library entry doesn't exist."); `422` (field `validation_result`: "Choose pending, confirmed or refuted.").

## Leadership view (PRD §4 Views, §5.4 Leadership) — phase P11

Where the process jams and why, for a **published** version: worked out from its map every time it is asked for (no AI call), kept in three separate parts (constraint 9). Only steps count (activities, decisions and approvals), never rejected ones. Every figure carries the IDs of the steps behind it (`element_ids`), so the screen can open them. Roles only; no person is named, scored or rated (constraint 10).

### GET /api/versions/{vid}/leadership
Response `200`:
```json
{"version": {"id", "label", "state"},
 "facts": {"phases": [{"phase_id", "name", "work_min", "wait_min", "rework_loops", "handoffs",
                       "divergence_counts": {"threshold": 1},
                       "links": {"work": [...], "wait": [...], "rework_loops": [...], "handoffs": [...],
                                 "divergence": {"threshold": [...]}}}],
           "sources": 5},
 "interpretation": {"causes": [{"cause_type", "systemic": true, "reason", "phases": [{"phase_id", "name"}],
                                "lanes": ["…"], "evidence_weight": {"supporting": 3, "sources": 5},
                                "confidence": 0.72, "constraints": [{"element_id", "label", "text", "is_key"}],
                                "element_ids": [...]}]},
 "recommendation": {"recoverable_wait_min": 15, "recoverable_wait_element_ids": [...],
                    "rework_loops": 3, "rework_element_ids": [...],
                    "ai_flags": [{"element_id", "label", "lane", "mechanism", "component", "input", "output", "handoff", "basis"}],
                    "decisions_needed": [{"cause_type", "text"}]}}
```
- **Facts, per phase** (in phase order; steps with no phase under "No phase"): `work_min` and `wait_min` add up the steps' times (steps without a time add nothing; `links.work` / `links.wait` list the steps that do); `rework_loops`: lines of kind `rework` or `reject` leaving a step of the phase; `handoffs`: lines of any kind between two steps in different lanes, counted in the phase of the step they leave; `divergence_counts`: steps of the phase by divergence type (B.5). `sources`: the sources the version was drafted from.
- **Interpretation, one entry per cause type** (B.9) found on the steps' constraints, in B.9 order. **Systemic** when the cause constrains 2 or more steps that sit in different lanes or different phases (it is not one team's local issue); otherwise **Local**. `reason` says which in plain words (for example "On 2 steps in 2 lanes: Load controller, Ramp."). `evidence_weight`: how many of the version's sources support at least one of those steps (a verified "supports" passage), of all its sources. `confidence`: the average confidence of those steps (their own confidence, worked out when the map was built), rounded to 2 places; `null` if none has one. Constraint texts have names hidden.
- **Recommendation:** `recoverable_wait_min`: waiting time on steps constrained by a systemic cause (time a fix to that cause could win back); `rework_loops`: all rework and reject lines; `ai_flags`: up to 3 steps with an AI flag, rule-based decisions first (automation candidates), then by confidence, in the fixed five-field block (a judgment step's flag is support only); `decisions_needed`: one line per **systemic** cause, with the text Eric saved (empty until he writes one).
Errors: `404` ("That version doesn't exist."); `409` "The leadership view shows a published map. Publish this draft first, then open Leadership." (a draft).

### PUT /api/versions/{vid}/leadership/decisions
Request: `[{"cause_type": "system_fragmentation", "text": "Fund one digital loading report across ramp and load control."}]` — the "Decision needed" lines (up to 500 characters each; an empty text clears a line). Replaces the version's saved lines. Response `200`: the `decisions_needed` list as above. An audit row "Saved leadership decisions". Allowed on published and superseded versions (the lines are Eric's notes about the map, not map content).
Errors: `404`; `409` (a draft, as above); `422` (field `cause_type`) "Decisions are recorded for systemic causes only." or (field `text`) "Keep each decision under 500 characters."

## Gap analysis (PRD §3.11, §4 Gap analysis, §5.4) — phase P10

Two advisory analyses Eric starts himself on any draft or published version. They produce a report of findings and **never change the map** (constraint 22); every kept finding waits for Eric's disposition.

A report as returned by `GET /api/gap-analyses/{gid}`:
```json
{"analysis": {"id", "version_id", "version_label", "mode": "internal" | "external",
              "status": "brief_draft" | "queued" | "running" | "draft_report" | "finalised" | "failed",
              "job_id", "error", "created_at", "completed_at", "finalised_at", "notes": [],
              "counts": {"kept", "rejected", "open", "needs_check"}},
 "findings": [finding, …], "rejected": [finding, …], "questions": [finding, …],
 "sources": [{"id", "url", "title", "domain", "page_age", "tier", "returned_in_results"}],
 "brief": {"brief": {…}, "text", "confirmed", "scan": {"hits": [{"text", "reason"}]}} | null,
 "usage": {"calls", "input_tokens", "output_tokens"} | null, "search_count": 0}
```
- `notes` (analysis): plain-language notes about the run, e.g. "The search limit was reached before the research finished, so this report may be incomplete." (a web search tool error, kept as a partial result) or "Left out as not a gap (the map already does this): “…”." `sources` and `brief` are for Analysis B (`[]` and `null` for A).
A finding: `{"id", "section": "fact" | "interpretation" | "recommendation", "finding_type" (B.22 or B.23), "title", "text", "element_ids": [...], "elements": [{"id", "label"}], "evidence": [{"side": "documents" | "practice" | "external" | "system", "source_id", "source_kind", "source_name", "stance", "segment_id" | null, "anchor", "quote", "url", "tier", "page_age", "citation_id"}], "basis", "provenance": "O" | "I" | "R" | "", "severity": "high" | "medium" | "low" | null, "evidence_strength": "strong" | "weak" | "dated", "comparison": "absent" | "different" | null, "verification_status": "verified" | "rejected", "rejection_guardrail", "rejection_reason", "verifier_verdict": "supported" | "partial" | "not_supported" | "not_run", "needs_check", "question", "notes": [], "disposition" (B.25), "disposition_note", "created_item_ref", "gap_class" (B.32) | null, "stated_reason", "cause_type" (B.9) | null}`.
- External evidence (Analysis B): `side` `external`, `source_kind` and `tier` the source tier (B.24), `source_name` the page title, `url`, `page_age`, `citation_id` (c1 …), and `quote` the cited text cut to at most 25 words. `url`, `tier`, `page_age` and `citation_id` are empty for internal evidence; `source_id` (the engagement's source, to open it in the viewer) is empty for external evidence.
- Finding `notes`: plain-language flags, e.g. "A link to a step that isn't on this map was removed." (GX6) or "Confirm with your compliance team; this is not legal advice." (a legal or regulatory finding).
- `findings`: kept findings in report order (facts, then interpretation, then recommendation; high severity first within a section). `rejected`: findings a guardrail or the verifier turned down, with the guardrail (`G3` passage, `G4` quote, `G5` number or role, `GAV` gap verifier); shown in a collapsible section, never as findings. `questions`: causes the sources don't explain (`question` holds the suggested SME question; `provenance` and `severity` empty) — they are dispositioned like findings.
- `needs_check`: the verifier found the finding only partly supported (`partial`).
- Names on the hidden list are replaced by roles in every text; `quote` is the passage words the finding cites (names hidden); a silent side has `segment_id: null` and no quote.
- `usage`: tokens of the analysis's AI calls. `search_count`: web searches used (Analysis B).
- **Reality gaps** (2026-10-01, C4b, PRD §3.12.7, criterion 56, A.8): `finding_type` may also be `known_adaptation`, `unknown_rule`, `disclosure_gap`, `control_gap` or `constraint_mismatch`. Analysis A sends each diverging step's interview accounts (official or lived, with the reason the SME stated, already found in the passage) and its work type with the cue passages. The gate adds: a **known adaptation** must quote the step's official account and its lived account, each from that account's own words (the two may share a passage), and needs no documents side; a **constraint mismatch** needs every step it names to be complex or chaotic work and a quote of what the documents prescribe. Only reality gaps have a `gap_class`: the class Claude proposes is kept only when its `stated_reason` is found word for word in an interview passage the finding cites (then `cause_type` too); otherwise the class is `unexplained`, `stated_reason` and `cause_type` are empty, a note says so if a reason was given but not found, and the report adds the question 'On "<step>": Why do people do it this way?' (the bank's M6.4) for the SMEs. Other findings have `gap_class: null`, `stated_reason: ""`, `cause_type: null`. While open, `gap_class` is the proposal; once decided, Eric's final class. Reality gaps take severity by the §3.11.1 rule, which names none of them (low). The Markdown export shows the class, whether it came from a stated reason and the cause type, never the reason's words (no passage words in documents-vs-practice exports).

### POST /api/versions/{vid}/gap-analyses/internal
**AI.** Analysis A, documents vs practice (PRD §3.11.1). Request: none. Response `202`: `{"analysis_id", "job_id"}`; the job (type `gap_internal`, target the analysis) runs:
1. **Finding where the sources differ** (no AI): every step whose source state is `contested`, `documented_only`, `practiced_only` or `trace_contradicted`, or that has a contested RACI entry, with each source's stance, the passages behind it and the divergence notes (threshold, timing, ownership, trigger).
2. **Explaining the differences** (`GA_internal`): Claude sees only that set and the passages it cites (names hidden) and returns findings of the B.22 types, each with evidence, plus causes it can't explain as questions.
3. **Checking every quote against your documents** (no AI): every evidence item must cite a passage it was given (G3) and quote it (G4); numbers and roles in a finding must be in its passages (G5); every step it names must be in the set (G3); it must have evidence from both sides — the documents and practice — where a side's silence (from the set) counts as that side's evidence; a pattern or likely cause (`interpretation`) needs a basis citing what the SMEs said (interview passages), else it is rejected (G3). Names are replaced by roles (G10).
4. **Independent verification** (`GA_verify`, follows the verifier switch; `skipped` when it is off): sees each finding and its passages only; `not_supported` → rejected `GAV`; `partial` → kept with `needs_check`.
5. **Writing the report** (no AI): severity by the §3.11.1 rules; provenance `O` for facts, `I` for interpretation and recommendation.
6. **System records** (no AI; R6, 2026-10-08; PRD §3.13.6, criterion 88): from every imported log of the engagement, using only the alignment rows Eric has **confirmed**, facts (`section: "fact"`, provenance `O`, `verifier_verdict: "not_run"`) of these B.22 types, each resting on at least 5 cases:
   - `hidden_work`: an activity Eric confirmed as hidden work. `element_ids`: the matched step it most often directly follows, if any. Severity **High** when that step is a decision or approval, else **Medium**.
   - `offline_work`: a step Eric confirmed as having no system record, when an interview describes it (source state other than `documented_only`). **Medium** on a decision or approval, else **Low**.
   - `dead_control_candidate` (stronger evidence): a documented-only approval or decision Eric confirmed as having no system record. When Claude's findings already name the step as a dead-control candidate, the system evidence and a note are added to that finding; otherwise a new finding is made. **High**.
   - `sequence_drift`: a step the system trace contradicts (R5b: the system records it before the step the map puts first). **High** on a decision or approval, else **Low**.
   - `estimate_gap`: a stated time (each account's own words: the SME's and the documents' time texts, or the step's time) that differs from the measured median work of the step's main activity by more than 50%. Needs end times and a single minutes figure in the text. **Medium** on a decision or approval, else **Low**.
   - `measured_rework`: the step's activities occur more than once in over 10% of cases. **Medium**.
   System evidence: `{"side": "system", "source_id": <log ID>, "source_kind": "system_log", "source_name": <log name>, "stance": "supports" | "contradicts" | "silent", "segment_id": null, "anchor": "2026-03-02 to 2026-04-26" (the log's window, or ""), "quote": ""}` — figures, never a quote or a user ID; the figures are in the finding's text.
With no step that differs and no system finding, the report is empty and no AI call is made. If a stage fails, the analysis is `failed` with the job's plain error and no findings. The map is not changed.
Errors: `404` ("That version doesn't exist."); `409` "A gap analysis is already running for this version." (one of its analyses is queued or running).

### POST /api/versions/{vid}/gap-analyses/external
Analysis B, external best practice (PRD §3.11.2): creates the analysis (status `brief_draft`) with a research brief drafted from the version, deterministically (`gap.build_brief`). **No AI call; nothing is sent.** Request: none.
Response `201`: `{"analysis": {…}, "brief": {"brief", "text", "confirmed": false, "scan": {"hits": [...]}}}`.
- `brief`: `{"process_name", "industry", "adjacent_industries": [...], "region", "steps": [...], "questions": [...], "max_searches": 10, "allowed_domains": [], "blocked_domains": [], "recency_years": 5}` — the process name and step labels (activities, decisions and approvals, not rejected ones) made generic: every confidential term (Setup), every name on the hidden list and every figure removed; industry and adjacent industries from Setup; the four default research questions.
- `text`: exactly what would be sent to web search (process, industry, adjacent industries, region focus, steps, questions). The search limit and domain lists go to the search tool's settings, not the text.
- `scan`: the confidentiality scan of `text` (PRD §3.11.2): every name on the hidden list ("A name from your list of names to hide"), every confidential term ("A confidential term from Setup"), every number or time copied from the map ("A number or time copied from the map") and every run of 8+ consecutive words found in a transcript or document passage ("Words copied from your sources").
Errors: `404` ("That version doesn't exist.").

### PATCH /api/gap-analyses/{gid}/brief
Request `{"brief": {…brief as above}, "confirmed": true | false}` (`confirmed`: "This brief contains no confidential information" is ticked). Saves the brief and returns the same shape as the POST above, with a fresh scan. Allowed while the analysis is `brief_draft` or `failed`.
Errors: `404` ("That gap analysis doesn't exist."); `409` "This analysis has already run. Start a new one to change the brief." (or it is Analysis A); `422` with the field: search limit 3–20, recency 1–30 years, "Use allowed domains or blocked domains, not both." (the API rejects requests with both).

### POST /api/gap-analyses/{gid}/run
**AI with web search.** Runs Analysis B from the saved brief. Request: none. Response `202`: `{"analysis_id", "job_id"}`; the job (type `gap_external`) runs:
1. **Searching the web with your brief** (`GB_research`, the web search tool; `max_uses` = the brief's search limit, at most `WEB_SEARCH_MAX_USES_CAP`): only the brief text is sent — never sources, the map, names or confidential terms. Every search result (URL, title, page age) and every citation on the answer (URL, title, cited text) is captured; citations get IDs `c1` … . A tool error (e.g. `max_uses_exceeded`) is kept as a partial result with a plain note on the analysis.
2. **Organising the findings** (`GB_structure`, no tools): the cited answer becomes findings of the B.23 types, each citing only captured citation IDs, with the steps of the map it concerns and whether the practice is `absent`, `different` or `aligned` (the step list with labels, names hidden, is sent here as in drafting — never to web search).
3. **Checking every finding against its sources** (no AI): GX1–GX6 (`grounding.verify_citations`): no citation → rejected `GX1`; a cited URL the search didn't return → `GX2`; claim or quote not in the cited text → `GX3`; vendor or unknown sources only → kept, weak evidence (`GX4`); every source older than the recency limit → kept, dated (`GX5`); a step reference not on the map → link removed with a note (`GX6`).
4. **Independent verification** (`GB_verify`, follows the verifier switch): `not_supported` → rejected `GAV`; `partial` → kept with `needs_check`.
5. **Writing the report** (no AI): findings the map already follows (`aligned`) are left out as "not a gap" (a note on the analysis); severity by `gap.severity_external`; provenance always `R`; the compliance note on legal or regulatory findings; `search_count` stored.
If a stage fails, the analysis is `failed` with the job's plain error and no findings; it can be run again. The map is not changed.
Errors: `404`; `409 BRIEF_NOT_APPROVED` "Tick “This brief contains no confidential information” before running the research." or "Remove the highlighted items from the brief before running the research." (scan hits); `409 WEB_RESEARCH_DISABLED` "Web research is switched off. Turn it on in Settings first."; `409` "A gap analysis is already running for this version."; `409` "This analysis has already run. Start a new one to run the research again." (a `draft_report` or `finalised` analysis, or Analysis A). A web search switched off for Eric's Anthropic organisation fails the job with "Web search isn't enabled for your Anthropic organisation. See the README, 'If something goes wrong'."

### GET /api/versions/{vid}/gap-analyses
Every analysis of the version, newest first: the `analysis` objects above. Errors: `404`.

### GET /api/gap-analyses/{gid}
The report above. Errors: `404` ("That gap analysis doesn't exist.").

### PATCH /api/gap-findings/{fid}
Eric's decision on one kept finding or question (PRD §3.11.3). Nothing changes the map without this. Request:
`{"disposition": "added_question" | "added_cause" | "added_step" | "dismissed", "note": "", "step": {"kind", "label", "lane_role_id", "after_element_id", "mechanism"}, "gap_class": B.32}` (`step` only for `added_step`; `gap_class`, optional, only for a reality gap: the final class Eric keeps, otherwise the proposed class stays; for another finding `422` "Only reality-gap findings have a gap class.").
Response `200`: the finding, with `disposition`, `disposition_note` and `created_item_ref` (`question:<id>`, `cause:<id>` or `element:<id>`).
- **added_question**: a validation question (reason `gap_analysis`, `origin_ref` the finding) in the engagement's **current draft**, on the draft's step with the same key as the finding's first step (if any). The wording: the finding's `question` for a cause the sources don't explain; otherwise "<title>: which account is right in practice?" (documents vs practice) or "Should the process include this practice: <title>?" (external).
- **added_cause** (documents vs practice only): a cause-library entry for the finding's first step and divergence type (`threshold_gap` → threshold, `ownership_mismatch` → ownership, `sequence_gap` → sequence, `trigger_gap` → trigger, `exception_gap` → exception, otherwise omission): pattern = the finding's text (`O`), likely cause = its basis (`I`) for an interpretation. An entry that already exists for that step and type is reused, never doubled.
- **added_step**: the step is added to the current draft exactly as `POST /versions/{vid}/elements`, with the provenance and evidence taken from the finding: an external finding makes an `R` step whose reference is "<source title> <URL>" (its first source); a documents-vs-practice finding makes an `O` step on its passages. `step` gives what Eric chose in the Add step form (kind, label, lane, where it goes, and for a decision or approval rule-based or judgment).
- **dismissed**: needs a `note` (why), 1–1000 characters.
- Each decision writes an audit row: "Added gap finding as question" · "Added gap finding to cause library" · "Added step from gap finding" (with the "Added step" row of the step itself) · "Dismissed gap finding".
Errors: `404` ("That finding doesn't exist."); `409` "This report is finalised and can't be changed." · "This finding already has a decision." · "A rejected finding can't be used." · "Reopen this map as a new draft first: questions and steps are added to the draft." (the analysis ran on a published map and no draft exists); `422` (field `note`) "Say why you're dismissing this finding." · (field `disposition`) "Only documents-vs-practice findings go to the cause library." · "This finding isn't tied to a step, so it can't go to the cause library." · "Choose added_question, added_cause, added_step or dismissed." · (field `step`) "Choose where the new step goes." · and the Add step field errors.

### POST /api/gap-analyses/{gid}/finalise
Finalises a draft report once every kept finding and question has a decision: status `finalised`, `finalised_at` set, read-only from then on (re-running means a new analysis). Response `200`: the report. Audit row "Finalised gap report".
Errors: `404`; `409` "Decide on every finding first: <n> still open." · "Only a draft report can be finalised."

### GET /api/gap-analyses/{gid}/export
The finalised report as Markdown (`text/markdown`, attachment `gap-analysis-<mode>-<version>.md`), a fixed template:
```
# <Process> — Gap analysis: documents vs practice | external best practice
Version <label> · run <date> · finalised <date>
Advisory evidence summary: not a legal, regulatory or audit opinion.

## 1. Facts
## 2. Interpretation
## 3. Recommendation
## Rejected findings   (counts by guardrail only)
## Notes               (analysis notes, if any)
```
- Documents vs practice: **Facts** lists each difference with its severity, steps and every side's sources by name, place and stance (never a passage's words); **Interpretation** the patterns and likely causes with their basis; **Recommendation** documentation updates, SME questions and each finding's decision.
- External: **Facts** what the sources say, each source with title, link, tier, date and an excerpt of at most 25 words; **Interpretation** how the map compares (absent, or different from named steps), weak or dated evidence and the compliance note; **Recommendation** each candidate change with its decision.
- Every line carries its provenance tag (`[O]`, `[I]`, `[R]`). Role names only; the text is scanned for names on the hidden list (0 hits, or the export isn't made). Confidential terms may appear (they only restrict what is sent to web search).
Errors: `404`; `409` "Finalise the report first."

### Gap findings on a step
`GET /api/elements/{eid}` `gap_findings`: `[{"id", "analysis_id", "mode", "title", "severity", "disposition"}]` — the kept findings and questions of every analysis in the engagement that name a step with this step's key, newest analysis first.

### Master Process Map section 3 (phase P10)
"Cause library entries (pending validation)" lists the engagement's pending entries for the map's steps: `- [O] <step> · <type>: <pattern>` and the likely cause (`[I]`) or "not known yet: ask your SMEs". "Gap analyses" lists the version's finalised reports: `- <mode> · finalised <date> · <n> accepted findings: <title>; <title>` (accepted = added as a question, cause or step). The HTML map shows the same.

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
Response `200`: `[{"id", "engagement_id", "label", "state", "created_at", "published_at", "published_by", "parent_version_id", "signal", "codebook_version"}]` — `state`: `draft` · `published` · `superseded`; `published_at`/`published_by` `null` for a draft; `signal` as in readiness, worked out from the sources the version was drafted from (`null` when it has none recorded). `codebook_version` (2026-10-01): the version of the mapping codebook (PRD Appendix E, `backend/app/prompts/codebook.md`) its latest draft or refresh was made with; `null` for a version made before the codebook existed. The codebook is sent with the S1, S2, S3c and S4 prompts.
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
Download an export of a published version; `fmt`: `md` (Master Process Map, §7.3) · `json` (graph JSON with the quality card) · `csv` (RACI) · `html` (the single-file offline map). Response `200`: the file (`text/markdown`, `application/json`, `text/csv`, `text/html`, UTF-8) with `Content-Disposition: attachment; filename="load-control-v1-0-master-map.md"` (`…-graph.json`, `…-raci.csv`, `…-map.html`). Role names only; no images, verbatim quotes or names; rejected steps left out; the stored quality card printed at the top. Since 2026-10-06 (K3) the Master Process Map follows PRD v1.11 §7.3 in full: section 1 adds **Stories** (SME-worded labels, story type, source and anchor; never the quote) and **Strengths as stated (preserve)**; section 2 adds a **View** column (both · as done · as documented), **Two views: as done and as documented** (each view's steps, those only in it, and its "not described" connectors), **Work type and know-how** (work type with proposed/confirmed per step; knowledge risk and dominant ASHEN category per decision point), **Official vs lived** (steps with both accounts and how the views differ on owner, threshold, time or trigger; steps with the official account only) and **Glossary of SME terms**; section 3 starts with **Preserve / Improve** (by capability dimension) and **Reality gaps by gap class** (from finalised documents-vs-practice analyses, with the stated reason) and ends with **Disposition and value** and **System records** ("Not used in this engagement." while those optional modules are off, decision A). Every heading is always printed, with a plain line when empty. The HTML map has the same sections, draws **both views** (As done, then As documented; "not described" connectors dashed), and each step's details add View and Work type. An audit row "Exported md" (etc.); the guided path's **Exports** step is done once anything was exported.
Errors: `404` (version, or unknown `fmt`: "Choose md, json, csv or html."); `409` "Publish a version with a green quality card first." (a draft, or a card that isn't green).

## Review (PRD §4 Review, §5.6–§5.8) — phase P5

### GET /api/elements/{eid}
One step with everything the detail panel shows (PRD §4: every element response carries these fields, so the panel renders without extra calls).
Response `200`: the element exactly as in the graph (`id, stable_key, kind, label, lane_role_id, phase_id, time, complexity, kpi, decision, handoff, provenance, r_reference, source_state, divergence_types, constraints, k_risk, ai_flag, confidence, confidence_breakdown, needs_check, review_status, account_summary, practice_described, variants, view_membership`), plus `answers` (2026-10-01, PRD §3.12.10 rule 6, §5.7.7 4d, acceptance criterion 66): the verified interview answers the step was translated from, `[{"quote", "account_type": "official" | "lived" | "unclear", "account_cue", "stated_reason", "variation_condition", "frequency", "source_id", "segment_id", "anchor", "question_id": "M2.4" | null, "question": "How long did each part take, …"}]` (cue, reason, condition and frequency — how often an exception, variation or workaround happens, X1 2026-10-06, "" when not stated — are the SME's words, each found in the cited passage; the question is the guide question the passage answers). In the app only; never in any export. Since 2026-10-01 (C2b, PRD §3.12.6, §5.7.7 4b–4c) also `know_how` and `stories`, worked out from the interview's checked items and the steps S3c linked them to:
- `know_how` (decisions, approvals and complex steps — the knowledge disclosure points — otherwise `null`): `{"kdp_type": "decision" | "judgment", "ashen": {"artefacts": [item], "skills": [...], "heuristics": [...], "experience": [...], "natural_talent": [...]}, "knowledge_risk": "high" | "medium" | "low" | "unknown", "risk_reason": "plain sentence", "cadence": "daily" | … | null, "received": [str], "attended": [str], "wanted": [str], "communicated_via": [str]}`; each item `{"text", "quote", "role", "source_id", "segment_id", "anchor"}` (role: the speaker's role, never a person; natural talent at role level only).
- `stories`: `[{"label", "fragment_type", "signifiers": [the SME's own words], "frequency", "single_account": true, "quote", "source_id", "segment_id", "anchor"}]`, in the order told; kept when told once.
- `work_type_cues` (2026-10-01, V3, §5.7.7 4a): the quoted cues behind the work type with where they are, `[{"quote", "source_id", "segment_id", "anchor"}]` (the same cues as `work_type_basis`, with anchors; names hidden); `[]` when the step is not classified.
And:
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
- `image_count`: images on the step that aren't discarded (images arrive in P8). `gap_findings`: see Gap analysis → Gap findings on a step (P10).
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

### PUT /api/elements/{eid}/work-type (2026-10-05, V3b; PRD §4 Review, §3.12.4, §5.7.7 4a, criterion 54)
Confirm or change a step's work type (the panel's Work type section). Request: `{"work_type": "complex", "constraint_type": "enabling", "confirm": true}`.
- `work_type`: clear · complicated · complex · chaotic · confused (B.29; `not_classified` can't be chosen: "Choose the kind of work this step is."). `constraint_type` (B.30) is optional: left out, it follows the work type (clear rigid, complicated governing, complex enabling, chaotic absent, confused none); sent, it must be a B.30 value or `null`. `confirm` must be `true` (`422`, `details.field: "confirm"`).
- Only steps (activity, decision, approval) of a draft version; a rejected step must be restored first (`409`); published (`409`); start and end (`422`).
- The step's `work_type_status` becomes `confirmed`. **Confirming the proposed type** (same work type and constraint type) leaves the step's review status as it is. **Changing it** is Eric's edit: the step becomes `edited` (an `added` step stays `added`), so it is locked like any edit.
- A confirmed work type is kept through refresh even when the step itself was not yet reviewed: the fresh run's step with the same key takes Eric's work type, constraint type and `confirmed` status.
- A complex or chaotic step is never an automation candidate (constraint 7): an AI flag with an automation basis (`rule_based_automate_candidate`) is removed, and a decision or approval marked `rule_based` becomes `judgment` (criterion 55: complex steps are judgment steps). Both are listed in the audit row.
- The work-type question for the step ("Work type not clear") is marked answered.
- Audit row "Confirmed work type" or "Changed work type" with `work_type`, `constraint_type`, `work_type_status` (and any removed flag or changed mechanism) before and after; the stored lint report is refreshed.
Response `200`: the element as `GET /api/elements/{eid}`. Errors `404`, `409`, `422` (`details.field`). Used by: Review panel 4a (Confirm · Change).
The edit form (`PATCH`) follows the same rule: an AI flag with an automation basis on a complex or chaotic step is refused (`422`, `details.field: "ai_flag.basis"`).

### POST /api/versions/{vid}/elements (phase P6)
Add a missing step (Eric's own, never an AI claim).
Request: `{"kind": "activity", "label": "Check fuel figures", "lane_role_id": "…", "after_element_id": "…", "provenance": "O", "segment_ids": ["…"], "r_reference": "", "mechanism": "judgment"}`.
- **From hidden work (R8, 2026-10-08; PRD §5.6 Variants tab):** `"system_activity": {"log_id": "…", "activity": "Manual weight override"}` with provenance `O` stands in for `segment_ids` (passages may still be added). The activity must be one Eric confirmed as hidden work in an imported log of this engagement, recorded in at least 5 cases (`422`, field `system_activity`: "Choose an activity you confirmed as hidden work in one of this engagement's logs." · "That activity is recorded in fewer than 5 cases."). The step is created as below and, in the same change, the activity's alignment row becomes a confirmed match to the new step (by stable key), so the step's evidence is the system trace (`GET …/system-traces`); the audit row "Added step" names the log and activity.
Response `201`: the element as `GET /api/elements/{eid}`, with `review_status: "added"` (locked).
- **Placement:** the step goes after `after_element_id` (any step or the start, not the end). The first outgoing line of that step that stays on the main path (not `no`, `reject`, `rework` or `exception`) now points at the new step, and a `sequence` line runs from the new step to where that line used to go. Without such a line, a `sequence` line joins them. The new step takes that step's phase. The layout is worked out afresh on the next `GET …/layout`.
- **Provenance:** `O` needs at least one passage (`segment_ids` from this engagement's sources; each becomes a verified "supports" evidence link) — "Pick the passage this step comes from." — or a hidden-work activity (`system_activity`, R8); `R` needs a reference (`r_reference`, 1–500 characters) — "Type the reference this recommended step comes from."; `I` is refused ("Choose Observed (with a passage) or Recommended (with a reference).").
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
`GET` response `200`: `[{"id", "element_id", "element_label", "phase_id", "phase_name", "question", "reason", "status"}]` in the order they were written (step questions in process order, then every gap Claude raised). `reason`: contested · documented_only · inferred · partial_support · low_confidence · gap · gap_analysis (added from a gap finding, P10) · work_type (2026-10-01, C2: a decision or approval whose kind of work no quoted cue shows, "Work type not clear") · information (2026-10-01, C3: information a step passes on that no step receives, or receives from no step, "Information flow") · sequence (2026-10-01: a line resting only on the order of mentioning, "Order not stated") · not_described (2026-10-01: a "not described" connector, "Not described"). Order: step questions in process order, then every gap Claude raised, then the `work_type` questions, then the translation's `sequence` and `not_described` questions. `status`: open · answered. Names hidden.
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

### GET /api/versions/{vid}/capability-notes
Strengths to preserve and weaknesses to improve, as the interviews named them (2026-10-01, C3, PRD §3.12.10 rule 10): `[{"kind": "strength" | "weakness", "dimension": "skillset" | "ways_of_working" | "systems" | "process" | "structure", "text", "cause_type": B.9 | null, "steps": [labels], "quote", "source_id", "segment_id", "anchor"}]`. A weakness linked to a step is also a constraint on it, with its cause type. Names hidden. Errors: `404`.

### GET /api/versions/{vid}/coverage
What the interviews covered and what still needs asking (2026-10-01, C4, PRD §3.12.8, criterion 50, A.8). Worked out on request from the version's checked interview claims and items (claims with an account type, and the stories, know-how, terms and decision information) and its As done view; nothing is sent to Claude.
```json
{"version_id": "…",
 "dimensions": {"trigger": {"status": "missing", "evidence_count": 0, "note": ""},
                "official_vs_lived": {"status": "covered", "evidence_count": 1,
                                      "note": "Both accounts on 1 step: Load and return LIR"}},
 "follow_up_questions": [{"dimension": "kpis", "question_id": "M7.1",
                          "question": "How do you know this went well — what's measured, and who looks at it?",
                          "about": ""}],
 "probes": [{"question_id": "F2", "question": "You mentioned previously that “…”. How do you manage that today, and where do you see the biggest risk?",
             "quote": "…", "source_id": "…", "anchor": "05:52", "speaker_role": "Ramp"}]}
```
- `dimensions`, in this order: `trigger` · `end_point` · `step_spine` · `handoffs` · `decisions_and_criteria` · `approvals` · `exceptions` · `raci` · `work_and_wait_time` · `kpis` · `artefacts` · `know_how` · `stories` · `official_vs_lived` · `sme_terms`. `status`: `covered` · `thin` · `missing`.
- **The rule** for most dimensions: `evidence_count` is the number of checked interview claims or items for it; 0 is `missing`, 1 is `thin` (one mention), 2 or more is `covered`. What counts: trigger claims (`trigger`); interview evidence on the steps that lead to an end (`end_point`); step claims (`step_spine`); hand-off claims (`handoffs`); decision and threshold claims (`decisions_and_criteria`); approval claims (`approvals`); exception claims and claims with a variation condition (`exceptions`); RACI claims and claims naming an accountable role or a decider (`raci`); duration claims and claims stating a time (`work_and_wait_time`); KPI claims (`kpis`); know-how items in the artefacts category (`artefacts`); SME terms (`sme_terms`).
- **Special rules:** `step_spine` is at most `thin` while a line of the As done view rests only on the order of mentioning or is a "not described" connector. `know_how`: the decisions and approvals of the As done view with at least one know-how item; all of them `covered`, some `thin`, none `missing` (`evidence_count`: know-how items). `stories`: one each of went well, went badly and surprise is `covered`, some `thin`, none `missing` (`evidence_count`: stories). `official_vs_lived`: `covered` when at least one step has both an official and a lived account, else `missing` (`evidence_count`: steps compared).
- `note`: what the count is made of, in plain words (step labels, never names); `""` when there is nothing to add.
- `follow_up_questions`: for each `thin` or `missing` dimension, the question bank's question for it, word for word, with its ID (trigger M2.1 · end point M2.5 · step spine M2.2 · hand-offs M3.3 · decisions M4.3 · approvals M7.2 · exceptions M2.6 · RACI M4.4 · time M2.4 · KPIs M7.1 · artefacts M7.4 · know-how M4.8 · official vs lived M6.2 · SME terms M0.2); for `know_how` one per decision without know-how and for `stories` one per kind not yet told (M5.1 went well · M5.2 went badly · M5.3 surprise). `about`: the step (or, for the step spine, the lines) it is about, or `""`. In dimension order. These feed the Follow-up guide (C5).
- `probes` (2026-10-01, C4c, Appendix F F2, A.10): reflective probes that quote an SME back to themself, `[{"question_id": "F2", "question": "You mentioned previously that “The weakness is the paper loading report; it gets lost or arrives late”. How do you manage that today, and where do you see the biggest risk?", "quote", "source_id", "anchor", "speaker_role"}]`. One per distinct verified interview quote that carries a constraint, a weakness or a stated reason, word for word as S1 checked it (only a final full stop or semicolon is dropped where it meets the bank's wording), at most 20 words: a longer quote is left out, never cut, unless it carries a stated reason, which is then played back instead (S1 found it word for word), names hidden, in the order the interviews were read. `source_id` and `speaker_role` say whom to ask.
Errors: `404` ("That version doesn't exist."). Used by: the Interview screen (coverage) and the Follow-up guide (C5).

### GET /api/versions/{vid}/exceptions?view=done|documented (X2, 2026-10-06; Eric's request; PRD §3.7 S4 exception paths, §3.12.10 rule 2, Appendix F M3.2, M3.4, M5.s2, constraint 9)
How much of the process is exception handling, rework and workarounds, per view (default `done`, what people actually do). Deterministic, no AI, read-only (never changes the map), names hidden; facts from the map's structure and the SME's own words only:
`{"view", "summary": {"steps", "usual_steps", "exception_steps", "variation_steps", "off_usual_share", "routes", "rework_loops", "workarounds", "extra_handoffs", "frequency_stated"}, "steps": [{"element_id", "label", "route": "usual" | "exception" | "variation", "workaround": bool, "condition"}], "routes": [{"id", "kind": "exception" | "variation", "from_element_id", "from_label", "condition", "element_ids": [], "labels": [], "lanes": [], "exits": [{"kind": "rejoins" | "loops_back" | "ends", "element_id", "label", "edge_label"}], "handoffs", "frequency", "stated_reason"}], "loops": [{"from_element_id", "from_label", "to_element_id", "to_label", "label"}], "workarounds": [{"element_id", "label", "lane", "condition", "stated_reason", "frequency", "basis": "stated_reason" | "story"}], "questions": [{"question_id": "M5.s2", "wording", "about"}]}`.
- **Steps** (start and end left out; rejected steps left out). `usual`: reached from the start over forward lines (rework and loop-back lines never count) without taking an exception exit (`no`, `reject`, `exception`) or entering a variation step; a `no` exit counts as usual where the decision's other exit leads into a variation step (the variation is the condition; "No" is the normal case, e.g. "Busy wave?"). `variation`: a step whose verified lived claim states a variation condition ("on a busy wave"), and steps reached only through one. `exception`: every other step. `condition`: the SME's variation condition, or the label of the exit that leads into the exception route.
- **Routes**: one per line from a usual step into a non-usual step, with the steps reached from there before the usual route again (in order), their lanes, and how the route ends: `rejoins` (a line back into the usual route), `loops_back` (a rework or loop-back line), `ends` (the end of the process). `handoffs`: the extra hand-overs one pass of the route adds: lane changes on entering and along it, plus one for leaving when any exit returns to another lane (each case takes one exit). `frequency` and `stated_reason`: the SME's words from the route steps' verified claims (or a story told about them), "" when not stated.
- **Loops**: every rework line, and every reject line that goes back to a step leading to it.
- **Workarounds**: steps where a verified lived claim gives the SME's reason for working that way and the step is a variation or practised only, or where a story of type `workaround` is told about the step.
- **Questions**: for each route and workaround with no stated frequency, the bank's M5.s2 ("How often does something like that happen?") with `about` naming it. Also fed into the Follow-up guide (rule 7: one more list in the turn, from the As done view).
- `summary.off_usual_share` = (exception + variation steps) ÷ steps, rounded to 2 places; 0 for a map with no steps.
Errors `404` (version), `422` (view). Used by: Review **Exceptions** lens (the line under each step, one short word: "Usual route", "Exception", "Variation" or "Workaround"; the condition is on the line into the step); Registers **Exceptions and workarounds** (X3).

### GET /api/versions/{vid}/lane-boundaries (C8, 2026-10-06; PRD F.4 L5, F.6 F1 and F4, criterion 76)
Where the interviews describe teams' activities overlapping or falling between them, per step of the map (deterministic, names hidden, never changes the map): `[{"element_id", "label", "kind": "shared_delivery" | "gap" | "boundary", "responsible", "consulted": [], "note", "question_ids": []}]`, in process order.
- `responsible` is the step's lane role, the one Responsible the map keeps (constraint 5); `consulted` the other roles the step's checked claims name as doing the work (aliases resolved to the role).
- `gap`: a claim answering L5 or F1 says the activity falls between teams ("nobody", "no one", "neither", "falls between", "not clear who", "no owner"); `shared_delivery`: the claims name more than one role doing the work; `boundary`: a claim answers L5, F1 or F4 without either.
- `note`: plain words, e.g. "Shared delivery: Ramp also take part. One Responsible (Load controller), the others Consulted; confirm with the teams."
These findings also feed the Follow-up guide (rule 7, one more list in the turn: F4 "On “<step>”, how does your team work with <role>? It sounds like both show up together." for shared delivery; F1 "Going back to where we left off, could you help me separate the activities managed by <role> versus <role>?" otherwise; "your team" is the interviewee's and the other role is the first of the step's Responsible and Consulted roles that isn't the interviewee's). Errors `404`. Used by: Registers, **Lane boundaries** (C8).

### Emerging themes (C7b, 2026-10-06; PRD Appendix E tier 3, §3.12.9 rule 3, criterion 58)
Patterns across the interviews' stories that fit no existing category, proposed by S3c (task 3 of `S3c_worktype` v2) and checked by the app before they are kept: a short plain name (one line, up to 80 characters), at least **two different stories** behind it, a one-sentence basis, no banned (blaming) word and no name on the hidden-names list; a theme with the same name as one already there is not proposed again. Proposed themes are replaced at each draft or refresh of that version; themes Eric accepted, renamed or dismissed are never touched by a re-run (constraint 8). They never change the map.

#### GET /api/engagements/{id}/themes
`[{"id", "version_id", "theme", "basis", "status": "proposed" | "accepted" | "dismissed", "note", "fragments": [{"claim_id", "text", "quote", "fragment_type", "source_id", "anchor"}], "created_at"}]`: the proposed themes of the current map (draft, else latest published) and every theme Eric has decided, oldest first; names hidden. `404` (engagement).

#### PATCH /api/themes/{tid}
`{"status": "accepted" | "dismissed" | "proposed", "theme"?: "new name", "note"?: "…"}`. Accept (optionally renamed), dismiss, or put back to proposed. A new name follows the same rules as a proposed one (`422`, `details.field: "theme"`); `note` up to 500 characters on one line. Response `200`: the theme; audit row "Accepted emerging theme" / "Dismissed emerging theme" / "Renamed emerging theme" / "Reopened emerging theme" with before and after. Errors `404`, `422` (`details.field`).
Used by: Registers, **Emerging themes** (C7b).

### GET /api/versions/{vid}/validation-pack (C6, 2026-10-06; PRD Appendix F.7, criterion 75)
The validation session pack as a Markdown file (`text/markdown; charset=utf-8`, `Content-Disposition: attachment; filename="validation-pack-v0.1.md"`), for a session with the SME alongside the draft map. Deterministic; nothing is sent to Claude; names hidden; no banned words. In this order:
1. **Walk the As done view**: "Is this how it actually happens?", then the As done view's steps in process order with their lane role, and its "not described" gaps ("Between "A" and "B": not described").
2. **Dissent round, then assent round**: the two F.7 questions.
3. **Contrast without evaluation**: up to three steps where the views differ — a step whose owner, threshold, time or trigger differs between the views first, then steps only the documents describe, then steps only the interviews describe — each with "As done: …" and "As documented: …" side by side and "What do you make of the difference?"; if none, the pack says so.
4. **Preserve / improve check**: the interviews' strengths ("Of these strengths, which must we keep?") and weaknesses ("Of these weaknesses, which matter most?") from the capability notes; if none, the two open questions instead.
5. **Open validation questions**: the version's open questions, each with the step it is about.
A footer: "Process Map Studio · <process> <version label> · enter the outcomes as edits on the Review screen". Errors: `404` ("That version doesn't exist."). Used by: Review screen, **Download validation pack** (C6).

### GET /api/versions/{vid}/stories (P9u, 2026-10-07; PRD §3.12.2, §5.4 Registers "Stories", criterion 59)
Every story fragment the interviews told on this map, in the order told, for the Registers **Stories** list: `[{"label", "fragment_type": B.31, "signifiers": [], "frequency", "single_account": true, "quote", "source_id", "segment_id", "anchor", "steps": [labels]}]` (the same fields as a step's stories in `GET /api/elements/{eid}`, plus the labels of the steps S3c linked it to; a story linked to no step is listed with `steps: []`). Kept when told once (§3.12.9 rule 2). Names hidden; quotes stay in the app (never exported verbatim). Read-only. Errors: `404`.

### GET /api/versions/{vid}/glossary
The SME terms the interviews use (2026-10-01, C2b, PRD §3.12.2, A.8): `[{"term": "re-trim", "plain_meaning": "…", "steps": ["Approve deviation"], "source_id": "…", "segment_id": "…", "anchor": "24:10"}]` in the order first heard; each term was found in its passage (C1). Names hidden. Errors: `404`. Used by: the panel and the Registers screen (V3).

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
- Since 2026-10-01 (C1) the register also lists the interview's stories, know-how items, SME terms, decision-information items and capability notes that failed a check (for a story its label, for a term "term: meaning", for decision information the decision). A term not found in the cited passages fails G4 ("term not found in cited text"). The draft summary's `verified` counts them too when they pass.
- `anchor` and `segment_id`: the first cited passage that exists; `""` and `null` when none does (`passage_available: false`, e.g. G3 "cites a passage that wasn't provided").
- `guardrail`: B.20 (`G3` passage · `G4` quote · `G5` number or role · `G6` verifier · `G10` redaction).
- `scrub_count`: names Claude used that were replaced by roles, across all claims of the version. `instruction_like_count`: passages in the engagement's sources that looked like instructions and were treated as data.
Errors: `404` ("That version doesn't exist."). Used by: Draft screen (rejected-claims list, P3), Review workbench (P5).
