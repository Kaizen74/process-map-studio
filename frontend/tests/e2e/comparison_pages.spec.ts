import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { seriousViolations } from "./helpers";

// The country comparison pages (2026-11-13, Eric's brief acceptance test 7; DECISIONS 98), as the
// backend renders them for the Arden and Belmar fixture maps (written by
// backend/tests/unit/test_countries_return.py). Printed in a real browser: no page is cut off, no
// text under 11 px, no request outside the file, 0 serious or critical accessibility problems.
const FIXTURES = resolve(dirname(fileURLToPath(import.meta.url)), "../fixtures");

for (const layout of ["a3", "slide"] as const) {
  test(`the ${layout} country comparison pages print cleanly and are accessible`, async ({ page }) => {
    const html = readFileSync(resolve(FIXTURES, `comparison_pages_${layout}.html`), "utf-8");
    const asked: string[] = [];
    const problems: string[] = [];
    page.on("request", (r) => {
      if (!r.url().startsWith("data:") && r.url() !== "about:blank") asked.push(r.url());
    });
    page.on("console", (m) => {
      if (m.type() === "error") problems.push(m.text());
    });
    page.on("pageerror", (e) => problems.push(String(e)));
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.setContent(html, { waitUntil: "load" });
    await page.emulateMedia({ media: "print" });
    const pages = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLElement>("section.page")].map((p) => {
        let smallest = 99;
        let where = "";
        for (const el of p.querySelectorAll("p, span, td, th, li, h1, h2, h3, caption")) {
          if (!(el.textContent ?? "").trim() || el.children.length > 0) continue;
          const size = parseFloat(getComputedStyle(el).fontSize);
          if (size < smallest) {
            smallest = size;
            where = (el.textContent ?? "").trim().slice(0, 30);
          }
        }
        return { page: p.dataset.section ?? "", overflow: p.scrollHeight - p.clientHeight, smallest, where };
      }),
    );
    expect(pages.map((p) => p.page)).toEqual(["summary", "decides", "work", "only"]);
    for (const p of pages) {
      expect(p.overflow, `${layout} page ${p.page} is cut off`).toBeLessThanOrEqual(0);
      expect(p.smallest, `${layout} page ${p.page}: "${p.where}" under 11 px`).toBeGreaterThanOrEqual(11);
    }
    // Visual baselines (Eric approved the 16:9 summary and Who decides pages, 2026-11-13, with the
    // singular wording fix). Soft, as for the Reality pack: the rest of the check keeps running.
    if (layout === "slide") {
      for (const section of ["summary", "decides"]) {
        await expect
          .soft(page.locator(`section[data-section="${section}"]`))
          .toHaveScreenshot(`country-pages-slide-${section}.png`);
      }
    }
    await page.emulateMedia({ media: "screen" });
    expect(await seriousViolations(page)).toEqual([]);
    expect(asked, "the pages asked for something outside the file").toEqual([]);
    expect(problems, "the pages logged errors").toEqual([]);
    expect(html.includes("Rosa Delgado") || html.includes("Tomas Vrba"), "a hidden name in the pages").toBe(false);
  });
}
