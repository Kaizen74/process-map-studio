import { expect, test, type Page } from "@playwright/test";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { FIXTURE_NAME, publicText, seriousViolations } from "./helpers";

// Phase P2 path through the real app: a transcript is read in the background, its speakers are
// mapped, names stay in the owner-only places, and a passage is corrected. Cleans up after itself.
const fixtures = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../backend/tests/fixtures/engagement_load_control",
);

async function expectNoName(page: Page, where: string) {
  const text = await publicText(page);
  expect(text.includes(FIXTURE_NAME), `${FIXTURE_NAME} shown on ${where}`).toBe(false);
  expect(text.includes("Priya"), `"Priya" shown on ${where}`).toBe(false);
}

test("transcript: read, map speakers, hide the name everywhere, correct a passage", async ({ page, request }) => {
  const created = await request.post("/api/engagements", {
    data: { name: "Load control", trigger: "Flight scheduled", end_point: "Load sheet issued" },
  });
  const { id } = (await created.json()) as { id: string };
  await request.post(`/api/engagements/${id}/roles`, { data: { name: "Load controller" } });
  try {
    await page.goto(`/engagements/${id}/sources`);
    await page.getByTestId("source-file-input").setInputFiles([
      join(fixtures, "interview_transcript.txt"),
      join(fixtures, "sop_LC-07.docx"),
      join(fixtures, "sop_RP-02.docx"),
    ]);
    await expect(page.getByText("3 files uploaded.")).toBeVisible();
    const table = page.getByRole("table", { name: "Sources for this engagement" });
    await expect(table.getByText("Ready")).toHaveCount(3); // read in the background, then shown
    await expect(page.getByText("Map 2 speakers in interview_transcript.txt")).toBeVisible();

    // The instruction-like line in SOP RP-02 §9 is flagged in words.
    await table.getByRole("button", { name: "sop_RP-02.docx", exact: true }).click();
    const rp02 = page.getByRole("region", { name: "sop_RP-02.docx" });
    await expect(
      rp02.getByRole("listitem").filter({ hasText: "§9" }).getByText("Instruction-like text. Treated as data and ignored."),
    ).toBeVisible();

    // Open the transcript: before mapping, the name is already hidden outside the owner-only cards.
    await table.getByRole("button", { name: "interview_transcript.txt", exact: true }).click();
    const mapping = page.getByRole("region", { name: "Speaker mapping" });
    await expect(mapping.getByRole("row").filter({ hasText: FIXTURE_NAME })).toBeVisible();
    await expect(page.getByRole("list", { name: "Names hidden in this engagement" })).toContainText(
      `${FIXTURE_NAME} → shown as [name]`,
    );
    await expectNoName(page, "Sources before mapping");

    await mapping.getByLabel("Role for Interviewer").selectOption("interviewer");
    await mapping.getByLabel(`Role for ${FIXTURE_NAME}`).selectOption({ label: "Load controller" });
    await mapping.getByRole("button", { name: "Save speakers" }).click();
    await expect(page.getByText("2 speakers saved.")).toBeVisible();
    const viewer = page.getByRole("region", { name: "interview_transcript.txt" });
    await expect(viewer.getByRole("listitem").filter({ hasText: "06:40" })).toContainText("Load controller");
    await expect(page.getByText(/Map \d speakers? in/)).toHaveCount(0);
    await expect(page.getByRole("list", { name: "Names hidden in this engagement" })).toContainText(
      `${FIXTURE_NAME} → shown as Load controller`,
    );

    // Correct a passage in the owner-only editor.
    await viewer.getByRole("button", { name: "Correct the text" }).click();
    const editor = viewer.getByRole("list", { name: "Passages to correct" });
    await editor.getByRole("button", { name: "Correct passage 31:10" }).click();
    await editor.getByLabel("Text of passage 31:10").fill("Then I issue the final load sheet, around T-15, through the system.");
    await editor.getByRole("button", { name: "Save correction" }).click();
    await expect(page.getByText("Passage corrected.")).toBeVisible();
    await viewer.getByRole("button", { name: "Done correcting" }).click();
    await expect(viewer.getByRole("listitem").filter({ hasText: "31:10" })).toContainText("through the system.");
    await expect(viewer.getByRole("listitem").filter({ hasText: "31:10" })).toContainText("Corrected");

    // Privacy scan of every screen built so far (PRD §6.2 item 8).
    await expectNoName(page, "Sources after mapping");
    for (const [where, path] of [
      ["Home", "/"],
      ["Setup", `/engagements/${id}/setup`],
      ["Draft (later phase)", `/engagements/${id}/draft`],
      ["Settings", "/settings"],
    ] as const) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expectNoName(page, where);
    }
  } finally {
    expect((await request.delete(`/api/engagements/${id}`)).status()).toBe(204);
  }
});

test("Sources with the speaker mapping, names list and correction editor open has no serious or critical violations", async ({
  page,
  request,
}) => {
  const created = await request.post("/api/engagements", { data: { name: "Load control" } });
  const { id } = (await created.json()) as { id: string };
  await request.post(`/api/engagements/${id}/roles`, { data: { name: "Load controller" } });
  try {
    await page.goto(`/engagements/${id}/sources`);
    await page.getByTestId("source-file-input").setInputFiles(join(fixtures, "interview_transcript.txt"));
    await expect(page.getByRole("table", { name: "Sources for this engagement" }).getByText("Ready")).toBeVisible();
    await page.getByRole("button", { name: "interview_transcript.txt", exact: true }).click();
    await expect(page.getByRole("table", { name: "Speakers in this transcript" })).toBeVisible();
    await expect(page.getByRole("list", { name: "Names hidden in this engagement" })).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);

    await page.getByRole("button", { name: "Correct the text" }).click();
    await page.getByRole("button", { name: "Correct passage 06:40" }).click();
    await expect(page.getByLabel("Text of passage 06:40")).toBeVisible();
    expect(await seriousViolations(page)).toEqual([]);
  } finally {
    expect((await request.delete(`/api/engagements/${id}`)).status()).toBe(204);
  }
});

test("the privacy scan catches a name outside the owner-only places (planted)", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.evaluate((name) => {
    const inside = document.createElement("div");
    inside.dataset.ownerOnly = "speaker-mapping";
    inside.textContent = `${name} (allowed here)`;
    document.querySelector("main")?.appendChild(inside);
  }, FIXTURE_NAME);
  expect(await publicText(page)).not.toContain(FIXTURE_NAME);
  await page.evaluate((name) => {
    const leak = document.createElement("p");
    leak.textContent = `Thanks, ${name}`;
    document.querySelector("main")?.appendChild(leak);
  }, FIXTURE_NAME);
  expect(await publicText(page)).toContain(FIXTURE_NAME);
});
