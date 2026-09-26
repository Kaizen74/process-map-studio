import axe from "axe-core";

/**
 * Run axe-core on a rendered element and return serious or critical violations.
 * Colour contrast can't be measured in jsdom; it is checked by the token contrast test and
 * by the browser (Playwright) accessibility checks.
 */
export async function seriousViolations(element: Element): Promise<string[]> {
  const results = await axe.run(element, { rules: { "color-contrast": { enabled: false } } });
  return results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
}
