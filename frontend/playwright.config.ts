import { defineConfig } from "@playwright/test";
import { rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

// Browser checks (PRD §6.2 items 6–7): the real app, built frontend + backend, on its own port,
// with Claude mocked (MOCK_CLAUDE=1), a throwaway settings file and a throwaway data folder
// (never the real .env or data/).
const here = dirname(fileURLToPath(import.meta.url));
const PORT = 8123;
export const E2E_ENV_FILE = join(tmpdir(), `pms-e2e-${process.pid}.env`);
export const E2E_DATA_DIR = join(tmpdir(), `pms-e2e-${process.pid}-data`);
rmSync(E2E_ENV_FILE, { force: true });
rmSync(E2E_DATA_DIR, { recursive: true, force: true });

const python =
  process.platform === "win32"
    ? resolve(here, "../.venv/Scripts/python.exe")
    : resolve(here, "../.venv/bin/python");

export default defineConfig({
  testDir: "tests/e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: true,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    browserName: "chromium",
    viewport: { width: 1440, height: 900 },
    launchOptions: {
      // Use a preinstalled Chromium when one is provided (cloud build machines);
      // otherwise Playwright's own (`npx playwright install chromium`).
      ...(process.env.PMS_CHROMIUM_PATH ? { executablePath: process.env.PMS_CHROMIUM_PATH } : {}),
    },
  },
  webServer: {
    command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port ${PORT} --log-level warning`,
    cwd: resolve(here, "../backend"),
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      PMS_ENV_FILE: E2E_ENV_FILE,
      DATA_DIR: E2E_DATA_DIR,
      MOCK_CLAUDE: "1",
      APP_PORT: String(PORT),
    },
  },
});
