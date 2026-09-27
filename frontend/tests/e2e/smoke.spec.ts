import { expect, test } from "@playwright/test";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { FAKE_KEY, publicText, seriousViolations } from "./helpers";

// First-run path through the real app (built frontend + backend, Claude mocked).
test("first run: add name and key, test the connection, checklist ticks", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("0 of 3 steps done")).toBeVisible();

  await page.getByRole("link", { name: "Add your Claude API key" }).click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByText("No key saved yet.")).toBeVisible();

  const nameCard = page.getByRole("region", { name: "Your name" });
  await nameCard.getByLabel("Your name").fill("Eric Yim");
  await nameCard.getByRole("button", { name: "Save name" }).click();
  await expect(page.getByText("Your name was saved.")).toBeVisible();

  const connection = page.getByRole("region", { name: "Claude connection" });
  await connection.getByLabel("Claude API key").fill(FAKE_KEY);
  await connection.getByRole("button", { name: "Save key" }).click();
  await expect(connection.getByText(`ending in ${FAKE_KEY.slice(-4)}`)).toBeAttached();
  expect(await page.content()).not.toContain(FAKE_KEY);

  await connection.getByRole("button", { name: "Test connection" }).click();
  const results = page.getByRole("group", { name: "Connection test results" });
  await expect(results).toContainText("Connected. Your key works");
  await expect(results.getByRole("listitem").filter({ hasText: "Key valid" })).toContainText("Pass");

  const model = page.getByRole("region", { name: "Model" });
  await expect(model.getByLabel("Model")).toContainText("Claude Opus 5.5 (illustrative mock)");

  await page.getByRole("link", { name: "Engagements" }).click();
  await expect(page.getByText("1 of 3 steps done")).toBeVisible();
  await expect(page.getByText(`Key saved (ending ${FAKE_KEY.slice(-4)})`)).toBeVisible();

  // Reload: settings persist in the (throwaway) .env file, not only in the page.
  await page.reload();
  await expect(page.getByText("1 of 3 steps done")).toBeVisible();
});

// Phase P1 path: create an engagement, set it up, upload the PRD sample documents, read one, clean up.
test("engagement: create, set up, upload and read sources, then delete", async ({ page }) => {
  const fixtures = resolve(dirname(fileURLToPath(import.meta.url)), "../../../backend/tests/fixtures/engagement_load_control");

  await page.goto("/");
  await page.getByRole("button", { name: "New engagement" }).click();
  const dialog = page.getByRole("dialog", { name: "New engagement" });
  await dialog.getByLabel("Engagement name").fill("Load control");
  await dialog.getByRole("button", { name: "Create engagement" }).click();

  // New engagement opens Setup, with the guided path in the top bar.
  await expect(page.getByRole("heading", { level: 1, name: "Setup" })).toBeVisible();
  const steps = page.getByRole("navigation", { name: "Engagement steps" });
  await expect(steps.getByRole("link", { name: /^Setup, not started.*recommended next step/ })).toBeVisible();

  const scope = page.getByRole("region", { name: "Process scope" });
  await scope.getByLabel("Trigger").fill("Flight scheduled");
  await scope.getByLabel("End point").fill("Final load sheet issued");
  await scope.getByLabel("Confidential terms").fill("Acme Ground Services");
  await scope.getByLabel("Confidential terms").press("Enter");
  await scope.getByRole("button", { name: "Save scope" }).click();
  await expect(page.getByText("Scope saved.")).toBeVisible();
  await expect(steps.getByRole("link", { name: /^Setup, done/ })).toBeVisible();

  const roles = page.getByRole("region", { name: "Roles and lanes" });
  for (const name of ["Load controller", "Load control lead"]) {
    await roles.getByLabel("Role name").fill(name);
    await roles.getByRole("button", { name: "Add role" }).click();
    await expect(page.getByText(new RegExp(`${name} added as lane`))).toBeVisible();
  }
  await roles.getByRole("button", { name: "Move Load control lead up" }).click();
  await expect(roles.getByRole("figure", { name: "Lane preview, top to bottom" }).getByRole("listitem").first()).toHaveText(
    "Load control lead",
  );

  // Sources: upload the PRD sample documents; an unsupported file is refused.
  await steps.getByRole("link", { name: /^Sources/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Sources" })).toBeVisible();
  await page.getByTestId("source-file-input").setInputFiles([
    join(fixtures, "sop_LC-07.docx"),
    join(fixtures, "jd_load_controller.docx"),
    join(fixtures, "manual_extract.pdf"),
  ]);
  await expect(page.getByText("3 files uploaded.")).toBeVisible();
  const table = page.getByRole("table", { name: "Sources for this engagement" });
  await expect(table.getByRole("row")).toHaveCount(4);
  await expect(table.getByRole("combobox", { name: "Kind of jd_load_controller.docx" })).toHaveValue("job_description");
  await expect(page.getByText("Add an interview transcript")).toBeVisible();

  await table.getByRole("button", { name: "sop_LC-07.docx", exact: true }).click();
  const viewer = page.getByRole("region", { name: "sop_LC-07.docx" });
  await expect(viewer.getByRole("listitem").filter({ hasText: "§3.1" }).first()).toContainText(
    "The Load Controller shall prepare the preliminary load plan by T-90.",
  );
  await page.reload();
  await expect(page.getByRole("region", { name: "sop_LC-07.docx" })).toBeVisible();

  // Home shows the card; deleting it removes the engagement.
  await page.getByRole("link", { name: "Engagements" }).click();
  await expect(page.getByText("3 sources · last updated")).toBeVisible();
  await page.getByRole("button", { name: "Delete Load control" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Delete engagement" }).click();
  await expect(page.getByText("Engagement deleted.")).toBeVisible();
  await expect(page.getByText(/No engagements yet/)).toBeVisible();
});

// Phase P3 path: the Appendix A engagement set up exactly as the mock answers expect (roles with
// their aliases, speakers mapped), then a draft made from the Draft screen with Claude mocked.
// Runs after the first-run test above, which saved the key. Cleans up after itself.
const ROLES: [string, string[]][] = [
  ["Load controller", ["LC", "Load Controller"]],
  ["Load control lead", ["Load Control Lead"]],
  ["Ramp", ["Ramp Supervisor", "Ramp agent"]],
  ["Airline ops", ["airline"]],
  ["Captain", []],
];
const FIXTURES = resolve(dirname(fileURLToPath(import.meta.url)), "../../../backend/tests/fixtures/engagement_load_control");
const DRAFT_SOURCES = [
  "interview_transcript.txt",
  "sop_LC-07.docx",
  "sop_RP-02.docx",
  "jd_load_control_lead.docx",
  "jd_load_controller.docx",
];

test("draft: create a draft map, watch it finish, see the checked claims", async ({ page, request }) => {
  const created = await request.post("/api/engagements", {
    data: { name: "Load control", trigger: "Flight scheduled", end_point: "Final load sheet issued" },
  });
  const { id } = (await created.json()) as { id: string };
  try {
    const roleIds: Record<string, string> = {};
    for (const [name, aliases] of ROLES) {
      const role = await request.post(`/api/engagements/${id}/roles`, { data: { name, aliases } });
      roleIds[name] = ((await role.json()) as { id: string }).id;
    }
    await page.goto(`/engagements/${id}/sources`);
    await page.getByTestId("source-file-input").setInputFiles(DRAFT_SOURCES.map((name) => join(FIXTURES, name)));
    await expect(page.getByText("5 files uploaded.")).toBeVisible();
    const table = page.getByRole("table", { name: "Sources for this engagement" });
    await expect(table.getByText("Ready")).toHaveCount(5);
    const sources = (await (await request.get(`/api/engagements/${id}/sources`)).json()) as {
      id: string;
      filename: string;
    }[];
    const transcript = sources.find((s) => s.filename === "interview_transcript.txt");
    const mapped = await request.put(`/api/sources/${transcript?.id ?? ""}/speakers`, {
      data: { Interviewer: "interviewer", "Priya Nair": roleIds["Load controller"] },
    });
    expect(mapped.status()).toBe(200);

    await page.reload();
    await page.getByRole("link", { name: "Go to Draft" }).click();
    const checklist = page.getByRole("region", { name: "Before drafting" });
    await expect(checklist.getByText("4 of 4 ready.")).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);

    await page.getByRole("button", { name: "Create draft map" }).click();
    const summary = page.getByRole("region", { name: "Draft v0.1" });
    await expect(summary).toBeVisible({ timeout: 30_000 });
    await expect(summary.getByText("Steps drafted").locator("xpath=following-sibling::dd")).toHaveText("8");
    await expect(summary.getByText("Needs check").locator("xpath=following-sibling::dd")).toHaveText("0");
    await expect(summary.getByText("Open questions").locator("xpath=following-sibling::dd")).toHaveText("5");
    await expect(summary.getByText(/Built from 21 checked claims/)).toBeVisible();
    await expect(page.getByRole("region", { name: "Rejected claims (0)" })).toContainText("No claims were rejected");
    await expect(page.getByRole("button", { name: "Draft again from sources" })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    const text = await publicText(page);
    expect(text.includes("Priya"), "a name shown on Draft").toBe(false);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p4-draft-summary.png"), fullPage: true });
    }

    // Every AI call shows in Settings, as usage only.
    await page.goto("/settings");
    const usage = page.getByRole("region", { name: "AI usage" });
    await expect(usage.getByRole("table")).toBeVisible();
    await expect(usage.getByText(/All time: \d+ calls/)).toBeVisible();
    await expect(usage.getByRole("row").filter({ hasText: "Extracting steps (interview)" })).toHaveCount(3);
    await expect(usage.getByRole("row").filter({ hasText: "Test answer" }).first()).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await usage.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p4-settings-ai-usage.png") });
    }
  } finally {
    expect((await request.delete(`/api/engagements/${id}`)).status()).toBe(204);
  }
});
