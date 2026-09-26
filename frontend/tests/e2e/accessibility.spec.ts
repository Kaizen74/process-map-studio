import { expect, test } from "@playwright/test";
import { seriousViolations, watchExternalRequests } from "./helpers";

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

  test("IBM Plex Sans and Mono load from the app itself", async ({ page }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings" })).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    const loaded = await page.evaluate(() => [
      document.fonts.check('12px "IBM Plex Sans"'),
      document.fonts.check('500 12px "IBM Plex Sans"'),
      document.fonts.check('12px "IBM Plex Mono"'),
    ]);
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
