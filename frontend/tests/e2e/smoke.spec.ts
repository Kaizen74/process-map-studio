import { expect, test } from "@playwright/test";
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
  // The whole journey: draft, review, refresh, publish, export, reopen (each AI stage mocked).
  test.setTimeout(90_000);
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
    await expect(checklist.getByText("3 of 3 ready.")).toBeVisible();
    // P12: the sample has an interview and an SOP, so the map's signal is Strong.
    await expect(checklist.getByText(/Signal strength: Strong/)).toBeVisible();
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

    // Review: the draft map drawn from the backend layout (P5).
    await summary.getByRole("link", { name: "Start reviewing" }).click();
    await expect(page.getByText("0 of 8 steps reviewed")).toBeVisible();
    await expect(page.locator(".version-banner").getByText(/Signal strength: Strong/)).toBeVisible();
    await expect(page.getByRole("button", { name: /^Activity, Draft load plan, Load controller/ })).toBeVisible();
    await expect(page.getByRole("group", { name: "Load controller lane, 4 steps" })).toBeAttached();
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
    await expect(page).toHaveScreenshot("p7-review-1440x900.png");
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
    await expect(page).toHaveScreenshot("p7-review-1080x800.png");
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
    await page.getByRole("radio", { name: "Map" }).click();

    // Confirm every step with auto-advance: buttons and the C shortcut, then all reviewed.
    await page.getByRole("button", { name: "Close details" }).click();
    await page.getByRole("button", { name: "Start with the first step that needs attention" }).click();
    for (let reviewed = 1; reviewed <= 8; reviewed += 1) {
      const actions = page.getByRole("complementary", { name: "Step details" });
      await expect(actions.getByRole("button", { name: "Confirm as drafted" })).toBeVisible();
      if (reviewed % 2 === 0) await page.keyboard.press("c");
      else await actions.getByRole("button", { name: "Confirm as drafted" }).click();
      await expect(page.getByText(`${reviewed} of 8 steps reviewed`)).toBeVisible();
    }
    await expect(page.getByText("All steps reviewed")).toBeVisible();
    await expect(page.locator(".map-node--unreviewed")).toHaveCount(0);
    expect(await seriousViolations(page)).toEqual([]);

    // Refresh draft from sources: the reviewed steps stay as they are; the draft number goes up.
    await page.getByRole("button", { name: "More" }).click();
    await page.getByRole("button", { name: "Refresh draft from sources" }).click();
    const refresh = page.getByRole("dialog", { name: "Refresh draft from sources" });
    await expect(refresh).toContainText("The 8 steps you confirmed, edited, added or rejected stay exactly as they are.");
    expect(await seriousViolations(page)).toEqual([]);
    await refresh.getByRole("button", { name: "Refresh draft" }).click();
    await expect(page.getByRole("region", { name: "Draft v0.2" })).toBeVisible({ timeout: 30_000 });
    await page.getByRole("region", { name: "Draft v0.2" }).getByRole("link", { name: "Start reviewing" }).click();
    await expect(page.getByText("8 of 8 steps reviewed")).toBeVisible();
    await expect(page.getByText("All steps reviewed")).toBeVisible();
    await page.getByRole("tab", { name: "Audit log" }).click();
    await expect(page.getByRole("tabpanel").getByRole("row", { name: /Refreshed draft from sources/ })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
    expect((await publicText(page)).includes("Priya"), "a name shown on Review after refresh").toBe(false);

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
    await expect(matrixTable.getByRole("row")).toHaveCount(9);
    const lirRow = matrixTable.getByRole("row", { name: /Load and return LIR/ });
    await expect(lirRow).toContainText("Contradicts");
    await expect(lirRow).toContainText("Contested");
    await expect(lirRow).toContainText("Threshold");
    await expect(matrixTable.getByRole("row", { name: /Approve load plan/ })).toContainText("Silent");
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
    for (const name of ["AI flags", "Constraints by cause", "External practice (R)", "Validation questions", "Rejected claims"]) {
      await registerChoice.getByRole("radio", { name }).click();
      await expect(registerChoice.getByRole("radio", { name })).toHaveAttribute("aria-checked", "true");
      expect(await seriousViolations(page)).toEqual([]);
    }
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
    await expect(page.getByText("8 of 8 steps reviewed")).toBeVisible();

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
    await expect(offline.getByRole("group", { name: "Swimlane map" })).toBeVisible();
    await offline.getByRole("link", { name: /^Activity, Draft load plan/ }).click();
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
    await expect(page.getByText("8 of 8 steps reviewed")).toBeVisible();
    await expect(page.getByRole("region", { name: "Visual walkthrough" })).toContainText(CAPTION);
    expect(await seriousViolations(page)).toEqual([]);

    // Every AI call shows in Settings, as usage only.
    await page.goto("/settings");
    const usage = page.getByRole("region", { name: "AI usage" });
    await expect(usage.getByRole("table")).toBeVisible();
    await expect(usage.getByText(/All time: \d+ calls/)).toBeVisible();
    // Three interview chunks, read twice: the first draft and the refresh (P6).
    await expect(usage.getByRole("row").filter({ hasText: "Extracting steps (interview)" })).toHaveCount(6);
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
  } finally {
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
    await expect(summary.getByText("Steps drafted").locator("xpath=following-sibling::dd")).toHaveText("7");
    await expect(summary.getByText(/Signal strength: Limited/)).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);

    // Review: the banner says Limited; the quality card warns but only the review blocks.
    await summary.getByRole("link", { name: "Start reviewing" }).click();
    await expect(page.getByText("0 of 7 steps reviewed")).toBeVisible();
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
