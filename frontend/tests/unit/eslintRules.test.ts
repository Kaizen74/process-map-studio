import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

// PRD §3.2: an eslint rule blocks src/components/ from importing src/api/ or src/hooks/.
const eslint = new ESLint({ cwd: process.cwd() });

async function restrictedImportErrors(filePath: string, code: string): Promise<number> {
  const [result] = await eslint.lintText(code, { filePath });
  return (result?.messages ?? []).filter((m) => m.ruleId === "no-restricted-imports").length;
}

describe("component import restriction", () => {
  it.each([
    'import { request } from "../../api/request";\nexport const x = request;\n',
    'import { useSettings } from "../../hooks/useSettings";\nexport const x = useSettings;\n',
    'import { request } from "../api";\nexport const x = request;\n',
  ])("blocks components from fetching data: %s", async (code) => {
    expect(await restrictedImportErrors("src/components/common/Button.tsx", code)).toBe(1);
  });

  it("allows features to use hooks", async () => {
    const code =
      'import { useSettings } from "../../hooks/useSettings";\nexport const x = useSettings;\n';
    expect(await restrictedImportErrors("src/features/settings/SettingsScreen.tsx", code)).toBe(0);
  });

  it("allows components to import shared utilities", async () => {
    const code = 'import { formatMinutes } from "../../lib/format";\nexport const x = formatMinutes;\n';
    expect(await restrictedImportErrors("src/components/common/Chip.tsx", code)).toBe(0);
  });
});
