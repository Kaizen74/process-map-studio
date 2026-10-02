import { describe, expect, it } from "vitest";
import {
  bySection,
  domainPolicy,
  filterFindings,
  linesToList,
  NO_FILTERS,
  openItems,
  rejectedCounts,
  removeHit,
  runBlocker,
  severityCounts,
  tierLabel,
  typeLabel,
  type Brief,
  type GapFinding,
  type GapReport,
} from "../../src/lib/gap";

export function finding(changes: Partial<GapFinding> = {}): GapFinding {
  return {
    id: "f1",
    section: "fact",
    finding_type: "threshold_gap",
    title:
      "Loading report return: 10 minutes in SOP RP-02, up to 15 minutes' wait in practice",
    text: "The SOP says 10 minutes; practice waits fifteen minutes.",
    element_ids: ["lir"],
    elements: [{ id: "lir", label: "Load and return LIR" }],
    evidence: [],
    basis: "",
    provenance: "O",
    severity: "medium",
    evidence_strength: "strong",
    comparison: null,
    verification_status: "verified",
    rejection_guardrail: "",
    rejection_reason: "",
    verifier_verdict: "supported",
    needs_check: false,
    question: "",
    notes: [],
    disposition: "open",
    disposition_note: "",
    created_item_ref: "",
    gap_class: null,
    stated_reason: "",
    cause_type: null,
    ...changes,
  };
}

export const BRIEF: Brief = {
  process_name: "Load control",
  industry: "Aviation ground handling",
  adjacent_industries: ["Air cargo"],
  region: "",
  steps: ["Draft load plan", "Acme Ground Services asks for a check"],
  questions: ["How are approvals allocated?"],
  max_searches: 10,
  allowed_domains: [],
  blocked_domains: [],
  recency_years: 5,
};

describe("gap helpers", () => {
  it("filters by type, severity, evidence and decision", () => {
    const list = [
      finding(),
      finding({
        id: "f2",
        finding_type: "ownership_mismatch",
        severity: "high",
      }),
      finding({
        id: "f3",
        severity: "low",
        evidence_strength: "weak",
        disposition: "dismissed",
      }),
    ];
    expect(filterFindings(list, NO_FILTERS)).toHaveLength(3);
    expect(
      filterFindings(list, { ...NO_FILTERS, severity: "high" }).map(
        (f) => f.id,
      ),
    ).toEqual(["f2"]);
    expect(
      filterFindings(list, { ...NO_FILTERS, strength: "weak" }).map(
        (f) => f.id,
      ),
    ).toEqual(["f3"]);
    expect(
      filterFindings(list, { ...NO_FILTERS, disposition: "open" }).map(
        (f) => f.id,
      ),
    ).toEqual(["f1", "f2"]);
    expect(
      filterFindings(list, { ...NO_FILTERS, type: "threshold_gap" }).map(
        (f) => f.id,
      ),
    ).toEqual(["f1", "f3"]);
  });

  it("groups by section in report order and counts severities", () => {
    const list = [
      finding({ section: "recommendation" }),
      finding({ id: "f2" }),
    ];
    expect(bySection(list).map((g) => g.section)).toEqual([
      "fact",
      "recommendation",
    ]);
    expect(
      severityCounts([
        { severity: "high" },
        { severity: "high" },
        { severity: "low" },
      ]),
    ).toBe("2 high · 1 low");
    expect(severityCounts([])).toBe("no findings");
  });

  it("counts open items across findings and questions, rejected ones by guardrail", () => {
    const report = {
      findings: [finding(), finding({ id: "f2", disposition: "dismissed" })],
      questions: [finding({ id: "q", question: "Why?" })],
    } as GapReport;
    expect(openItems(report)).toBe(2);
    const rejected = [
      finding({ rejection_guardrail: "GX2" }),
      finding({ rejection_guardrail: "GX1" }),
      finding({ rejection_guardrail: "GX2" }),
    ];
    expect(rejectedCounts(rejected)).toEqual([
      { guardrail: "GX1", label: "no source cited", count: 1 },
      {
        guardrail: "GX2",
        label: "source not returned by the search",
        count: 2,
      },
    ]);
  });

  it("labels are plain words", () => {
    expect(typeLabel("dead_control_candidate")).toBe(
      "Control nobody may perform",
    );
    expect(typeLabel("brand_new_type")).toBe("brand new type");
    expect(tierLabel("industry_association")).toBe("Industry association");
  });

  it("Remove takes a scan hit out of every field, ignoring case and punctuation", () => {
    const next = removeHit(
      {
        ...BRIEF,
        questions: ["Does acme ground services check it?"],
        process_name: "Acme Ground Services load control",
      },
      "Acme Ground Services",
    );
    expect(next.process_name).toBe("load control");
    expect(next.steps).toEqual(["Draft load plan", "asks for a check"]);
    expect(next.questions).toEqual(["Does check it?"]);
    expect(
      removeHit(
        { ...BRIEF, steps: ["Acme Ground Services"] },
        "Acme Ground Services",
      ).steps,
    ).toEqual([]);
  });

  it("the brief's lines and domain policy", () => {
    expect(linesToList(" a \n\n b\n")).toEqual(["a", "b"]);
    expect(domainPolicy(BRIEF)).toBe("none");
    expect(domainPolicy({ ...BRIEF, blocked_domains: ["x.com"] })).toBe(
      "blocked",
    );
    expect(domainPolicy({ ...BRIEF, allowed_domains: ["iso.org"] })).toBe(
      "allowed",
    );
  });

  it("says why research can't run yet: switched off, scan hits, not ticked", () => {
    const clean = {
      brief: BRIEF,
      text: "",
      confirmed: true,
      scan: { hits: [] },
    };
    expect(runBlocker(clean, false, false)).toBe(
      "Web research is switched off. Turn it on in Settings first.",
    );
    const hits = {
      ...clean,
      scan: {
        hits: [{ text: "Acme", reason: "A confidential term from Setup" }],
      },
    };
    expect(runBlocker(hits, true, false)).toMatch(
      /Remove the highlighted items/,
    );
    expect(runBlocker(hits, true, true)).toBeNull(); // changed since: saved and scanned again first
    expect(runBlocker({ ...clean, confirmed: false }, true, false)).toMatch(
      /Tick “This brief contains/,
    );
    expect(runBlocker(clean, true, false)).toBeNull();
  });
});
