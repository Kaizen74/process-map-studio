import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SourceBreakdown } from "../../src/api/types";
import { SourceBreakdownTable } from "../../src/features/draft/SourceBreakdownTable";
import { RemovedSourcesNote } from "../../src/features/review/RemovedSourcesNote";
import { deleteWarning } from "../../src/lib/sources";
import { seriousViolations } from "../axe";
import { fakeApi } from "../renderApp";

// DECISIONS 114 (Eric's SOP Section 04 test, 2026-11-27): a draft made from deleted sources says
// so, deleting a source a map uses is warned about first, and the Draft screen shows what each
// source gave.

afterEach(() => vi.unstubAllGlobals());

function withClient(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

describe("deleting a source a map was drafted from", () => {
  it("says which versions and how many steps use it", () => {
    expect(deleteWarning({ used_by: ["v0.1 (draft)"], steps_citing: 14 })).toBe(
      "v0.1 (draft) was drafted from this file. 14 steps of the current map are built from it. Deleting it takes " +
        "that evidence away, and the draft will say it needs a refresh. To replace the file, upload the new copy, " +
        "refresh the draft, then delete this one.",
    );
    expect(deleteWarning({ used_by: ["v1.0 (published)", "v1.1 (draft)"], steps_citing: 1 })).toMatch(
      /^v1\.0 \(published\) and v1\.1 \(draft\) were drafted from this file\. 1 step of the current map is built/,
    );
    expect(deleteWarning({ used_by: ["v0.1 (draft)"], steps_citing: 0 })).toMatch(/this file\. Deleting it/);
  });

  it("says nothing for a file no map uses", () => {
    expect(deleteWarning({ used_by: [], steps_citing: 0 })).toBe("");
    expect(deleteWarning({})).toBe("");
  });
});

describe("a draft made from sources deleted since", () => {
  it("names them and asks for a refresh", async () => {
    fakeApi({
      "GET /api/versions/v1": () => ({ body: { id: "v1", removed_sources: ["SOP section 4.pdf", "SOP section 5.pdf"] } }),
    });
    const { container } = withClient(<RemovedSourcesNote versionId="v1" />);
    const note = await screen.findByRole("status");
    expect(note.textContent).toBe(
      "Needs a refresh. This draft was made from SOP section 4.pdf and SOP section 5.pdf, which have since been " +
        "deleted. Steps that cited them have lost that evidence. Refresh the draft (More, then Refresh draft from " +
        "sources) to rebuild it from the sources you have now.",
    );
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("shows nothing while every source is still there", async () => {
    const { calls } = fakeApi({ "GET /api/versions/v1": () => ({ body: { id: "v1", removed_sources: [] } }) });
    withClient(<RemovedSourcesNote versionId="v1" />);
    await vi.waitFor(() => expect(calls.some((c) => c.key === "GET /api/versions/v1")).toBe(true));
    expect(screen.queryByRole("status")).toBeNull();
  });
});

const BREAKDOWN: SourceBreakdown[] = [
  {
    source_id: "s1",
    filename: "SOP section 4.pdf",
    kind: "sop",
    found: 120,
    verified: 95,
    rejected: 20,
    outside_flow: 5,
    steps: 14,
    reasons: [
      { reason: "names a role the cited passage doesn't", count: 12 },
      { reason: "quote not found in the cited passage", count: 8 },
    ],
  },
  {
    source_id: "s2",
    filename: "SOP section 5.pdf",
    kind: "sop",
    found: 30,
    verified: 0,
    rejected: 30,
    outside_flow: 0,
    steps: 0,
    reasons: [{ reason: "quote not found in the cited passage", count: 30 }],
  },
];

describe("what each source gave the draft", () => {
  it("lists every source with its counts and the reasons claims were rejected", async () => {
    const { container } = render(<SourceBreakdownTable sources={BREAKDOWN} />);
    const table = screen.getByRole("table", { name: "What each source gave this draft" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => r.textContent)).toEqual([
      "SOP section 4.pdf1209520 (12 names a role the cited passage doesn't; 8 quote not found in the cited passage)514",
      "SOP section 5.pdf30030 (30 quote not found in the cited passage)00",
    ]);
    expect(screen.getByText(/^1 source gave claims but no step of this map is built from them yet/)).toBeTruthy();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("shows nothing for a draft made before the breakdown existed", () => {
    const { container } = render(<SourceBreakdownTable sources={[]} />);
    expect(container.textContent).toBe("");
  });
});
