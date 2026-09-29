import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

/** WCAG 2.1 A/AA violations of serious or critical impact on the current page (PRD §5.10). */
export async function seriousViolations(page: Page): Promise<string[]> {
  // Measure the settled page: a toast still fading in (120 ms) reads as low contrast mid-way.
  // Looping animations (skeleton shimmer) never finish, so only finite ones are waited for.
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every((a) => a.playState !== "running" || a.effect?.getTiming().iterations === Infinity),
  );
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.help} → ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

/** Records every request the page makes that leaves the app's own address. */
export function watchExternalRequests(page: Page, baseURL: string): string[] {
  const external: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    if (!url.startsWith(baseURL) && !url.startsWith("data:")) external.push(url);
  });
  return external;
}

// Built by concatenation so the source never contains a key-shaped string (secret check).
export const FAKE_KEY = "sk-" + "ant-" + "api03-" + "E2eTest".repeat(6) + "W9zz";

/**
 * Privacy scan (PRD §6.2 item 8): the rendered text of the page, leaving out the three owner-only
 * places (speaker-mapping card, redaction list, correction editor), which carry data-owner-only.
 */
export async function publicText(page: Page): Promise<string> {
  return page.evaluate(() => {
    const copy = document.body.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("[data-owner-only]").forEach((el) => el.remove());
    // Form values (inputs, selects) are not in textContent; include them as well.
    const values = Array.from(copy.querySelectorAll("input, textarea"))
      .map((el) => (el as HTMLInputElement).value)
      .join(" ");
    return `${copy.textContent ?? ""} ${values} ${document.title}`;
  });
}

// PRD Appendix A.1: the fictional SME whose name must never appear outside the owner-only places.
export const FIXTURE_NAME = "Priya Nair";
