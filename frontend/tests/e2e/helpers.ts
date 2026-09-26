import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

/** WCAG 2.1 A/AA violations of serious or critical impact on the current page (PRD §5.10). */
export async function seriousViolations(page: Page): Promise<string[]> {
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
