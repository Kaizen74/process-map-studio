import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  TOKENS_CSS,
  propertyName,
  readTokens,
  renderTokensCss,
} from "../../scripts/generate-tokens.mjs";

// PRD §5.2 and constraint 20: one design system, tokens only, WCAG 2.1 AA contrast.
const root = resolve(__dirname, "../..");
const tokens = readTokens();
const colors = tokens.color as Record<string, string>;

function filesUnder(dir: string, extensions: string[]): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return filesUnder(path, extensions);
    return extensions.some((ext) => name.endsWith(ext)) ? [path] : [];
  });
}

function luminance(hex: string): number {
  const channels = [0, 2, 4].map((i) => parseInt(hex.replace("#", "").slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}

function contrast(foreground: string, background: string): number {
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a);
  return ((light ?? 0) + 0.05) / ((dark ?? 0) + 0.05);
}

function color(name: string): string {
  const value = colors[name];
  if (!value) throw new Error(`missing colour token ${name}`);
  return value;
}

describe("design tokens", () => {
  it("tokens.css is in sync with shared/design_tokens.json", () => {
    expect(readFileSync(TOKENS_CSS, "utf8")).toBe(renderTokensCss(tokens));
  });

  it("keeps the PRD colour values", () => {
    expect(colors).toMatchObject({
      bg: "#F4F3EF",
      surface: "#FFFFFF",
      "surface-2": "#FAFAF7",
      ink: "#1E1D1A",
      "ink-4": "#6F6C64",
      "decision-stroke": "#534AB7",
      "approval-stroke": "#0F6E56",
      constraint: "#D85A30",
      "danger-text": "#993C1D",
    });
  });

  it("names colours bare and other tokens with their group", () => {
    expect(propertyName("color", "ink")).toBe("--ink");
    expect(propertyName("space", "8")).toBe("--space-8");
  });

  it("rejects malformed tokens", () => {
    expect(() => renderTokensCss({ color: { Ink: "#000" } })).toThrow(/lower-case/);
    expect(() => renderTokensCss({ color: { ink: "red; x" } })).toThrow(/CSS value/);
    expect(() => renderTokensCss({ Color: {} })).toThrow(/group/);
  });
});

describe("tokens only", () => {
  const scanned = [
    ...filesUnder(join(root, "src/components"), [".ts", ".tsx", ".css"]),
    ...filesUnder(join(root, "src/features"), [".ts", ".tsx", ".css"]),
  ];

  it("has no raw colour values in components or features", () => {
    const offenders = scanned.flatMap((file) => {
      const text = readFileSync(file, "utf8");
      const hits = text.match(/#[0-9a-fA-F]{3,8}\b|\brgba?\(/g) ?? [];
      return hits.map((hit) => `${relative(root, file)}: ${hit}`);
    });
    expect(offenders).toEqual([]);
  });

  it("the raw-colour scan would catch a hex value and rgb()", () => {
    const sample = "color: #1E1D1A; background: rgba(0,0,0,.1)";
    expect(sample.match(/#[0-9a-fA-F]{3,8}\b|\brgba?\(/g)).toHaveLength(2);
  });

  it("every var(--name) used in the source is a defined token", () => {
    const defined = new Set(
      Object.entries(tokens)
        .filter(([group]) => !group.startsWith("$"))
        .flatMap(([group, values]) => Object.keys(values).map((name) => propertyName(group, name))),
    );
    const sources = filesUnder(join(root, "src"), [".ts", ".tsx", ".css"]);
    const unknown = sources.flatMap((file) => {
      const text = readFileSync(file, "utf8");
      const localProps = new Set([...text.matchAll(/(--[a-z0-9-]+)\s*:/g)].map((m) => m[1]));
      return [...text.matchAll(/var\((--[a-z0-9-]+)/g)]
        .map((m) => m[1] ?? "")
        .filter((name) => !defined.has(name) && !localProps.has(name))
        .map((name) => `${relative(root, file)}: ${name}`);
    });
    expect(unknown).toEqual([]);
  });
});

describe("contrast (WCAG 2.1 AA)", () => {
  const backgrounds = ["surface", "surface-2", "bg"];

  it.each(["ink", "ink-2", "ink-3", "ink-4", "danger-text", "decision-stroke", "approval-stroke"])(
    "text colour %s is at least 4.5:1 on every background",
    (name) => {
      for (const bg of backgrounds) {
        expect(contrast(color(name), color(bg))).toBeGreaterThanOrEqual(4.5);
      }
    },
  );

  it.each([
    ["danger-text", "danger-bg"],
    ["approval-stroke", "approval-fill"],
    ["decision-stroke", "decision-fill"],
    ["on-ink", "ink"],
  ])("%s on %s is at least 4.5:1", (fg, bg) => {
    expect(contrast(color(fg), color(bg))).toBeGreaterThanOrEqual(4.5);
  });

  it("input outlines are at least 3:1 (non-text contrast)", () => {
    for (const bg of backgrounds) {
      expect(contrast(color("border-input"), color(bg))).toBeGreaterThanOrEqual(3);
    }
  });

  // PRD §5.2 impact and Reality tokens (P13): each impact colour carries text on white, on the
  // page background and on its own tint, and white text sits on it; the documented baseline's
  // stroke still meets 3:1 so its meaning never rests on the quiet fill.
  const impacts = ["impact-control", "impact-time", "impact-capacity", "impact-workaround"];

  it.each(impacts)("%s is at least 4.5:1 on every background, on its tint and under white text", (name) => {
    for (const bg of [...backgrounds, `${name}-bg`]) {
      expect(contrast(color(name), color(bg))).toBeGreaterThanOrEqual(4.5);
    }
    expect(contrast(color("on-ink"), color(name))).toBeGreaterThanOrEqual(4.5);
  });

  it("designed work is text-safe and the baseline stroke is at least 3:1", () => {
    for (const bg of backgrounds) {
      expect(contrast(color("designed-work"), color(bg))).toBeGreaterThanOrEqual(4.5);
      expect(contrast(color("baseline-stroke"), color(bg))).toBeGreaterThanOrEqual(3);
    }
    expect(contrast(color("ink"), color("baseline-fill"))).toBeGreaterThanOrEqual(4.5);
  });
});

describe("RQ3 channel discipline (PRD §5.12.8)", () => {
  it("impact and Reality tokens are used only by the Reality components and the views they feed", () => {
    const allowed = ["src/components/reality/", "src/styles/tokens.css"];
    const users = filesUnder(join(root, "src"), [".ts", ".tsx", ".css"])
      .filter((file) => /--(impact-|designed-work|baseline-)/.test(readFileSync(file, "utf8")))
      .map((file) => relative(root, file).replaceAll("\\", "/"));
    expect(users.filter((f) => !allowed.some((a) => f.startsWith(a)))).toEqual([]);
    expect(users.some((f) => f.startsWith("src/components/reality/"))).toBe(true);
  });
});

describe("self-hosted fonts", () => {
  const css = readFileSync(join(root, "src/styles/fonts.css"), "utf8");
  const urls = [...css.matchAll(/url\('([^']+)'\)/g)].map((m) => m[1] ?? "");

  it("uses only local files that exist", () => {
    expect(urls.length).toBe(8);
    for (const url of urls) {
      expect(url.startsWith("/fonts/")).toBe(true);
      expect(existsSync(join(root, "public", url))).toBe(true);
    }
  });

  it("declares only weights 400 and 500", () => {
    const weights = new Set([...css.matchAll(/font-weight: (\d+)/g)].map((m) => m[1]));
    expect([...weights].sort()).toEqual(["400", "500"]);
  });

  it("ships the font licences", () => {
    expect(existsSync(join(root, "public/fonts/OFL-IBM-Plex-Sans.txt"))).toBe(true);
    expect(existsSync(join(root, "public/fonts/OFL-IBM-Plex-Mono.txt"))).toBe(true);
  });
});
