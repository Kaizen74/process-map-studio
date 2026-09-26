// Generates src/styles/tokens.css from shared/design_tokens.json (PRD §5.2).
//   npm run tokens          write the file
//   npm run tokens -- --check   exit 1 if the file is out of date
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
export const TOKENS_JSON = resolve(here, "../../shared/design_tokens.json");
export const TOKENS_CSS = resolve(here, "../src/styles/tokens.css");

const NAME = /^[a-z0-9]+(-[a-z0-9]+)*$/;

/** CSS custom property name for a token: colours are bare (--ink), others prefixed. */
export function propertyName(group, name) {
  return group === "color" ? `--${name}` : `--${group}-${name}`;
}

/** Turn the token JSON into the tokens.css text. Throws on malformed tokens. */
export function renderTokensCss(tokens) {
  const lines = [
    "/* Generated from shared/design_tokens.json by `npm run tokens`. Do not edit by hand. */",
    ":root {",
  ];
  for (const [group, values] of Object.entries(tokens)) {
    if (group.startsWith("$")) continue;
    if (!NAME.test(group) || typeof values !== "object" || values === null) {
      throw new Error(`Token group "${group}" must be a lower-case name holding an object`);
    }
    lines.push(`  /* ${group} */`);
    for (const [name, value] of Object.entries(values)) {
      if (!NAME.test(name)) throw new Error(`Token name "${group}.${name}" is not lower-case-dashed`);
      if (typeof value !== "string" || value.trim() === "" || /[;{}]/.test(value)) {
        throw new Error(`Token "${group}.${name}" must be a non-empty CSS value without ; { }`);
      }
      lines.push(`  ${propertyName(group, name)}: ${value};`);
    }
  }
  lines.push("}", "");
  return lines.join("\n");
}

export function readTokens(path = TOKENS_JSON) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function main() {
  const css = renderTokensCss(readTokens());
  if (process.argv.includes("--check")) {
    let current = "";
    try {
      current = readFileSync(TOKENS_CSS, "utf8");
    } catch {
      current = "";
    }
    if (current !== css) {
      console.error("tokens.css is out of date. Run: npm run tokens");
      process.exit(1);
    }
    console.log("tokens.css is up to date.");
    return;
  }
  writeFileSync(TOKENS_CSS, css);
  console.log(`Wrote ${TOKENS_CSS}`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
