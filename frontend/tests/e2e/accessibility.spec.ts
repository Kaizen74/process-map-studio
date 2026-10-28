import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { seriousViolations, watchExternalRequests } from "./helpers";

const SOP = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../backend/tests/fixtures/engagement_load_control/sop_LC-07.docx",
);

// PRD §6.2 item 7 and acceptance 23: 0 serious/critical axe violations on every screen built so
// far; fonts are self-hosted and no request leaves the app.

test.describe("accessibility and offline assets", () => {
  for (const [name, path, ready] of [
    ["Home", "/", /steps done/],
    ["Settings", "/settings", /No key saved yet|Saved key/],
    ["Page not found", "/nowhere", /doesn't exist/],
  ] as const) {
    test(`${name} has no serious or critical violations`, async ({ page, baseURL }) => {
      const external = watchExternalRequests(page, baseURL ?? "");
      await page.goto(path);
      await expect(page.getByText(ready).first()).toBeVisible();
      await page.evaluate(() => document.fonts.ready);
      expect(await seriousViolations(page)).toEqual([]);
      expect(external).toEqual([]);
    });
  }

  test("Settings with connection results shown has no serious or critical violations", async ({ page }) => {
    await page.goto("/settings");
    await page.getByRole("button", { name: "Test connection" }).click();
    await expect(page.getByRole("group", { name: "Connection test results" })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
  });

  test("Home with an engagement card and the engagement's screens have no serious or critical violations", async ({
    page,
    request,
  }) => {
    // About ten screens, each with an accessibility scan: 25 to 30 s measured (2026-10-15), so it
    // gets its own limit; overrunning the default 30 s left its engagement behind for the next tests.
    test.setTimeout(60_000);
    // Created through the API and removed afterwards, so the first-run smoke test still starts empty.
    const created = await request.post("/api/engagements", { data: { name: "Load control" } });
    expect(created.status()).toBe(201);
    const { id } = (await created.json()) as { id: string };
    try {
      await page.goto("/");
      await expect(page.getByRole("link", { name: "Load control" })).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);

      await page.getByRole("link", { name: "Load control" }).click();
      await expect(page).toHaveURL(new RegExp(`/engagements/${id}/setup$`));
      await expect(page.getByRole("navigation", { name: "Engagement steps" })).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);

      // PRD v1.10 §5.4: the Interview screen's templates (always available).
      await page.goto(`/engagements/${id}/interview`);
      await expect(page.getByRole("region", { name: "Practice (60 min)" })).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);
      // C5a: an interviewee is added by stakeholder group (roles only, never a name), on the Guide tab.
      await page.getByRole("tab", { name: "Guide" }).click();
      const interviewees = page.getByRole("region", { name: "Interviewees" });
      await interviewees.getByRole("button", { name: "Add interviewee" }).click();
      const profileForm = interviewees.getByRole("form", { name: "Add interviewee" });
      await profileForm.getByRole("textbox", { name: "Stakeholder group" }).fill("Ramp");
      expect(await seriousViolations(page)).toEqual([]);
      await profileForm.getByRole("button", { name: "Add interviewee" }).click();
      await expect(interviewees.getByRole("list", { name: "Interviewees" })).toContainText("Ramp");
      expect(await seriousViolations(page)).toEqual([]);
      // G2: a tailored guide for that interviewee, downloadable as Word or Markdown.
      await interviewees.getByRole("button", { name: "Make guide for Ramp" }).click();
      const word = interviewees.getByRole("link", { name: "Download Word guide for Ramp" });
      await expect(word).toBeVisible();
      const file = await request.get((await word.getAttribute("href")) ?? "");
      expect(file.status()).toBe(200);
      expect(file.headers()["content-disposition"]).toContain("interview-guide-");
      expect(await seriousViolations(page)).toEqual([]);
      // C5c: the guide opens as editable cards and saves.
      await interviewees.getByRole("button", { name: "Edit guide for Ramp" }).click();
      const editor = page.getByRole("form", { name: /^Edit .*interview guide/ });
      await editor.getByRole("textbox", { name: "Question M2.2" }).fill("Walk me through the last case you handled, step by step.");
      expect(await seriousViolations(page)).toEqual([]);
      await editor.getByRole("button", { name: "Save guide" }).click();
      await expect(editor.getByRole("status")).toHaveText("Saved.");
      // C5d: the Coverage tab (no draft yet: it says when the report appears).
      await page.getByRole("tab", { name: "Coverage" }).click();
      await expect(page.getByText(/The coverage report appears after the first draft/)).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);

      const upload = await request.post(`/api/engagements/${id}/sources`, {
        multipart: { file: { name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("[00:05] Interviewer: Hello") } },
      });
      expect(upload.status()).toBe(201);
      const sop = await request.post(`/api/engagements/${id}/sources`, {
        multipart: { file: { name: "sop.docx", mimeType: "application/octet-stream", buffer: readFileSync(SOP) } },
      });
      const { id: sopId } = (await sop.json()) as { id: string };
      // Files are read in the background, one after another; wait until this one has been read
      // (under load this can take longer than a single expect's timeout).
      await expect
        .poll(async () => ((await (await request.get(`/api/sources/${sopId}`)).json()) as { text_status: string }).text_status, {
          timeout: 30_000,
        })
        .toBe("ready");
      await page.goto(`/engagements/${id}/sources?source=${sopId}`);
      await expect(page.getByRole("list", { name: "Passages" })).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);

      await page.goto(`/engagements/${id}/draft`);
      await expect(page.getByRole("heading", { name: "Before drafting" })).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);

      await page.goto(`/engagements/${id}/review`);
      await expect(page.getByText(/There is no draft map to review yet/)).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);

      await page.goto(`/engagements/${id}/published`);
      await expect(page.getByText(/Nothing published yet/)).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);

      await page.goto(`/engagements/${id}/matrix`);
      await expect(page.getByText(/No draft map yet/)).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);

      await page.goto(`/engagements/${id}/gap-analysis`);
      await expect(page.getByText(/Make a draft map first/)).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);

      await page.goto(`/engagements/${id}/leadership`);
      await expect(page.getByText(/Publish a version first/)).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);

      // R7a: System records, off by default (decision A), then on: the screen and the import wizard.
      await page.goto(`/engagements/${id}/system-records`);
      await expect(page.getByText(/System records is switched off/)).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);
      expect((await request.put("/api/settings/modules", { data: { system_records_enabled: true } })).status()).toBe(200);
      await page.reload();
      await expect(page.getByText(/No logs yet/)).toBeVisible();
      await page.getByRole("button", { name: /^More steps/ }).click(); // 2026-10-28: under More
      await expect(page.getByRole("dialog", { name: "More steps" }).getByRole("link", { name: /^System records/ })).toBeVisible();
      await page.keyboard.press("Escape");
      expect(await seriousViolations(page)).toEqual([]);
      const csv = "Case ID,Event Name,Start Time,Performed by\nC1,Opened,2026-03-02 09:00,U1\nC1,Closed,2026-03-02 10:00,U2\n";
      await page.getByTestId("log-file-input").setInputFiles({ name: "extract.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
      await page.getByRole("button", { name: "Upload" }).click();
      await expect(page.getByText("Step 1 of 5: Map columns")).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);
      await page.getByRole("button", { name: "Next: time zone" }).click();
      await page.getByRole("button", { name: "Next: map users to roles" }).click();
      await expect(page.getByText("These are not stored.")).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);
      // R7b: an imported log (6 cases, through the API) opens on matching (no map yet) and Metrics.
      const rows = ["case_id,activity,timestamp,role"];
      for (let n = 0; n < 6; n++) rows.push(`C${n},Opened,2026-03-02 0${n}:00,Ops`, `C${n},Closed,2026-03-02 0${n}:30,Ops`);
      const log = await request.post(`/api/engagements/${id}/event-logs`, {
        multipart: { name: "Six cases", file: { name: "six.csv", mimeType: "text/csv", buffer: Buffer.from(rows.join("\n")) } },
      });
      const held = (await log.json()) as { id: string; column_map: Record<string, string | null> };
      await request.put(`/api/event-logs/${held.id}/column-map`, { data: { columns: held.column_map } });
      const approval = { approved_by_role: "Head of operations", confirm_approval: true };
      expect((await request.post(`/api/event-logs/${held.id}/import`, { data: approval })).status()).toBe(202);
      await expect
        .poll(async () => ((await (await request.get(`/api/event-logs/${held.id}`)).json()) as { status: string }).status)
        .toBe("imported");
      await page.goto(`/engagements/${id}/system-records?log=${held.id}`);
      await expect(page.getByText(/Draft the map first/)).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);
      await page.getByRole("tab", { name: "Metrics" }).click();
      await expect(page.getByRole("region", { name: "Variants (top 10)" })).toBeVisible();
      expect(await seriousViolations(page)).toEqual([]);
    } finally {
      await request.put("/api/settings/modules", { data: { system_records_enabled: false } });
      expect((await request.delete(`/api/engagements/${id}`)).status()).toBe(204);
    }
  });

  test("IBM Plex Sans and Mono load from the app itself", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    // Load each face explicitly: `document.fonts.ready` only waits for faces the page has already
    // asked for, so checking right after it raced with the weight-500 face (seen once, 2026-09-26).
    // A face whose file is missing or blocked loads as nothing, so this still fails.
    const loaded = await page.evaluate(async () => {
      const faces = ['12px "IBM Plex Sans"', '500 12px "IBM Plex Sans"', '12px "IBM Plex Mono"'];
      const results = await Promise.all(faces.map((face) => document.fonts.load(face)));
      return results.map((found, i) => found.length > 0 && document.fonts.check(faces[i] ?? ""));
    });
    expect(loaded).toEqual([true, true, true]);
    const family = await page.evaluate(() => getComputedStyle(document.body).fontFamily);
    expect(family).toContain("IBM Plex Sans");
  });
});

test("the accessibility check catches a real problem (planted)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/steps done/)).toBeVisible();
  await page.evaluate(() => {
    const bad = document.createElement("div");
    bad.innerHTML =
      '<p style="color:#eeeeee;background:#ffffff">Barely visible text</p><input type="text">';
    document.querySelector("main")?.appendChild(bad);
  });
  const found = (await seriousViolations(page)).map((v) => v.split(":")[0]);
  expect(found).toEqual(expect.arrayContaining(["color-contrast", "label"]));
});
