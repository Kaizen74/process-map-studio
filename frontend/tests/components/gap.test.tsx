import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BriefEditor, FindingCard, SourceCard } from "../../src/components/gap";
import type { GapEvidence, GapReport } from "../../src/lib/gap";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp } from "../renderApp";
import { BRIEF, finding } from "../unit/gap.test";

afterEach(() => vi.unstubAllGlobals());

const SOP: GapEvidence = {
  side: "documents",
  source_id: "s-rp02",
  source_kind: "sop",
  source_name: "sop RP-02",
  stance: "contradicts",
  segment_id: "seg-2",
  anchor: "§2",
  quote: "return the loading report to Load Control within 10 minutes of loading completion",
  url: "",
  tier: "",
  page_age: "",
  citation_id: "",
};
const SILENT: GapEvidence = { ...SOP, side: "practice", source_id: "s-int", source_kind: "interview_transcript",
  source_name: "interview transcript", stance: "silent", segment_id: null, anchor: "", quote: "" }; // prettier-ignore
const WEB: GapEvidence = {
  ...SOP,
  side: "external",
  source_id: "",
  source_kind: "industry_association",
  source_name: "Illustrative industry guidance on load control",
  stance: "supports",
  segment_id: null,
  anchor: "",
  quote: "The load sheet shall be checked by a second qualified person before it is signed.",
  url: "https://www.iata.org/illustrative/load-control-guidance",
  tier: "industry_association",
  page_age: "March 2024",
  citation_id: "c1",
};

describe("finding card", () => {
  it("shows the finding with both sides' evidence and offers every decision", async () => {
    const onDecide = vi.fn();
    const onOpenSource = vi.fn();
    const onGoTo = vi.fn();
    const f = finding({ evidence: [SOP, SILENT] });
    const { container, rerender } = render(
      <FindingCard finding={f} mode="internal" locked={false} onGoTo={onGoTo} onOpenSource={onOpenSource} onDecide={onDecide} />,
    );
    expect(screen.getByText("Different threshold")).toBeInTheDocument();
    expect(screen.getByText("Medium severity")).toBeInTheDocument();
    expect(screen.getByText(/Silence is not contradiction/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open Load and return LIR on the map" }));
    expect(onGoTo).toHaveBeenCalledWith("lir");
    const actions = screen.getByRole("group", { name: /Decide on/ });
    expect(within(actions).getAllByRole("button").map((b) => b.textContent)).toEqual([
      "Add as validation question",
      "Add to cause library",
      "Add as step",
      "Dismiss",
    ]);
    fireEvent.click(within(actions).getByRole("button", { name: "Add to cause library" }));
    expect(onDecide).toHaveBeenCalledWith(f, "added_cause");
    expect(await seriousViolations(container)).toEqual([]);

    rerender(
      <FindingCard
        finding={{ ...f, disposition: "dismissed", disposition_note: "The SOP is being rewritten." }}
        mode="internal"
        locked={false}
        onGoTo={onGoTo}
        onOpenSource={onOpenSource}
        onDecide={onDecide}
      />,
    );
    expect(screen.getByText("Decision: Dismissed (The SOP is being rewritten.)")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /Decide on/ })).not.toBeInTheDocument();
  });

  it("an external finding shows source cards, evidence strength and no cause-library choice", () => {
    render(
      <FindingCard
        finding={finding({ evidence: [WEB], provenance: "R", section: "recommendation", comparison: "absent",
          evidence_strength: "weak", notes: ["Confirm with your compliance team; this is not legal advice."] })} // prettier-ignore
        mode="external"
        locked
        onGoTo={vi.fn()}
        onOpenSource={vi.fn()}
        onDecide={vi.fn()}
      />,
    );
    expect(screen.getByText("Absent from the current map")).toBeInTheDocument();
    expect(screen.getByText(/Weak evidence \(vendor or unknown sources only\)/)).toBeInTheDocument();
    expect(screen.getByText(/Confirm with your compliance team/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add to cause library" })).not.toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /Decide on/ })).not.toBeInTheDocument(); // finalised
  });

  it("a source card shows title, domain, tier, date and the excerpt, and opens in a new tab", async () => {
    const { container } = render(<SourceCard evidence={WEB} />);
    expect(screen.getByText("Illustrative industry guidance on load control")).toBeInTheDocument();
    expect(screen.getByText("iata.org")).toBeInTheDocument();
    expect(screen.getByText("Industry association")).toBeInTheDocument();
    expect(container).toHaveTextContent("March 2024");
    expect(container).toHaveTextContent("“The load sheet shall be checked by a second qualified person");
    const link = screen.getByRole("link", { name: /Open source/ });
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("brief editor", () => {
  const STATE = {
    brief: BRIEF,
    text: "Process: Load control",
    confirmed: false,
    scan: { hits: [{ text: "Acme Ground Services", reason: "A confidential term from Setup" }] },
  };

  it("lists each scan hit with Remove, and says why research can't run yet", async () => {
    const onSave = vi.fn();
    const onRun = vi.fn();
    const { container } = render(
      <BriefEditor state={STATE} researchEnabled={false} saving={false} running={false} problem={null}
        onSave={onSave} onRun={onRun} settingsLink={<a href="/settings">Turn it on in Settings</a>} />, // prettier-ignore
    );
    expect(screen.getByText("Acme Ground Services").tagName).toBe("MARK");
    expect(screen.getByText("A confidential term from Setup")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Run research" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Web research is switched off. Turn it on in Settings first.");
    expect(onRun).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /^Remove\s*“Acme Ground Services”$/ }));
    const [saved] = onSave.mock.calls[0] ?? [];
    expect(saved.steps).toEqual(["Draft load plan", "asks for a check"]);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("runs once research is on, the brief is ticked and the scan is clean", () => {
    const onRun = vi.fn();
    render(
      <BriefEditor state={{ ...STATE, scan: { hits: [] } }} researchEnabled saving={false} running={false}
        problem={null} onSave={vi.fn()} onRun={onRun} settingsLink={null} />, // prettier-ignore
    );
    expect(screen.getByText(/No names, confidential terms, map numbers or copied passages found/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Run research" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/Tick “This brief contains no confidential information”/);
    fireEvent.click(screen.getByRole("checkbox", { name: "This brief contains no confidential information" }));
    fireEvent.click(screen.getByRole("button", { name: "Run research" }));
    expect(onRun).toHaveBeenCalledWith(BRIEF, true);
  });
});

describe("Gap analysis screen (PRD §5.4)", () => {
  const DRAFT = {
    id: "v1",
    engagement_id: "e1",
    label: "v0.1",
    state: "draft",
    created_at: "2026-09-28T09:00:00+00:00",
    published_at: null,
    published_by: null,
    parent_version_id: null,
  };
  const ANALYSIS = {
    id: "g1",
    version_id: "v1",
    version_label: "v0.1",
    mode: "internal",
    status: "draft_report",
    job_id: "j1",
    error: "",
    created_at: "2026-09-28T10:00:00+00:00",
    completed_at: "2026-09-28T10:01:00+00:00",
    finalised_at: null,
    notes: [],
    counts: { kept: 1, rejected: 1, open: 2, needs_check: 0 },
  };
  const REPORT: GapReport = {
    analysis: ANALYSIS as GapReport["analysis"],
    findings: [finding({ evidence: [SOP, SILENT] })],
    rejected: [finding({ id: "r1", title: "A made-up rule", verification_status: "rejected", rejection_guardrail: "G4",
      rejection_reason: "quote not found in source" })], // prettier-ignore
    questions: [finding({ id: "q1", title: "Cause not explained by the sources", question: "Why is the approval skipped?",
      text: "Why is the approval skipped?", severity: null, provenance: "", section: "recommendation" })], // prettier-ignore
    sources: [],
    brief: null,
    usage: { calls: 2, input_tokens: 1200, output_tokens: 300 },
    search_count: 0,
  };

  function backend(versions: unknown[] = [DRAFT]) {
    return fakeApi({
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/versions": () => ({ body: versions }),
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/versions/v1/gap-analyses": () => ({ body: [ANALYSIS] }),
      "GET /api/gap-analyses/g1": () => ({ body: REPORT }),
      "GET /api/jobs/j1": () => ({ body: { id: "j1", stages: [], status: "done" } }),
      "GET /api/engagements/e1/roles": () => ({ body: [] }),
      "POST /api/versions/v1/gap-analyses/internal": () => ({ status: 202, body: { analysis_id: "g1", job_id: "j1" } }),
      "PATCH /api/gap-findings/f1": () => ({ body: { ...REPORT.findings[0], disposition: "added_question" } }),
      "PATCH /api/gap-findings/q1": () => ({ body: { ...REPORT.questions[0], disposition: "dismissed" } }),
    });
  }

  it("with no map yet, says to make a draft first", async () => {
    backend([]);
    renderApp("/engagements/e1/gap-analysis");
    expect(await screen.findByText(/Make a draft map first/)).toBeInTheDocument();
  });

  it("shows both analyses, the history and the report; decisions go to the server", async () => {
    const { calls } = backend();
    const { container } = renderApp("/engagements/e1/gap-analysis?analysis=g1");
    expect(await screen.findByRole("region", { name: "Documents vs practice" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "External best practice" })).toHaveTextContent("Web research is off");
    expect(await screen.findByRole("heading", { name: "Facts" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Questions for your SMEs" })).toBeInTheDocument();
    expect(screen.getByText("2 AI calls · 1,500 tokens · 2 items waiting for your decision")).toBeInTheDocument();
    expect(screen.getByText(/Rejected findings \(1\)/)).toBeInTheDocument();
    expect(screen.getByText(/Export .md becomes available once the report is finalised/)).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);

    fireEvent.click(screen.getByRole("button", { name: "Finalise report" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Decide on every finding first: 2 still open.");

    const [card] = screen.getAllByRole("group", { name: /Decide on/ });
    if (!card) throw new Error("card");
    fireEvent.click(within(card).getByRole("button", { name: "Add as validation question" }));
    await waitFor(() => expect(calls.some((c) => c.key === "PATCH /api/gap-findings/f1")).toBe(true));
    expect(calls.find((c) => c.key === "PATCH /api/gap-findings/f1")?.body).toEqual({ disposition: "added_question" });

    const question = screen.getByRole("group", { name: "Decide on “Cause not explained by the sources”" });
    fireEvent.click(within(question).getByRole("button", { name: "Dismiss" }));
    const dialog = await screen.findByRole("dialog", { name: "Dismiss finding" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Dismiss finding" }));
    expect(within(dialog).getByText("Say why you're dismissing this finding.")).toBeInTheDocument();
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Why dismiss it?" }), {
      target: { value: "Checked with the owner." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Dismiss finding" }));
    await waitFor(() =>
      expect(calls.find((c) => c.key === "PATCH /api/gap-findings/q1")?.body).toEqual({
        disposition: "dismissed",
        note: "Checked with the owner.",
      }),
    );
  });

  it("Run analysis starts documents vs practice", async () => {
    const { calls } = backend();
    renderApp("/engagements/e1/gap-analysis");
    fireEvent.click(await screen.findByRole("button", { name: "Run analysis" }));
    await waitFor(() => expect(calls.some((c) => c.key === "POST /api/versions/v1/gap-analyses/internal")).toBe(true));
  });
});
