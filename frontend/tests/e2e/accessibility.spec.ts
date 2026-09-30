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
    } finally {
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
