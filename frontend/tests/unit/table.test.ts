import { describe, expect, it } from "vitest";
import { filterOptions, tableRows } from "../../src/lib/table";
import { SAMPLE } from "../sampleMap";

describe("the table view's rows (PRD §5.7.4)", () => {
  it("one row per step in process order, holding what the map shows", () => {
    const rows = tableRows(SAMPLE.graph, "all");
    expect(rows.map((r) => r.label)).toEqual(
      SAMPLE.graph.elements.filter((e) => !["start", "end"].includes(e.kind)).map((e) => e.label),
    );
    const plan = rows.find((r) => r.label === "Draft load plan");
    expect(plan).toMatchObject({ kind: "Activity", lane: "Load controller", time: "~20 min", review: "Unreviewed" });
    expect(rows.find((r) => r.label === "Issue load sheet")?.time).toBe("No time stated");
    expect(rows.find((r) => r.label === "Special loads OK?")?.time).toBe(""); // decisions take no time
  });

  it("filters with counts; rejected and reviewed steps leave the Unreviewed filter", () => {
    const graph = structuredClone(SAMPLE.graph);
    graph.elements = graph.elements.map((e, i) =>
      i === 1 ? { ...e, review_status: "confirmed" } : i === 2 ? { ...e, review_status: "rejected", source_state: "contested" } : e,
    );
    const counts = Object.fromEntries(filterOptions(graph).map((f) => [f.value, f.label]));
    expect(counts.all).toBe("All steps (10)"); // v1.10 A.5
    expect(counts.unreviewed).toBe("Unreviewed (8)");
    expect(tableRows(graph, "unreviewed").some((r) => r.rejected)).toBe(false);
    expect(tableRows(graph, "contested").every((r) => r.sourceState === "contested")).toBe(true);
    expect(tableRows(graph, "all").find((r) => r.rejected)?.review).toBe("Rejected");
  });
});
