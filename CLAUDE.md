# CLAUDE.md — Process Map Studio

## What this is
A local app that turns SME interview transcripts and process documents (SOPs, manuals, job descriptions) into an evidence-traceable current-state swimlane map. Claude drafts; the owner reviews and publishes. The owner, Eric, is non-technical.

## Read first, every session
1. This file  2. PROJECT_STATE.md  3. DECISIONS.md  4. PRD_ProcessMapStudio.md (the single source of truth)
The files are the project memory. If chat memory and these files disagree, the files win.

## Binding constraints
1. **Evidence before map.** The AI never invents content. Every element carries provenance `O` (observed in a source), `I` (inferred from a source) or `R` (recommended from external practice, added by Eric only: typed with a reference, or accepted from a verified external gap finding with its source). Every `O` and `I` element links to at least one **verified** evidence segment.
2. **Grounded or rejected.** Every AI claim must pass the deterministic grounding checks in §3.8 (segment exists, quote found, numbers found, roles found). A claim that fails is rejected, logged in the rejected-claims register, and never reaches the map. There is no override that lets an unverified AI claim onto the map; Eric may instead add the element himself.
3. **Don't reconcile — classify.** Sources are never merged into one "best" account. Agreement and disagreement are classified (§3.7 Stage 3) and shown.
4. **Silence is not contradiction.** A source that does not mention an element is `silent`, never `contradicts`. Job-description silence about tasks never changes an element's source state.
5. **Lane rule.** Activities sit in the lane of their single Responsible role. Approvals sit in the lane of their Accountable role. Decisions sit in the lane of the role that makes the routing call.
6. **Every exit labelled.** Every decision has at least two labelled outgoing edges. Every approval has an approve edge and a reject/rework edge. No orphan elements.
7. **Rule versus judgment.** Every decision and approval is classified `rule_based` or `judgment`. A judgment step, or any step whose work type is complex or chaotic (§3.12), is never flagged as an automation candidate.
8. **Human publishes.** Nothing is published until every element, merge proposal and suggested image has been reviewed and every hard check on the quality card (§7.2) is green. Elements Eric has confirmed, edited or added are never overwritten by any AI re-run.
9. **Facts, interpretation, recommendation stay separate** in every generated text output and export.
10. **Roles, not people.** Maps and exports use role names only. Speaker labels map to roles; names on the redaction list never appear in AI outputs or exports. The app never scores, rates or assesses individuals.
11. **Images are interactive-only.** Shown only in the app UI; require caption, type and redaction confirmation; metadata (EXIF, including GPS) stripped on upload; excluded from every export.
12. **Secrets stay local.** The API key lives only in the local `.env` file or OS environment. Never in the database, logs, test fixtures, exports or git; never returned unmasked by any endpoint. A secret check blocks any commit containing a key pattern, `.env` or anything under `data/`.
13. **Every AI call is mockable.** All Claude calls go through the single AI service with a mock mode returning canned fixtures. The default test suite runs fully offline with no key.
14. **Strict JSON.** AI outputs are validated against a schema; one repair attempt on failure; then a plain-language error. No parsing of AI prose.
15. **Layered code (§3.2).** Routers contain no business logic. Services never touch the database or domain state and return structured results. Repositories are the only database access. Enforced by an architecture test.
16. **Additive-only migrations.** Schema changes add tables/columns; `downgrade()` removes only what that migration added.
17. **Visual restraint.** On the map canvas: node shape plus at most three markers (key-constraint dot, image glyph, review-state outline) and one lens line under each node. A lens may change only that line; it never adds a marker. Colourblind-safe (shape, pattern or text with every colour; never red/green alone). Details on click. Sentence case. No emoji.
18. **One map, one hour.** Warn (not block) above 25 steps or 6 lanes and suggest splitting by phase.
19. **No AGPL or GPL dependencies.** The app may become licensed IP (for example, do not use PyMuPDF).
20. **One design system.** All colours, type, spacing and radii come from `shared/design_tokens.json`; components use tokens only, never raw colour values. The HTML export uses the same tokens. Every screen meets WCAG 2.1 AA contrast and has 0 serious or critical automated accessibility violations. The UI never computes layout; it draws the backend layout.
21. **Private repository, plain-language README.** Code is pushed only to Eric's designated private GitHub repository. README.md follows Appendix D, is written for a non-technical reader, and is updated in the same increment as any change to installing, starting, updating or configuring the app.
22. **Gap analysis is advisory and on demand.** It runs only when Eric starts it and never changes the map by itself. Internal findings carry evidence from every side they compare. External findings carry sources actually returned by the web search in the same request, pass the GX checks and the verifier, and are always provenance `R`. External research sends only an approved brief that has passed the confidentiality scan; transcripts, documents and map content are never sent to web search.
23. **Sensemaking integrity (§3.12.9).** The SME's own meaning comes first: SME signifiers and terms are observed data; the model's interpretations of stories, patterns and work types are inferred and shown separately. Stories told once are kept and flagged, not discarded. Interview claims are tagged official, lived or unclear, and the interview is always labelled work-as-disclosed. Work types need quoted evidence cues. Natural talent and know-how are recorded at role level only. All UI copy, prompts and exports use non-blaming vocabulary. The As done view shows only what lived accounts or traces support; gaps are shown as "not described", never filled with invented steps.

## Code structure (PRD §3.2)
- routers/: HTTP only; call exactly one action.
- actions/ and pipeline/: business rules, state transitions, failure classification, retries, user messages, audit.
- services/: shared mechanics; explicit inputs; return Ok/Err; never import db, repositories or actions; never mutate state.
- repositories/: the only database access.
- domain/: models, enums, result type.
- Only services/ai_service.py imports the anthropic SDK.
- Frontend: components/ never fetch; hooks/ are the only callers of api/; features/ compose screens.
- Extract to a service only for non-domain mechanics with 2+ callers. No god services, no leaky services.

## AI grounding (PRD §3.8)
Every AI claim needs segment IDs, a verbatim quote and (if inferred) a basis. Claims failing segment, quote, number or role checks are rejected and logged, never shown on the map. No outside knowledge. Unknowns become questions, not elements. Confidence is computed with a breakdown, never self-reported. Names on the redaction list never appear outside the three owner-only screens. Gap analysis (§3.11) is advisory: it never changes the map; external findings must cite sources returned by the same search and pass GX1–GX6 and the verifier; web research sends only the approved, scan-clean brief.

## Sensemaking (PRD §3.12, Appendices E and F)
- Five lenses per interview: Flow, Stories, Know-how (ASHEN), Work type (Cynefin-informed), Reality gap (official · lived · documented · traced).
- SME meaning first: SME signifiers and terms are observed; model interpretations are inferred and shown separately. Keep single-account stories.
- Work type needs quoted cues; complex steps are judgment steps; complex or chaotic steps never carry automation flags.
- Codebook tiers: invariants never change; conventions may be overridden with a reason; emergent themes are proposed, never forced.
- Non-blaming vocabulary everywhere (banned-words test).
- Interviews follow the Appendix F question bank; answers are anchored to question IDs; marker tags are hints confirmed by quotes; the label is the translation, the quote is the proof.
- Standard interview templates (Appendix F.9; 60-minute Landscape and Practice, 30-minute Follow-up) are generated from question_bank.json only, in Word and Markdown.
- Interview types (Landscape, Practice, Follow-up) follow Appendix F; decision information in/out stitches flows across interviews; strengths and weaknesses feed Preserve / Improve.
- Two views: As done (default, lived and traced evidence only, "not described" connectors instead of invented steps) and As documented.

## UI (PRD §5)
- Tokens only (shared/design_tokens.json → tokens.css). No raw colours in components or features.
- IBM Plex Sans/Mono, self-hosted, weights 400/500. Sentence case. No emoji.
- Map: shape + at most three markers + one lens line. Lenses never add markers.
- The UI never computes layout; it draws the backend layout.
- Every state uses shape or text as well as colour. 0 serious/critical axe violations.
- Every screen has loading, empty and error states in plain language. Avoid disabled buttons; explain what is missing instead.

## Session protocol (PRD §6.1)
Start: read files, git status, ./run_checks.sh, fix anything broken first, tell Eric the plan.
Work in ~30-minute increments. After each: full ./run_checks.sh, review git diff --staged, commit in plain language, update PROJECT_STATE.md, log decisions.
After each increment also push to GitHub. End: update GUIDE.md (and README.md when relevant); at the end of a phase tag it `phase-pN` and push; report card (what works, X of Y checks, pushed yes/no, resume point, next goal).

## Rules
- Verify every library, SDK method and API against the installed version and real docs before use; log it.
- Read files before editing. Cite file:line when describing code. Read errors exactly.
- Scope lock: current phase only; propose extras in one line.
- Contract first: API_CONTRACT.md → backend → frontend → tests, one increment.
- Tests ship with the feature; full suite every time; never delete, skip or weaken a failing test; bug fixes need a failing test first.
- Visual baselines only after Eric approves the screenshot.
- All Claude calls mocked in the default suite; no key or network needed.
- Additive-only migrations. No AGPL/GPL dependencies. No secrets in code, DB, logs, fixtures or git.
- Three failed attempts → stop and report options, including reverting.
- Push to the private GitHub repository after every checkpoint; tag every phase (phase-pN). Never make the repository public.
- The secret check must pass: no API key, `.env` or `data/` ever committed.
- README.md (PRD Appendix D) is for a non-technical owner; update it in the same increment as any change to installing, starting, updating or configuring.
- "Done" = checks green, committed, pushed, PROJECT_STATE.md and GUIDE.md (and README.md when relevant) updated.
- Speak to Eric in outcomes; give options with a recommendation; exact commands only when unavoidable, with what success looks like.

## Quality bar
p95 < 200 ms on non-AI endpoints · 0 warnings (ruff, mypy, eslint, tsc) · architecture, token-sync and no-raw-colour tests green · coverage ≥ 85% on services and actions · axe 0 serious/critical · privacy scan 0 hits · full suite green incl. golden baselines G1–G7 and approved visual baselines · secret and README checks green · publish quality card Q1–Q9 green.
