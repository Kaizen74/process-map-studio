import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
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
  // Documents alone can be drafted (2026-10-20); the interview is recommended.
  await expect(page.getByText("Recommended, not required:")).toBeVisible();
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
  // A.10 (P4c): the landscape interview with the Ramp duty manager.
  "landscape_ramp_lead.txt",
];

test("draft: create a draft map, watch it finish, see the checked claims", async ({ page, request }) => {
  // The whole journey: draft, review, refresh, publish, export, reopen (each AI stage mocked).
  // The whole journey: about 85 s measured with X3 (2026-10-06), plus R8, and since P13c all
  // seven Reality views with an accessibility scan each: 1.7 to 2.4 min measured (2026-10-15).
  test.setTimeout(240_000);
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
    await expect(page.getByText("6 files uploaded.")).toBeVisible();
    const table = page.getByRole("table", { name: "Sources for this engagement" });
    await expect(table.getByText("Ready")).toHaveCount(6);
    type Listed = { id: string; filename: string; kind: string; text_status: string };
    const sourcesNow = async () =>
      (await (await request.get(`/api/engagements/${id}/sources`)).json()) as Listed[];
    // Its name doesn't say "interview", so it is read as a document until its kind is set.
    const landscape = (await sourcesNow()).find((s) => s.filename === "landscape_ramp_lead.txt");
    const kind = await request.patch(`/api/sources/${landscape?.id ?? ""}`, { data: { kind: "interview_transcript" } });
    expect(kind.status()).toBe(200);
    await expect
      .poll(async () => (await sourcesNow()).find((s) => s.id === landscape?.id)?.text_status, { timeout: 15_000 })
      .toBe("ready");
    const ramp = await request.put(`/api/sources/${landscape?.id ?? ""}/speakers`, {
      data: { Interviewer: "interviewer", "Ramp duty manager": roleIds["Ramp"] },
    });
    expect(ramp.status()).toBe(200);
    const sources = await sourcesNow();
    const transcript = sources.find((s) => s.filename === "interview_transcript.txt");
    const mapped = await request.put(`/api/sources/${transcript?.id ?? ""}/speakers`, {
      data: { Interviewer: "interviewer", "Priya Nair": roleIds["Load controller"] },
    });
    expect(mapped.status()).toBe(200);

    await page.reload();
    await page.getByRole("link", { name: "Go to Draft" }).click();
    const checklist = page.getByRole("region", { name: "Before drafting" });
    await expect(checklist.getByText("3 of 3 ready.")).toBeVisible();
    // P12: the sample has an interview and an SOP, so the map's signal is Strong.
    await expect(checklist.getByText(/Signal strength: Strong/)).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);

    await page.getByRole("button", { name: "Create draft map" }).click();
    const summary = page.getByRole("region", { name: "Draft v0.1" });
    await expect(summary).toBeVisible({ timeout: 30_000 });
    // v1.10 A.5: ten steps; A.9: three lines rest only on the order of mentioning (+3 questions);
    // A.8 (C2): three decisions and approvals whose kind of work isn't clear (+3 questions).
    // A.10 (C3): the loading report hand-off explains one of those lines (−1 question).
    await expect(summary.getByText("Steps drafted").locator("xpath=following-sibling::dd")).toHaveText("10");
    await expect(summary.getByText("Needs check").locator("xpath=following-sibling::dd")).toHaveText("0");
    await expect(summary.getByText("Open questions").locator("xpath=following-sibling::dd")).toHaveText("10");
    // v1.10 A.1, A.5, A.8 (C1); A.10 (C3): + the landscape interview and two information flows
    await expect(summary.getByText(/Built from 40 checked claims/)).toBeVisible();
    await expect(page.getByRole("region", { name: "Rejected claims (0)" })).toContainText("No claims were rejected");
    await expect(page.getByRole("button", { name: "Draft again from sources" })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    const text = await publicText(page);
    expect(text.includes("Priya"), "a name shown on Draft").toBe(false);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p4-draft-summary.png"), fullPage: true });
    }

    // Review: the draft map drawn from the backend layout (P5).
    await summary.getByRole("link", { name: "Start reviewing" }).click();
    await expect(page.getByText("0 of 10 steps reviewed")).toBeVisible();  // v1.10 A.5: ten steps
    await expect(page.locator(".version-banner").getByText(/Signal strength: Strong/)).toBeVisible();
    await expect(page.getByRole("button", { name: /^Activity, Draft load plan, Load controller/ })).toBeVisible();
    await expect(page.getByRole("group", { name: "Load controller lane, 6 steps" })).toBeAttached();
    expect(await seriousViolations(page)).toEqual([]);
    // Visual baseline (PRD §6.2 item 9): the sample's Review screen, plain lens, nothing
    // selected, at both sizes; at most 0.5% of pixels may differ. P7 added the quality card button
    // and Publish to the banner; with PMS_SCREENSHOT_DIR the run first saves candidates for
    // Eric to approve (a baseline is never written by a test run).
    const shots = process.env.PMS_SCREENSHOT_DIR;
    const still = { animations: "disabled", caret: "hide" } as const;
    if (shots) {
      await page.screenshot({ path: join(shots, "p7-review-1440x900.png"), ...still });
      await page.setViewportSize({ width: 1080, height: 800 });
      await page.screenshot({ path: join(shots, "p7-review-1080x800.png"), ...still });
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.getByRole("radio", { name: "Table" }).click();
      await expect(page.getByRole("table", { name: "Steps in process order" })).toBeVisible();
      await page.screenshot({ path: join(shots, "p7-review-table.png"), fullPage: true, ...still });
      await page.getByRole("radio", { name: "Map" }).click();
      await expect(page.getByRole("radiogroup", { name: "Lens" })).toBeVisible();
    }
    // V2-V4 (§3.12.11): the map opens As done; As documented draws the documents' version (with
    // Approve load plan, A.9), and the Work type lens shows A.8's kinds of work.
    const viewSwitch = page.getByRole("radiogroup", { name: "View" });
    await expect(viewSwitch.getByRole("radio", { name: "As done" })).toHaveAttribute("aria-checked", "true");
    const approvePlan = page.getByRole("button", { name: /^Approval, Approve load plan/ });
    await expect(approvePlan).toHaveCount(0);
    if (shots) await page.screenshot({ path: join(shots, "v4-as-done-1440x900.png"), ...still });
    await viewSwitch.getByRole("radio", { name: "As documented" }).click();
    await expect(approvePlan).toBeVisible();
    await expect(page.getByRole("button", { name: /^Activity, Read report at aircraft/ })).toHaveCount(0);
    expect(await seriousViolations(page)).toEqual([]);
    if (shots) await page.screenshot({ path: join(shots, "v4-as-documented-1440x900.png"), ...still });
    await viewSwitch.getByRole("radio", { name: "As done" }).click();
    const showOther = page.getByRole("checkbox", { name: "Show the other view" });
    await showOther.click(); // the choice lives in the address, so it applies a moment later
    await expect(showOther).toBeChecked();
    await expect(page.getByRole("button", { name: /Approve load plan.*only in the documented version$/ })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    if (shots) await page.screenshot({ path: join(shots, "v4-as-done-with-other-1440x900.png"), ...still });
    await showOther.click();
    await expect(showOther).not.toBeChecked();
    await page.getByRole("radiogroup", { name: "Lens" }).getByRole("radio", { name: "Work type" }).click();
    await expect(page.locator(".map-lens", { hasText: /^Complexproposed$/ })).toBeVisible(); // A.8
    expect(await seriousViolations(page)).toEqual([]);
    if (shots) await page.screenshot({ path: join(shots, "v4-as-done-work-type-1440x900.png"), ...still });
    // X3: the Exceptions lens, from the backend's report of this view (real backend, Claude mocked).
    await page.getByRole("radiogroup", { name: "Lens" }).getByRole("radio", { name: "Exceptions" }).click();
    await expect(page.locator(".map-lens", { hasText: /^Workaround$/ })).toBeVisible(); // Read report at aircraft
    await expect(page.locator(".map-lens", { hasText: /^Exception$/ })).toHaveCount(2);
    expect(await seriousViolations(page)).toEqual([]);
    if (shots) await page.screenshot({ path: join(shots, "x3-as-done-exceptions-1440x900.png"), ...still });
    if (shots) {
      // P13a (PRD §5.2): the Time lens's wait hatch, for Eric to compare coral with the time colour.
      await page.getByRole("radiogroup", { name: "Lens" }).getByRole("radio", { name: "Time" }).click();
      await expect(page.locator(".map-bar__wait").first()).toBeVisible();
      await page.screenshot({ path: join(shots, "p13a-time-lens-1440x900.png"), ...still });
    }
    await page.getByRole("radiogroup", { name: "Lens" }).getByRole("radio", { name: "Plain" }).click();
    await expect(approvePlan).toHaveCount(0);
    // Soft (2026-10-01): a changed screen still fails the check until Eric approves new baselines,
    // but the rest of the journey keeps running, so other regressions are still caught.
    await expect.soft(page).toHaveScreenshot("p7-review-1440x900.png");
    await page.setViewportSize({ width: 1080, height: 800 });
    // P12 visual pass: every step of the guided path stays in view at the smaller size (the bar
    // wraps instead of cutting off Registers, Leadership and Exports).
    const bar = page.getByRole("navigation", { name: "Engagement steps" });
    const barBox = await bar.boundingBox();
    for (const step of await bar.getByRole("link").all()) {
      const box = await step.boundingBox();
      const name = await step.getAttribute("aria-label");
      expect(box && barBox && box.x + box.width <= barBox.x + barBox.width + 0.5, `${name} is cut off`).toBe(true);
    }
    await expect.soft(page).toHaveScreenshot("p7-review-1080x800.png");
    await page.setViewportSize({ width: 1440, height: 900 });
    // P7: Publish on an unreviewed draft is refused with what to fix, in the quality card popover.
    await page.getByRole("button", { name: "Publish" }).click();
    const blocked = page.getByRole("dialog", { name: "Publish blocked" });
    await expect(blocked.getByRole("list", { name: "What to fix before publishing" })).toContainText(
      "hasn't been reviewed yet",
    );
    await expect(blocked.getByRole("list", { name: "Quality checks" })).toContainText("Fully reviewed");
    expect(await seriousViolations(page)).toEqual([]);
    if (shots) await page.screenshot({ path: join(shots, "p7-publish-blocked.png"), ...still });
    await blocked.getByRole("button", { name: "Close" }).click();
    await page.getByRole("button", { name: /^Activity, Load and return LIR/ }).click();
    const panel = page.getByRole("complementary", { name: "Step details" });
    await expect(panel.getByRole("heading", { name: "Load and return LIR" })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    expect((await publicText(page)).includes("Priya"), "a name shown on Review").toBe(false);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p5-review-selected.png"), fullPage: true });
    }
    // Evidence opens its source at the exact passage, quote highlighted, names hidden.
    await panel.getByRole("button", { name: /Open interview_transcript.txt at 21:50/ }).click();
    const viewer = page.getByRole("complementary", { name: "Source" });
    await expect(viewer.locator("mark")).toContainText("Ramp loads the aircraft");
    expect(await seriousViolations(page)).toEqual([]);
    expect((await publicText(page)).includes("Priya"), "a name shown in the source viewer").toBe(false);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p5-review-evidence.png") });
    }
    await viewer.getByRole("button", { name: /Back to Load and return LIR/ }).click();
    await expect(panel.getByRole("region", { name: "Evidence" })).toBeVisible();

    // P6: select from every entry point — map node (above), progress segment, RACI row, table row.
    const heading = (name: string) =>
      page.getByRole("complementary", { name: "Step details" }).getByRole("heading", { name });
    await page.getByRole("button", { name: /^Approve load plan, / }).click();
    await expect(heading("Approve load plan")).toBeVisible();
    await page.getByRole("tabpanel").getByRole("button", { name: "Issue load sheet", exact: true }).click();
    await expect(heading("Issue load sheet")).toBeVisible();
    await page.getByRole("radio", { name: "Table" }).click();
    const steps = page.getByRole("table", { name: "Steps in process order" });
    await steps.getByRole("button", { name: "Special loads OK?", exact: true }).click();
    await expect(heading("Special loads OK?")).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    // V3b: Eric confirms the proposed work type (the step itself stays to be reviewed).
    const details = page.getByRole("complementary", { name: "Step details" });
    await details.getByRole("button", { name: "Confirm work type" }).click();
    await expect(details.getByText("You confirmed this work type.")).toBeVisible();
    await expect(details.getByRole("button", { name: "Confirm as drafted" })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    await page.getByRole("radio", { name: "Map" }).click();

    // Confirm every step with auto-advance: buttons and the C shortcut, then all reviewed.
    await page.getByRole("button", { name: "Close details" }).click();
    await page.getByRole("button", { name: "Start with the first step that needs attention" }).click();
    for (let reviewed = 1; reviewed <= 10; reviewed += 1) {
      const actions = page.getByRole("complementary", { name: "Step details" });
      await expect(actions.getByRole("button", { name: "Confirm as drafted" })).toBeVisible();
      if (reviewed % 2 === 0) await page.keyboard.press("c");
      else await actions.getByRole("button", { name: "Confirm as drafted" }).click();
      await expect(page.getByText(`${reviewed} of 10 steps reviewed`)).toBeVisible();
    }
    await expect(page.getByText("All steps reviewed")).toBeVisible();
    await expect(page.locator(".map-node--unreviewed")).toHaveCount(0);
    expect(await seriousViolations(page)).toEqual([]);

    // Refresh draft from sources: the reviewed steps stay as they are; the draft number goes up.
    await page.getByRole("button", { name: "More" }).click();
    await page.getByRole("button", { name: "Refresh draft from sources" }).click();
    const refresh = page.getByRole("dialog", { name: "Refresh draft from sources" });
    await expect(refresh).toContainText("The 10 steps you confirmed, edited, added or rejected stay exactly as they are.");
    // Anti-drift: nothing changed in Settings or the instructions since the draft was made.
    await expect(refresh).toContainText("Claude's model, settings and instructions are the same as when this draft was made.");
    expect(await seriousViolations(page)).toEqual([]);
    await refresh.getByRole("button", { name: "Refresh draft" }).click();
    await expect(page.getByRole("region", { name: "Draft v0.2" })).toBeVisible({ timeout: 30_000 });
    const changed = page.getByRole("region", { name: "What the refresh changed" });
    await expect(changed).toContainText("The 10 steps you reviewed stayed exactly as they were.");
    await expect(changed).toContainText("The steps you hadn't reviewed came out the same as before.");
    expect(await seriousViolations(page)).toEqual([]);
    await page.getByRole("region", { name: "Draft v0.2" }).getByRole("link", { name: "Start reviewing" }).click();
    await expect(page.getByText("10 of 10 steps reviewed")).toBeVisible();
    await expect(page.getByText("All steps reviewed")).toBeVisible();
    await page.getByRole("tab", { name: "Audit log" }).click();
    await expect(page.getByRole("tabpanel").getByRole("row", { name: /Refreshed draft from sources/ })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    expect((await publicText(page)).includes("Priya"), "a name shown on Review after refresh").toBe(false);
    // C6 (criterion 75): the validation session pack downloads from the Review screen.
    await page.getByRole("tab", { name: /^Validation questions/ }).click();
    const pack = page.getByRole("tabpanel").getByRole("link", { name: "Download validation pack" });
    expect(await seriousViolations(page)).toEqual([]);
    const packFile = await request.get((await pack.getAttribute("href")) ?? "");
    expect(packFile.status()).toBe(200);
    const packText = await packFile.text();
    expect(packText).toContain("## 3. Contrast without evaluation");
    expect(packText.includes("Priya"), "a name in the validation pack").toBe(false);

    // P8: a photo on a step. The form explains what is missing; the stored copy keeps no camera
    // or GPS details; the step gets the has-images marker and the walkthrough strip appears.
    const CAPTION = "Load sheet on the ramp printer";
    const photo = join(FIXTURES, "photo_with_gps.jpg");
    expect(readFileSync(photo).includes("CameraCo"), "the fixture photo carries camera details").toBe(true);
    await page.getByRole("button", { name: /^Activity, Issue load sheet,/ }).click();
    const pictures = page.getByRole("complementary", { name: "Step details" }).getByRole("region", { name: "Images" });
    await expect(pictures).toContainText("In-app only · never exported · metadata stripped");
    await expect(pictures.getByText("No pictures on this step yet.")).toBeVisible();
    await pictures.getByRole("button", { name: "Add image to this step" }).click();
    const imageForm = pictures.getByRole("form", { name: "Add image to this step" });
    await imageForm.getByRole("button", { name: "Add picture" }).click();
    await expect(imageForm.getByText("4 things to fix before saving.")).toBeVisible();
    await imageForm.getByLabel("Picture", { exact: true }).setInputFiles(photo);
    await imageForm.getByLabel("Caption").fill(CAPTION);
    await imageForm.getByLabel("Type of picture").selectOption("workplace_photo");
    await imageForm.getByLabel(/Faces, names, badge numbers and flight identifiers/).check();
    expect(await seriousViolations(page)).toEqual([]);
    await imageForm.getByRole("button", { name: "Add picture" }).click();
    await expect(pictures.getByRole("img", { name: CAPTION })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Activity, Issue load sheet,.*, has images$/ })).toBeVisible();
    const walkthrough = page.getByRole("region", { name: "Visual walkthrough" });
    await expect(walkthrough.getByRole("button", { name: new RegExp(`Issue load sheet ${CAPTION}`) })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(await seriousViolations(page)).toEqual([]);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p8-review-images.png"), fullPage: true });
    }
    const draftVersion = ((await (await request.get(`/api/engagements/${id}/draft`)).json()) as { version: { id: string } })
      .version.id;
    const listed = (await (await request.get(`/api/versions/${draftVersion}/images`)).json()) as { id: string }[];
    expect(listed).toHaveLength(1);
    const stored = await (await request.get(`/api/images/${listed[0]?.id ?? ""}/file`)).body();
    expect(stored.length).toBeGreaterThan(0);
    for (const trace of ["CameraCo", "Ramp phone", "Exif"]) {
      expect(stored.includes(trace), `"${trace}" left in the stored photo`).toBe(false);
    }

    // P9: coverage on Sources (G11): the share of each file the map cites, uncited passages on request.
    await page.goto(`/engagements/${id}/sources`);
    const registry = page.getByRole("table", { name: "Sources for this engagement" });
    // v1.10 A.1: every SME turn is cited once the story, know-how and decision cues are extracted.
    await expect(registry.getByRole("row", { name: /interview_transcript\.txt/ })).toContainText("100%");
    await expect(registry.getByRole("row", { name: /sop_LC-07\.docx/ })).toContainText("50%");
    await registry.getByRole("button", { name: "sop_LC-07.docx", exact: true }).click();
    const lc07 = page.getByRole("region", { name: "sop_LC-07.docx" });
    await expect(lc07).toContainText("50% cited by the map");
    await expect(lc07.getByText("Uncited", { exact: true })).toHaveCount(5);
    await lc07.getByRole("button", { name: "Show uncited passages" }).click();
    await expect(lc07.getByRole("button", { name: "Show uncited passages" })).toHaveAttribute("aria-pressed", "true");
    await expect(lc07.getByRole("list", { name: "Passages" }).getByRole("listitem")).toHaveCount(5);
    expect(await seriousViolations(page)).toEqual([]);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p9-sources-coverage.png"), fullPage: true });
    }

    // P9: the Matrix, every step against every kind of source; silence shown as silent.
    await page.getByRole("link", { name: /^Matrix/ }).click();
    const matrixTable = page.getByRole("table", { name: "How each kind of source stands on each step" });
    await expect(matrixTable.getByRole("row")).toHaveCount(11);  // header + ten steps (v1.10 A.5)
    const lirRow = matrixTable.getByRole("row", { name: /Load and return LIR/ });
    await expect(lirRow).toContainText("Contradicts");
    await expect(lirRow).toContainText("Contested");
    await expect(lirRow).toContainText("Threshold");
    await expect(matrixTable.getByRole("row", { name: /Approve load plan/ })).toContainText("Silent");
    // P9u-2: the interview split by account (G4): the deviation check is told only in unclear terms.
    await expect(matrixTable.getByRole("columnheader", { name: "SME lived" })).toBeVisible();
    await expect(matrixTable.getByRole("row", { name: /Deviation in limits\?/ })).toContainText("Account unclear");
    expect(await seriousViolations(page)).toEqual([]);
    expect((await publicText(page)).includes("Priya"), "a name shown on Matrix").toBe(false);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p9-matrix.png"), fullPage: true });
    }
    await page.getByRole("button", { name: "Ownership 1" }).click();
    await expect(matrixTable.getByRole("row")).toHaveCount(2);
    await matrixTable.getByRole("button", { name: "Deviation in limits?" }).click();
    await expect(
      page.getByRole("complementary", { name: "Step details" }).getByRole("heading", { name: "Deviation in limits?" }),
    ).toBeVisible();

    // P9: Registers, including the cause library (confirm an entry).
    await page.getByRole("link", { name: /^Registers/ }).click();
    const registerChoice = page.getByRole("radiogroup", { name: "Register" });
    await expect(page.getByText(/Widebody plans rely/)).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    for (const name of [
      "AI flags",
      "Constraints by cause",
      "External practice (R)",
      "Validation questions",
      "Rejected claims",
      "Stories",
      "Glossary",
      "Emerging themes",
      "Preserve / Improve",
    ]) {
      await registerChoice.getByRole("radio", { name }).click();
      await expect(registerChoice.getByRole("radio", { name })).toHaveAttribute("aria-checked", "true");
      expect(await seriousViolations(page)).toEqual([]);
    }
    // P9u: the interview lists from the real backend (the sample's story, terms and capability notes).
    await registerChoice.getByRole("radio", { name: "Stories" }).click();
    await expect(page.getByRole("list", { name: "Stories" })).toContainText("Had to re-trim three flights in one night");
    await registerChoice.getByRole("radio", { name: "Preserve / Improve" }).click();
    await expect(page.getByRole("list", { name: "Improve: what gets in the way, Systems" })).toContainText(
      "The paper loading report gets lost or arrives late",
    );
    expect(await seriousViolations(page)).toEqual([]);
    // X3: how much of the process is exception handling, rework and workarounds.
    await registerChoice.getByRole("radio", { name: "Exceptions and workarounds" }).click();
    await expect(registerChoice.getByRole("radio", { name: "Exceptions and workarounds" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await expect(page.getByText(/^3 of 9 steps \(33%\) are off the usual route/)).toBeVisible();
    await expect(page.getByRole("list", { name: "Workarounds" })).toContainText("otherwise we'd miss the slot");
    expect(await seriousViolations(page)).toEqual([]);
    if (shots) await page.screenshot({ path: join(shots, "x3-registers-exceptions-1440x900.png"), fullPage: true });
    // C8: the sample's shared loading step, one Responsible and the load controller Consulted.
    await registerChoice.getByRole("radio", { name: "Lane boundaries" }).click();
    await expect(registerChoice.getByRole("radio", { name: "Lane boundaries" })).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("listitem").filter({ hasText: "Load and return LIR" })).toContainText(
      "One Responsible (Ramp), the others Consulted",
    );
    expect(await seriousViolations(page)).toEqual([]);
    await registerChoice.getByRole("radio", { name: "Cause library" }).click();
    const lirCause = page.getByRole("listitem").filter({ hasText: "Threshold divergence" });
    await expect(lirCause).toContainText("Possible cause (inferred from this step's constraints");
    await expect(page.getByRole("listitem").filter({ hasText: "Ownership divergence" })).toContainText(
      "Cause not known yet",
    );
    expect(await seriousViolations(page)).toEqual([]);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p9-registers-causes.png"), fullPage: true });
    }
    await lirCause.getByRole("button", { name: "Confirm" }).click();
    await expect(lirCause.getByRole("button", { name: "Reopen" })).toBeVisible();
    expect((await publicText(page)).includes("Priya"), "a name shown on Registers").toBe(false);

    await page.goto(`/engagements/${id}/review`);
    await expect(page.getByText("10 of 10 steps reviewed")).toBeVisible();

    // P7: every step reviewed and the card green, so Publish makes v1.0, read-only on Published.
    await expect(page.getByRole("button", { name: /Quality card: 9 of 9 green/ })).toBeVisible();
    await page.getByRole("button", { name: "Publish" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Published" })).toBeAttached();
    await expect(page.getByText("Published v1.0")).toBeVisible();
    await expect(page.getByRole("region", { name: "Changes in this version" })).toContainText("Confirmed");
    await expect(page.getByRole("button", { name: "Publish" })).toHaveCount(0);
    await expect(page.locator(".map-node--unreviewed")).toHaveCount(0);
    expect(await seriousViolations(page)).toEqual([]);
    expect((await publicText(page)).includes("Priya"), "a name shown on Published").toBe(false);
    // P8: the picture is shown on Published, with no way to change it.
    await page.getByRole("region", { name: "Visual walkthrough" }).getByRole("button", { name: /Issue load sheet/ }).click();
    const publishedPictures = page.getByRole("complementary", { name: "Step details" }).getByRole("region", { name: "Images" });
    await expect(publishedPictures.getByRole("img", { name: CAPTION })).toBeVisible();
    await expect(publishedPictures.getByRole("button")).toHaveCount(0);
    expect(await seriousViolations(page)).toEqual([]);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p7-published.png"), fullPage: true });
    }
    // Exports: the four files of v1.0, privacy-scanned; the HTML map makes no requests and no errors.
    await page.getByRole("link", { name: "Exports" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Exports" })).toBeVisible();
    await expect(page.getByText("No images, verbatim quotes or names.")).toHaveCount(4);
    await expect(page.getByText(/Quality card: 9 of 9 green/).first()).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p7-exports.png"), fullPage: true });
    }
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("link", { name: "Download Master Process Map (.md) of v1.0" }).click(),
    ]);
    expect(download.suggestedFilename()).toBe("load-control-v1-0-master-map.md");
    const files: Record<string, string> = {};
    for (const format of ["md", "json", "csv", "html"]) {
      const href = await page
        .getByRole("link", { name: new RegExp(`^Download .*\\(\\.${format}\\) of v1\\.0$`) })
        .getAttribute("href");
      const response = await request.get(href ?? "");
      expect(response.status(), format).toBe(200);
      files[format] = await response.text();
    }
    for (const [format, text] of Object.entries(files)) {
      expect(text.includes("Priya"), `a hidden name in the ${format} export`).toBe(false);
      expect(/<img\b|data:image\//i.test(text), `an image in the ${format} export`).toBe(false);
      expect(text.includes(CAPTION), `a picture's caption in the ${format} export`).toBe(false);
      expect(/\/api\/images\/|photo_with_gps/.test(text), `a picture reference in the ${format} export`).toBe(false);
    }
    expect(files.md).toContain("## 3. Recommendation: enablement and gaps");
    const offline = await page.context().newPage();
    const requests: string[] = [];
    const errors: string[] = [];
    offline.on("request", (r) => {
      if (!r.url().startsWith("data:") && r.url() !== "about:blank") requests.push(r.url());
    });
    offline.on("console", (m) => {
      if (m.type() === "error") errors.push(m.text());
    });
    offline.on("pageerror", (e) => errors.push(String(e)));
    await offline.setContent(files.html ?? "", { waitUntil: "load" });
    // K3 (2026-10-06): both views are published together, so the file draws two maps.
    await expect(offline.getByRole("group", { name: "Swimlane map" })).toHaveCount(2);
    await expect(offline.getByRole("heading", { name: "Map as done: the work as actually performed" })).toBeVisible();
    await expect(offline.getByRole("heading", { name: "Map as documented: the documents' version" })).toBeVisible();
    await offline.getByRole("link", { name: /^Activity, Draft load plan/ }).first().click();
    await expect(offline.locator(".step:target")).toContainText("Draft load plan");
    expect(requests, "the HTML map asked for something outside itself").toEqual([]);
    expect(errors, "the HTML map logged errors").toEqual([]);
    expect(await seriousViolations(offline)).toEqual([]);
    await offline.close();

    // P11: Leadership on v1.0: facts, interpretation and recommendation kept apart, each figure
    // opening its steps, and one decision line for the systemic cause.
    await page.goto(`/engagements/${id}/leadership`);
    await expect(page.getByRole("heading", { level: 1, name: "Leadership" })).toBeVisible();
    for (const part of ["Facts", "Interpretation", "Recommendation"]) {
      await expect(page.getByRole("heading", { level: 2, name: part })).toBeVisible();
    }
    await expect(page.getByText("Work 80 min")).toBeVisible();
    await expect(page.getByText("Systemic", { exact: true })).toBeVisible();
    await expect(page.getByText("Recoverable wait: 15 min")).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    expect((await publicText(page)).includes("Priya"), "a name shown on Leadership").toBe(false);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p11-leadership.png"), fullPage: true });
    }
    await page
      .getByRole("textbox", { name: "Decision needed: System fragmentation" })
      .fill("Fund one digital loading report across Ramp and Load control.");
    await page.getByRole("button", { name: "Save decisions" }).click();
    const saved = page.locator(".toast", { hasText: "Decisions saved." });
    await expect(saved).toBeVisible();
    await expect(saved).toHaveCount(0, { timeout: 10_000 });
    await page.reload();
    await expect(page.getByRole("textbox", { name: "Decision needed: System fragmentation" })).toHaveValue(
      "Fund one digital loading report across Ramp and Load control.",
    );
    const recoverable = page.locator("details", { hasText: "Recoverable wait: 15 min" });
    await recoverable.getByText("Recoverable wait: 15 min").click();
    await recoverable.getByRole("button", { name: "Open Load and return LIR" }).click();
    await expect(page).toHaveURL(/\/review|\/published/);
    await page.goto(`/engagements/${id}/published`);

    // Reopen: a new draft with every reviewed step locked.
    await page.getByRole("button", { name: "Reopen as new draft" }).click();
    await expect(page.getByText("Draft v1.1 draft")).toBeVisible();
    await expect(page.getByText("10 of 10 steps reviewed")).toBeVisible();
    await expect(page.getByRole("region", { name: "Visual walkthrough" })).toContainText(CAPTION);
    expect(await seriousViolations(page)).toEqual([]);

    // Every AI call shows in Settings, as usage only.
    await page.goto("/settings");
    const usage = page.getByRole("region", { name: "AI usage" });
    await expect(usage.getByRole("table")).toBeVisible();
    await expect(usage.getByText(/All time: \d+ calls/)).toBeVisible();
    // The table lists the 50 most recent calls (the total counts every call). A draft makes 30
    // calls (C3: + the A.10 landscape interview), so the latest run's four interview chunks are
    // listed and the first draft's have scrolled out of the 50.
    await expect(usage.getByRole("row").filter({ hasText: "Extracting steps (interview)" })).toHaveCount(4);
    await expect(usage.getByRole("row").filter({ hasText: "Test answer" }).first()).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await usage.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p4-settings-ai-usage.png") });
    }

    // P10: Gap analysis, last so its AI calls don't push the rows above out of the usage list.
    // Documents vs practice on the published map (Claude mocked), then an external brief:
    // refused while web research is off, run with the mocked web search once it is on.
    await page.goto(`/engagements/${id}/gap-analysis`);
    await expect(page.getByRole("heading", { level: 1, name: /Gap analysis/ })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    await page.getByRole("button", { name: "Run analysis" }).click();
    await expect(page.getByText(/2 AI calls/)).toBeVisible({ timeout: 30_000 });
    // The "started" toast can be caught mid-way in (it may even appear after the report), so
    // the page is checked once that toast has come and gone.
    const started = page.locator(".toast", { hasText: "Documents-vs-practice analysis started." });
    await expect(started).toBeVisible();
    await expect(started).toHaveCount(0, { timeout: 10_000 });
    expect(await seriousViolations(page)).toEqual([]);
    expect((await publicText(page)).includes("Priya"), "a name shown on Gap analysis").toBe(false);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p10-gap-report.png"), fullPage: true });
    }
    await page.getByRole("button", { name: "Prepare research brief" }).click();
    let brief = page.getByRole("form", { name: "Research brief" });
    await expect(brief.getByRole("region", { name: "Confidentiality check" })).toBeVisible();
    await brief.getByRole("checkbox", { name: "This brief contains no confidential information" }).check();
    await brief.getByRole("button", { name: "Run research" }).click();
    await expect(brief.getByRole("alert")).toContainText("Web research is switched off");
    expect(await seriousViolations(page)).toEqual([]);
    if (process.env.PMS_SCREENSHOT_DIR) {
      await page.screenshot({ path: join(process.env.PMS_SCREENSHOT_DIR, "p10-gap-brief.png"), fullPage: true });
    }
    expect((await request.put("/api/settings/research", { data: { web_research_enabled: true } })).status()).toBe(200);
    await page.reload();
    brief = page.getByRole("form", { name: "Research brief" });
    await brief.getByRole("checkbox", { name: "This brief contains no confidential information" }).check();
    await brief.getByRole("button", { name: "Run research" }).click();
    await expect(page.getByText(/1 web search used/)).toBeVisible({ timeout: 30_000 });
    const research = page.locator(".toast", { hasText: "Research started." });
    await expect(research).toBeVisible();
    await expect(research).toHaveCount(0, { timeout: 10_000 });
    expect(await seriousViolations(page)).toEqual([]);
    expect((await request.put("/api/settings/research", { data: { web_research_enabled: false } })).status()).toBe(200);

    // R8: System records on, a small log matched to the current map; the Volume and wait lens and
    // the Variants tab in a real browser (contrast included). Switched back off at the end.
    expect((await request.put("/api/settings/modules", { data: { system_records_enabled: true } })).status()).toBe(200);
    const rows = ["case_id,activity,timestamp"];
    for (let n = 0; n < 6; n++) {
      rows.push(`C${n},Plan created,2026-03-02 0${n}:00`, `C${n},Special load checked,2026-03-02 0${n}:20`);
      rows.push(`C${n},Manual weight override,2026-03-02 0${n}:40`);
    }
    const upload = await request.post(`/api/engagements/${id}/event-logs`, {
      multipart: { name: "Six cases", file: { name: "six.csv", mimeType: "text/csv", buffer: Buffer.from(rows.join("\n")) } },
    });
    const log = (await upload.json()) as { id: string; column_map: Record<string, string | null> };
    await request.put(`/api/event-logs/${log.id}/column-map`, { data: { columns: log.column_map } });
    const approval = { approved_by_role: "Head of operations", confirm_approval: true };
    expect((await request.post(`/api/event-logs/${log.id}/import`, { data: approval })).status()).toBe(202);
    await expect
      .poll(async () => ((await (await request.get(`/api/event-logs/${log.id}`)).json()) as { status: string }).status)
      .toBe("imported");
    const aligned = (await (await request.get(`/api/event-logs/${log.id}/alignment`)).json()) as { version_id: string };
    const current = (await (await request.get(`/api/versions/${aligned.version_id}/graph`)).json()) as {
      version: { state: string };
      elements: { id: string; label: string }[];
    };
    const step = (label: string) => current.elements.find((e) => e.label === label)?.id ?? "";
    const decided = await request.put(`/api/event-logs/${log.id}/alignment`, {
      data: { rows: [
        { activity: "Plan created", element_id: step("Draft load plan"), status: "confirmed" },
        { activity: "Special load checked", element_id: step("Special loads OK?"), status: "confirmed" },
        { activity: "Manual weight override", element_id: null, status: "hidden_work" },
      ] }, // prettier-ignore
    });
    expect(decided.status()).toBe(200);
    await page.goto(`/engagements/${id}/${current.version.state === "draft" ? "review" : "published"}`);
    await page.getByRole("radiogroup", { name: "Lens" }).getByRole("radio", { name: "Volume and wait" }).click();
    await expect(page.locator(".map-lens", { hasText: /cases\/mo|No system data/ }).first()).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    await page.getByRole("tab", { name: "Variants" }).click();
    await expect(page.getByRole("region", { name: "Hidden work in Six cases" })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    await page.getByRole("radiogroup", { name: "Lens" }).getByRole("radio", { name: "Plain" }).click();

    // P13b: Reality views on. The screen opens on the current draft's snapshot: Glance, Reality
    // stack and Fix or keep, each with its table, in a real browser (contrast included); Leadership
    // shows the published version's frozen tiles. Switched back off at the end.
    expect((await request.put("/api/settings/modules", { data: { reality_views_enabled: true } })).status()).toBe(200);
    await page.goto(`/engagements/${id}/reality`);
    await expect(page.getByRole("heading", { level: 1, name: "Reality" })).toBeVisible();
    await expect(page.getByRole("heading", { name: /How different is real/ })).toBeVisible();
    await expect(page.getByRole("note")).toContainText("Draft: figures may change");
    await expect(page.getByRole("region", { name: "Intent" })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    // P13d visual baselines (Eric approved 2026-10-18): each view at 1440 x 900. Soft, as for
    // Review: a changed view fails the check until Eric approves new baselines, and the rest of
    // the journey keeps running.
    const shoot = async (name: string) => {
      await expect.soft(page).toHaveScreenshot(`p13d-reality-${name}-1440x900.png`);
    };
    await shoot("glance");
    for (const view of ["Reality stack", "Fix or keep", "Redline", "Where the time goes", "Belief vs evidence", "Typical case"]) {
      await page.getByRole("radiogroup", { name: "Reality view" }).getByRole("radio", { name: view }).click();
      await expect(page.locator(".reality-view__headline")).not.toBeEmpty();
      await shoot(view.toLowerCase().replace(/ /g, "-"));
      expect(await seriousViolations(page)).toEqual([]);
      // P13c RQ7 in a real browser: no two drawn labels overlap on the P13c canvases.
      expect(await overlappingLabels(page), `labels overlap on ${view}`).toEqual([]);
    }
    await page.getByRole("button", { name: "Show as table" }).click();
    await expect(page.getByRole("table")).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    expect((await publicText(page)).includes("Priya"), "a name shown on Reality").toBe(false);
    // P13d: the Reality pack of the published version in both layouts, downloaded from the Reality
    // screen and opened offline: no request outside the file, no error, and on every printed page
    // nothing cut off, no text under 11 px and no two drawn labels overlapping (RQ7).
    const versionList = (await (await request.get(`/api/engagements/${id}/versions`)).json()) as {
      id: string;
      label: string;
      state: string;
    }[];
    const released = versionList.find((v) => v.state === "published");
    expect(released, "a published version to print").toBeTruthy();
    await page.goto(`/engagements/${id}/reality?version=${released?.id ?? ""}`);
    const packCard = page.getByRole("region", { name: "Reality pack" });
    await expect(packCard).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    for (const [label, layout, pageCount] of [["A3", "a3", 11], ["16:9", "slide", 11]] as const) {
      const [pack] = await Promise.all([
        page.waitForEvent("download"),
        packCard.getByRole("link", { name: `Download ${label} Reality pack of ${released?.label ?? ""}` }).click(),
      ]);
      expect(pack.suggestedFilename()).toMatch(new RegExp(`-reality-pack-${layout}\\.html$`));
      const html = readFileSync(await pack.path(), "utf-8");
      expect(html.includes("Priya"), `a hidden name in the ${label} pack`).toBe(false);
      const printed = await page.context().newPage();
      const asked: string[] = [];
      const problems: string[] = [];
      printed.on("request", (r) => {
        if (!r.url().startsWith("data:") && r.url() !== "about:blank") asked.push(r.url());
      });
      printed.on("console", (m) => {
        if (m.type() === "error") problems.push(m.text());
      });
      printed.on("pageerror", (e) => problems.push(String(e)));
      await printed.setViewportSize({ width: 1920, height: 1080 });
      await printed.setContent(html, { waitUntil: "load" });
      await printed.emulateMedia({ media: "print" });
      const pages = await printChecks(printed);
      expect(pages, `${label} pages`).toHaveLength(pageCount);
      for (const p of pages) {
        expect(p.overflow, `${label} page ${p.page} is cut off`).toBeLessThanOrEqual(0);
        expect(p.smallest, `${label} page ${p.page}: "${p.where}" under 11 px`).toBeGreaterThanOrEqual(11);
      }
      expect(await overlappingLabels(printed), `labels overlap in the ${label} pack`).toEqual([]);
      // P13d visual baselines (Eric approved 2026-10-18): every printed page. The data label's
      // date is the day the journey publishes, a few dozen pixels inside the 0.5% tolerance.
      for (const [i, p] of pages.entries()) {
        const name = `p13d-pack-${layout}-${String(i + 1).padStart(2, "0")}-${p.page}.png`;
        await expect.soft(printed.locator("section.page").nth(i)).toHaveScreenshot(name);
      }
      expect(asked, `the ${label} pack asked for something outside itself`).toEqual([]);
      expect(problems, `the ${label} pack logged errors`).toEqual([]);
      await printed.close();
    }

    await page.goto(`/engagements/${id}/leadership`);
    await expect(page.getByRole("heading", { level: 2, name: "Facts" })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
  } finally {
    await request.put("/api/settings/modules", { data: { system_records_enabled: false, reality_views_enabled: false } });
    expect((await request.delete(`/api/engagements/${id}`)).status()).toBe(204);
  }
});

// P12 (Eric's decision 2026-09-29): a map drafted from the interview alone. The draft is allowed,
// and its Limited signal strength is stated in words and bars on Draft, Review (with a quality-card
// warning that never blocks), Published and Exports. Claude mocked; cleans up after itself.
test("interview only: draft, review and publish at Limited signal strength", async ({ page, request }) => {
  test.setTimeout(90_000);
  const created = await request.post("/api/engagements", {
    data: { name: "Load control (interview only)", trigger: "Flight scheduled", end_point: "Final load sheet issued" },
  });
  const { id } = (await created.json()) as { id: string };
  try {
    const roleIds: Record<string, string> = {};
    for (const [name, aliases] of ROLES) {
      const role = await request.post(`/api/engagements/${id}/roles`, { data: { name, aliases } });
      roleIds[name] = ((await role.json()) as { id: string }).id;
    }
    await page.goto(`/engagements/${id}/sources`);
    await page.getByTestId("source-file-input").setInputFiles([join(FIXTURES, "interview_transcript.txt")]);
    await expect(page.getByText("1 file uploaded.")).toBeVisible();
    await expect(page.getByRole("table", { name: "Sources for this engagement" }).getByText("Ready")).toHaveCount(1);
    const [transcript] = (await (await request.get(`/api/engagements/${id}/sources`)).json()) as { id: string }[];
    const mapped = await request.put(`/api/sources/${transcript?.id ?? ""}/speakers`, {
      data: { Interviewer: "interviewer", "Priya Nair": roleIds["Load controller"] },
    });
    expect(mapped.status()).toBe(200);

    // Draft: ready without a document, which is recommended; the signal is Limited.
    await page.goto(`/engagements/${id}/draft`);
    const checklist = page.getByRole("region", { name: "Before drafting" });
    await expect(checklist.getByText("3 of 3 ready.")).toBeVisible();
    await expect(checklist.getByText("Recommended", { exact: true })).toBeVisible();
    await expect(checklist.getByText("Add a process document such as an SOP or manual")).toBeVisible();
    await expect(checklist.getByText(/Signal strength: Limited/)).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    await page.getByRole("button", { name: "Create draft map" }).click();
    const summary = page.getByRole("region", { name: "Draft v0.1" });
    await expect(summary).toBeVisible({ timeout: 30_000 });
    // v1.10: seven steps plus the busy-wave decision and its lived branch (A.5).
    await expect(summary.getByText("Steps drafted").locator("xpath=following-sibling::dd")).toHaveText("9");
    await expect(summary.getByText(/Signal strength: Limited/)).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);

    // Review: the banner says Limited; the quality card warns but only the review blocks.
    await summary.getByRole("link", { name: "Start reviewing" }).click();
    await expect(page.getByText("0 of 9 steps reviewed")).toBeVisible();
    await expect(page.locator(".version-banner").getByText(/Signal strength: Limited/)).toBeVisible();
    await page.getByRole("button", { name: /Quality card: 8 of 9 green/ }).click();
    await expect(page.getByText(/Signal strength: Limited\. Built from interviews only/)).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    expect((await publicText(page)).includes("Priya"), "a name shown on Review").toBe(false);
    await page.keyboard.press("Escape");

    const graph = (await (await request.get(`/api/engagements/${id}/draft`)).json()) as { version: { id: string } };
    const elements = (await (await request.get(`/api/versions/${graph.version.id}/graph`)).json()) as {
      elements: { id: string; kind: string }[];
    };
    for (const e of elements.elements.filter((x) => x.kind !== "start" && x.kind !== "end")) {
      expect((await request.post(`/api/elements/${e.id}/confirm`)).status()).toBe(200);
    }
    await page.reload();
    await expect(page.getByRole("button", { name: /Quality card: 9 of 9 green/ })).toBeVisible();
    await page.getByRole("button", { name: "Publish" }).click();
    await expect(page.getByText("Published v1.0")).toBeVisible();
    await expect(page.locator(".version-banner").getByText(/Signal strength: Limited/)).toBeVisible();

    await page.goto(`/engagements/${id}/exports`);
    await expect(page.getByText(/Built from interviews only/)).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
  } finally {
    expect((await request.delete(`/api/engagements/${id}`)).status()).toBe(204);
  }
});

// PRD v1.10 F.9 and acceptance 77: the standard interview templates download from the home screen
// as Word and Markdown, with no engagement needed; the Word file is a real .docx (a zip package).
test("interview templates: download Word and Markdown from the home screen", async ({ page }) => {
  await page.goto("/");
  const card = page.getByRole("region", { name: "Interview templates" });
  await expect(card.getByRole("list", { name: "Interview templates" }).getByRole("listitem")).toHaveCount(3);
  expect(await seriousViolations(page)).toEqual([]);

  const [word] = await Promise.all([
    page.waitForEvent("download"),
    card.getByRole("link", { name: "Download Word Practice interview template" }).click(),
  ]);
  expect(word.suggestedFilename()).toBe("interview-template-practice.docx");
  const wordBytes = readFileSync(await word.path());
  expect(wordBytes.subarray(0, 2).toString()).toBe("PK");

  const [markdown] = await Promise.all([
    page.waitForEvent("download"),
    card.getByRole("link", { name: "Download Markdown Landscape interview template" }).click(),
  ]);
  expect(markdown.suggestedFilename()).toBe("interview-template-landscape.md");
  const text = readFileSync(await markdown.path(), "utf-8");
  expect(text.startsWith("# Landscape interview template\n\nQuestion bank v1.0 · Process Map Studio")).toBe(true);
  expect(text).toContain("| **Total** | **60** |");
  expect(text).toContain("| L3 |");
  expect(text).toContain("Use roles, not names.");
});

/**
 * The print checks of the Reality pack (P13d, RQ7): for each printed page, how far its content
 * runs past the page (0 or less when nothing is cut off) and its smallest text as printed,
 * counting how far a drawing is scaled down to fit.
 */
async function printChecks(page: Page): Promise<{ page: string; overflow: number; smallest: number; where: string }[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>("section.page")].map((p) => {
      let smallest = 99;
      let where = "";
      for (const el of p.querySelectorAll("text, tspan, p, span, td, th, li, h1, h2, h3")) {
        const own = el.tagName === "text" || el.children.length === 0;
        if (!(el.textContent ?? "").trim() || !own) continue;
        const svg = el.closest("svg");
        let scale = 1;
        if (svg?.viewBox.baseVal.width) {
          const box = svg.getBoundingClientRect();
          const vb = svg.viewBox.baseVal;
          scale = Math.min(box.width / vb.width, box.height / vb.height);
        }
        const size = parseFloat(getComputedStyle(el).fontSize) * scale;
        if (size < smallest) {
          smallest = size;
          where = (el.textContent ?? "").trim().slice(0, 30);
        }
      }
      return {
        page: p.dataset.view ?? p.dataset.section ?? "",
        overflow: p.scrollHeight - p.clientHeight,
        smallest: Math.round(smallest * 10) / 10,
        where,
      };
    }),
  );
}

/** RQ7 (P13c): pairs of drawn text labels on the Reality canvas whose boxes overlap on screen. */
async function overlappingLabels(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const boxes = [...document.querySelectorAll("svg.reality-canvas [data-role] > text")].map((t) => ({
      text: t.textContent ?? "",
      r: t.getBoundingClientRect(),
    }));
    const out: string[] = [];
    boxes.forEach((a, i) =>
      boxes.slice(i + 1).forEach((b) => {
        const x = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
        const y = Math.min(a.r.bottom, b.r.bottom) - Math.max(a.r.top, b.r.top);
        if (x > 1 && y > 1) out.push(`${a.text} | ${b.text}`);
      }),
    );
    return out;
  });
}
