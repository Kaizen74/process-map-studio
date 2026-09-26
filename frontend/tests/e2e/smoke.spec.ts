import { expect, test } from "@playwright/test";
import { FAKE_KEY } from "./helpers";

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
