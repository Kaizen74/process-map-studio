import js from "@eslint/js";
import { defineConfig } from "eslint/config";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

// PRD §3.2 and §5.11: components are presentational only. They receive data and callbacks
// and may never import the API client (src/api) or the data hooks (src/hooks).
export const componentImportRestriction = {
  files: ["src/components/**/*.{ts,tsx}"],
  rules: {
    "no-restricted-imports": [
      "error",
      {
        patterns: [
          {
            group: ["**/api", "**/api/**", "**/hooks", "**/hooks/**", "@/api/**", "@/hooks/**"],
            message:
              "Components are presentational only: pass data and callbacks in from a feature instead of importing src/api or src/hooks.",
          },
        ],
      },
    ],
  },
};

export default defineConfig(
  { ignores: ["dist", "coverage", "node_modules"] },
  {
    files: ["**/*.{ts,tsx,js}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.strict,
      reactHooks.configs.flat.recommended,
    ],
    languageOptions: { ecmaVersion: 2023, globals: { ...globals.browser, ...globals.node } },
    plugins: { "react-refresh": reactRefresh },
    rules: {
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    },
  },
  componentImportRestriction,
);
