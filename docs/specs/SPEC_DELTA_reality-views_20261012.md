# Spec Delta: Reality views and v1.12 coherence review | Status: DRAFT for Eric's approval | Targets: PRD v1.12 §0–§2, §3.2–3.5, §3.7–3.8, §3.12.12, §3.15–3.18, §4–4.1, §5.2–5.12, §6–7, §8–10, Appendices A.12, B, C, H

## 0. What you're getting (plain language)
- A new optional module, **Reality views**: seven read-only pictures of a published map that show executives how actual work differs from the manual **and from what the organisation intends**, with the size of every gap and where the fix lies (keep the workaround, correct the practice, or rewrite the rule).
- Every number and sentence on those views is calculated from verified evidence. The AI writes none of it.
- The PRD now matches what is already built (seven lenses, the anti-drift safeguards, exceptions and the usual route, the real endpoint names), and three new binding constraints guard intent, the Reality views and drift.
- Nothing already built changes, except one optional colour clean-up on the review map that waits for your approval of a new screenshot.

## 1. Scope
**IN (P13a–P13d, after P10b and P12 close):** intent statements (documents or owner-stated); deterministic discrepancy engine D1–D14 with deltas, impact classes, verdicts and persistent X codes; one frozen snapshot per version; seven Reality views; Reality pack (offline HTML, A3 and 16:9 print layouts); automated Reality checks RQ1–RQ10; fixture A.12; golden baseline G11; enum sync check.
**IN (documentation only, already built):** signal strength, instruction lock, run records, refresh check and change report, exceptions and the usual route, lane boundaries, capability notes, the seventh lens, the built endpoint names.
**OUT (not built now):** a future-state (to-be) designer; AI-written executive text; `.pptx` files; a dark pack cover; editing stories and glossary terms; any single-case or per-person figure; live process mining (all in PRD §1.4 or §10).

## 2. Binding constraints restated
PRD §2 items 1–27 apply in full (CLAUDE.md carries them word for word). The ones this delta leans on:
- 1 Evidence before map · 2 Grounded or rejected · 4 Silence is not contradiction · 9 Facts, interpretation, recommendation separate · 10 Roles, not people · 13 Every AI call mockable · 14 Strict JSON · 15 Layered code · 16 Additive-only migrations · 17 Visual restraint (review canvas; Reality views follow §5.12) · 19 No GPL/AGPL · 20 One design system; the UI never computes layout · 24 System data describes the process, never people (5-case floor).
- **25 (new) Intent is evidence, never aspiration.** **26 (new) Reality views are computed, never generated.** **27 (new) No silent drift.**
Constraints 11 (images), 12 (secrets), 18 (one map, one hour), 21 (repository) and 22 (gap analysis) are not implicated beyond their existing checks.
*(The spec-delta skill's default constraint list belongs to another project, the Talent Intelligence Tool, and does not apply here.)*

## 3. Data model changes
Migration **0015**, additive only: tables `intent_statements`, `intent_conflicts`, `discrepancy_items`, `reality_snapshots`; source kind `policy_or_charter`. `downgrade()` drops only these four tables (the source kind is a value, not a column). No existing column changes. PRD §3.5 now also lists the columns earlier migrations added (`claims.frequency`, `map_versions.run_record`, `map_versions.system_traces`, `elements.disposition_note`, `elements.value_override_note`).

## 4. API contract
New (PRD §4, "Intent and Reality"): intent CRUD; **AI** `POST /engagements/{id}/intent/extract`; **AI** `POST /versions/{vid}/intent/compare`; `PATCH /intent-conflicts/{cid}`; `GET /versions/{vid}/discrepancies`; `PUT /discrepancy-items/{code}/verdict`; `GET /versions/{vid}/reality`; `GET /versions/{vid}/reality/export?layout=a3|slide`; `PUT /settings/modules` gains `reality_views_enabled`. AI endpoints return `202 {job_id}` and are exempt from the 200 ms gate; every other endpoint meets p95 < 200 ms on the fixture. Every response with figures carries the figure label (measured · stated · documented · target · mixed); intent carries its origin and either its quote (redacted) or its owner role and date. Errors use the standard shape; `409` for exports of unpublished or non-green versions.
Reconciled (already built): stories and glossary per version (read-only), no answer-block endpoint, "Map checks" tab label, every built endpoint now listed (§4 and §4.1).

## 5. Frontend changes
New nav item **Reality** (Optional, after Registers, only while the module is on); `features/reality/` (RealityScreen, ViewSwitcher, IntentCard, DiscrepancyCard); `components/reality/` (one component per view plus badges, chips, pills, legend, table equivalent) drawing **backend geometry only**; panel section 12 Discrepancies; impact tokens in `shared/design_tokens.json`; Leadership reads the shared snapshot. Untouched: the review canvas, its markers and lenses (except the optional coral clean-up, baseline approval required), every other screen.

## 6. Phased build plan
| Phase | Delivers | Tests | Gate and commit message |
|---|---|---|---|
| P13a | Migration 0015, enums B.44–B.50 + enum sync, intent prompts (mocked, locked), `intent`/`discrepancies`/`verdicts` services, endpoints, Delete respects intent, fixture A.12 | D1–D14 detected and not detected (table-driven), RT1–RT8, verdict override, code stability, no AI call while classifying, latency | `./run_checks.sh` green · "The app can say how practice differs from the manual and from what the organisation intends" |
| P13b | Snapshot, freeze on publish, geometry, copy templates; Reality screen with Glance, Reality stack, Fix or keep; Intent and Discrepancies cards; panel section; Leadership on the snapshot | Byte-identical snapshot, freeze, template-only copy, RQ1–RQ6, axe, table equivalents | green · "Executives can see at a glance how far reality is from the manual and the promise" |
| P13c | Redline, Where the time goes, Belief vs evidence, Typical case | 5-case composite, belief medians, waits on connectors, RQ7 | green · "The Redline, time, belief and typical-case views explain why the gaps happen" |
| P13d | Reality pack, RQ1–RQ10 in checks, G11, visual baselines after approval, README and GUIDE, comprehension test with Eric | Pack offline, no images/quotes/names, RQ9 across views, Leadership and pack | green, tag `phase-p13` · "The Reality pack prints for the board, and every number in it matches the app" |
**Regression list (must stay byte-identical):** G1–G10, the review visual baselines (unless Eric approves the coral clean-up), the instruction lock, every prior suite, the Playwright smoke path.

## 7. Acceptance criteria
PRD §7.1 criteria **95–118**, plus the standing quality bar: p95 < 200 ms on non-AI endpoints · 0 warnings (ruff, mypy, eslint, tsc) · full suite green including every golden baseline, RQ1–RQ10 and the enum sync and instruction lock checks.

## 8. Verbatim prompts
### Kickoff prompt (start P13)
Use the PRD §8 **Feature prompt: Reality views** word for word. It tells Claude Code to read CLAUDE.md, PROJECT_STATE.md, DECISIONS.md and the PRD first, check the base is clean, and build P13a→P13d.
### Resume prompt
Use the PRD §8 **Resume prompt** (it recovers from PROJECT_STATE.md and verifies a clean, green base before continuing).
### Bug-fix prompt
Use the PRD §8 **Bug-fix prompt** (reproduce with a failing test first, fix in the right layer, then the full regression).
### Update prompt (now, for this PRD revision)
Use the PRD §8 **Update prompt** (v1.12): impact table first, PRD committed on its own, CLAUDE.md synced (items 1–27), then P10b, P12 and P13 in order.

## 9. Assumptions made (Eric was not asked)
1. Reality views is an **optional module, off by default** (decision A pattern) and starts after P10b and P12 close.
2. Executive outputs are **print layouts of one HTML file** (A3 and 16:9) rather than PDF or PPTX libraries.
3. Thresholds: 5% show threshold, 50% time rule (shared with `estimate_gap`), 5-minute wait floor, ×1.5 belief factor, ±10-point verdict margin, 5-case floor. All are versioned constants Eric can change later.
4. The term **impact class** replaces X-Ray's "severity" because "severity" already means high/medium/low in gap analysis; X-Ray's "shadow system" is called **workaround**.
5. Discrepancy IDs use the prefix **X** so they never collide with exception routes, guardrails, lint or quality IDs.
6. Fixture A.12 extends the load-control fixture with a four-clause charter and one owner-stated target; G1–G10 are unaffected.

## 10. Future upgrades (document, do not build)
A future-state designer from confirmed verdicts; a trend view across versions (codes are already stable); a dark pack cover and `.pptx` export; editing stories and glossary terms.

**Risk note:** the most likely misreading is letting the frontend size or place Reality marks itself ("it's only a chart"). Constraint 20 and §5.12.4 forbid it: the backend computes the geometry, the UI draws it, and RQ1/RQ7 test it.
