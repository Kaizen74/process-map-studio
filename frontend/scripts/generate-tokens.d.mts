// Type declarations for generate-tokens.mjs (used by the design-system tests).
export const TOKENS_JSON: string;
export const TOKENS_CSS: string;
export function propertyName(group: string, name: string): string;
export function renderTokensCss(tokens: Record<string, unknown>): string;
export function readTokens(path?: string): Record<string, Record<string, string>>;
