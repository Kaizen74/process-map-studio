// Comprehension test kit: the published A.12 example's Glance, Reality stack and Fix or keep views,
// drawn by the built app from the G11 snapshot (the frozen, approved baseline), one PNG each.
// Usage: build the frontend, serve it (npx vite preview --port 4179 in frontend/), then
//   PMS_CHROMIUM_PATH=<chromium> node scripts/make_comprehension_kit.mjs . docs/comprehension_kit http://127.0.0.1:4179
import { createRequire } from "node:module";
import { readFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
const [repo, out, base] = process.argv.slice(2);
const require = createRequire(join(repo, "frontend", "package.json"));
const { chromium } = require("@playwright/test");
const snap = JSON.parse(readFileSync(join(repo, "backend/tests/golden/G11_reality.json"), "utf-8"));
const VID = snap.version_id;
const version = { id: VID, engagement_id: "e1", label: "v1.0", state: "published", created_at: "2026-10-14T09:00:00+00:00",
  published_at: "2026-10-14T10:00:00+00:00", published_by: "Owner", parent_version_id: null };
const engagement = { id: "e1", name: "Load control", process_name: "Aircraft load control", trigger: "", end_point: "",
  in_scope_roles: [], out_of_scope: "", process_kpi: "", industry: "", adjacent_industries: [], confidential_terms: [],
  status: "active", created_at: "2026-09-26T09:00:00+00:00", updated_at: "2026-09-26T10:00:00+00:00" };
const settings = { owner_name: "Owner", model: "claude-opus-5-5", effort: "high", verifier_enabled: true,
  web_research_enabled: false, system_records_enabled: false, gap_analysis_enabled: true, value_enabled: false,
  reality_views_enabled: true, currency: "SGD", default_timezone: "Asia/Singapore", draft_cost_limit_usd: null,
  key_set: true, key_last4: "abcd" };
const routes = {
  "/api/settings": { ...settings, reality_views_enabled: true },
  "/api/engagements/e1": engagement,
  "/api/engagements/e1/versions": [version],
  "/api/engagements/e1/roles": [],
  "/api/engagements/e1/intent": [],
  [`/api/versions/${VID}/reality`]: snap,
};
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.PMS_CHROMIUM_PATH });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.route("**/api/**", (route) => {
  const path = new URL(route.request().url()).pathname;
  const body = routes[path];
  if (body !== undefined) return route.fulfill({ json: body });
  if (path === "/api/engagements/e1/readiness") return route.fulfill({ json: { key_set: true, transcripts_ready: true,
    documents_ready: true, speakers_unmapped: 0, draft_exists: true, blockers_count: 0, nav: {setup: "done", interview: "done", sources: "done", draft: "done", review: "done", published: "done", matrix: "done", gap_analysis: "done", registers: "done", leadership: "done", exports: "done"}, nav_counts: {},
    next_step: "published", missing: [], ready_to_draft: true } });
  return route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "Not found.", details: {} } } });
});
await page.goto(`${base}/engagements/e1/reality?version=${VID}`);
await page.locator(".reality-view__headline").first().waitFor();
const views = [["1-glance", "Glance"], ["2-reality-stack", "Reality stack"], ["3-fix-or-keep", "Fix or keep"]];
for (const [file, name] of views) {
  await page.getByRole("radiogroup", { name: "Reality view" }).getByRole("radio", { name }).click();
  await page.locator(".reality-view__headline").waitFor();
  await page.waitForTimeout(300);
  await page.locator("section.reality-view").screenshot({ path: join(out, `${file}.png`), animations: "disabled" });
  console.log("wrote", file, await page.locator(".reality-view__headline").textContent());
}
await browser.close();
