import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { CompassLink, Engagement } from "../../src/api/types";
import { GuideEditor } from "../../src/components/interview";
import type { GuideView } from "../../src/lib/interview";
import type { QualityCard, VersionDetail, VersionSummary } from "../../src/lib/reviewTypes";
import { seriousViolations } from "../axe";
import comparisons from "../fixtures/comparison_sample.json";
import sample from "../fixtures/compass_sample.json";
import { referenceNote, type ComparisonSummary } from "../../src/lib/comparisons";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp, type Handler } from "../renderApp";

// The return file and the suggested probes (2026-11-12, Eric's brief; DECISIONS 97).
const LINK = sample.link as CompassLink;
const PATH = "/engagements/e1/exports";

const GREEN: QualityCard = {
  checks: Array.from({ length: 10 }, (_, i) => ({
    id: `Q${i + 1}`,
    name: `Check ${i + 1}`,
    status: "pass" as const,
    hard: i < 9,
    detail: "",
  })),
  warnings: [],
  all_green: true,
};

const V1: VersionSummary = {
  id: "v1",
  engagement_id: "e1",
  label: "v1.0",
  state: "published",
  created_at: "2026-11-10T08:00:00+00:00",
  published_at: "2026-11-10T08:00:00+00:00",
  published_by: "Eric",
  parent_version_id: null,
};

function backend(engagement: Engagement, extra: Record<string, Handler> = {}) {
  const detail: VersionDetail = {
    ...V1,
    review: { reviewed: 8, total: 8 },
    change_log: [],
    quality_card: GREEN,
    acceptance: { drafted: 8, confirmed: 8, edited: 0, rejected: 0, unreviewed: 0, added: 0 },
  };
  const routes: Record<string, Handler> = {
    "GET /api/settings": () => ({ body: SETTINGS }),
    "GET /api/engagements/e1": () => ({ body: engagement }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/versions": () => ({ body: [V1] }),
    "GET /api/versions/v1": () => ({ body: detail }),
    "GET /api/versions/v1/gap-analyses": () => ({ body: [] }),
    ...extra,
  };
  return fakeApi(routes);
}

beforeEach(() => window.localStorage.clear());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("the Capability Compass return file on Exports", () => {
  it("is offered for an engagement from a hand-off, with the pilot and cluster and the cells Eric adds", async () => {
    backend({ ...ENGAGEMENT, compass: LINK });
    const { container } = renderApp(PATH);
    const heading = await screen.findByRole("heading", { name: "Capability Compass return file" });
    const card = heading.closest(".card") as HTMLElement;
    expect(within(card).getByText(LINK.key)).toBeInTheDocument();
    expect(within(card).getByText(`${LINK.pilot_ref}, ${LINK.cluster_ref}`)).toBeInTheDocument();
    expect(within(card).getByText(/No quotes, no source text, no names on your list of names to hide/)).toBeInTheDocument();
    const json = within(card).getByRole("link", { name: /Download JSON/ });
    const text = within(card).getByRole("link", { name: /Download readable text/ });
    expect(json).toHaveAttribute("href", "/api/versions/v1/compass-return?fmt=json");
    expect(text).toHaveAttribute("href", "/api/versions/v1/compass-return?fmt=md");
    // Only the hand-off's own cells are offered: no ID is typed or made here.
    const cell = LINK.cell_refs[0] as string;
    expect(within(card).getAllByRole("checkbox")).toHaveLength(LINK.cell_refs.length);
    fireEvent.click(within(card).getByRole("checkbox", { name: cell }));
    expect(within(card).getByText(`${LINK.pilot_ref}, ${LINK.cluster_ref}, ${cell}`)).toBeInTheDocument();
    expect(json).toHaveAttribute("href", `/api/versions/v1/compass-return?fmt=json&cells=${encodeURIComponent(cell)}`);
    expect(text).toHaveAttribute("href", `/api/versions/v1/compass-return?fmt=md&cells=${encodeURIComponent(cell)}`);
    expect(await seriousViolations(container)).toEqual([]);
  });

  // Eric, 2026-11-14: a country that is the reference reads where its differences go instead.
  const SUMMARY = (comparisons.comparisons as ComparisonSummary[])[0] as ComparisonSummary;
  const asSide = (side: "reference" | "other"): ComparisonSummary[] => [
    { ...SUMMARY, [side]: { ...SUMMARY[side], engagement_id: "e1" } },
  ];

  it("tells the reference country that the differences are in the other country's file", async () => {
    backend({ ...ENGAGEMENT, compass: LINK }, { "GET /api/engagements/e1/comparisons": () => ({ body: asSide("reference") }) });
    renderApp(PATH);
    const card = (await screen.findByRole("heading", { name: "Capability Compass return file" })).closest(".card") as HTMLElement;
    expect(
      await within(card).findByText(
        "Arden is the reference in its comparison with Belmar, so those differences are in Belmar's return file.",
      ),
    ).toBeInTheDocument();
  });

  it("names every country it is the reference for", () => {
    const with_ = (country: string): ComparisonSummary => ({
      ...SUMMARY,
      reference: { ...SUMMARY.reference, engagement_id: "e1" },
      other: { ...SUMMARY.other, country },
    });
    expect(referenceNote("e1", [with_("Belmar"), with_("Corland")])).toBe(
      "Arden is the reference in its comparisons with Belmar and Corland, so those differences are in Belmar's and Corland's return files.",
    );
    expect(referenceNote("e1", [])).toBeNull();
  });

  it("says nothing more for the country whose file carries the differences", async () => {
    backend({ ...ENGAGEMENT, compass: LINK }, { "GET /api/engagements/e1/comparisons": () => ({ body: asSide("other") }) });
    renderApp(PATH);
    const card = (await screen.findByRole("heading", { name: "Capability Compass return file" })).closest(".card") as HTMLElement;
    await within(card).findByRole("link", { name: /Download JSON/ });
    expect(within(card).queryByText(/is the reference in its comparison/)).toBeNull();
  });

  it("is not shown for an engagement made without a hand-off, and the other downloads are", async () => {
    backend(ENGAGEMENT);
    renderApp(PATH);
    expect(await screen.findAllByRole("link", { name: /^Download/ })).not.toHaveLength(0);
    expect(screen.queryByRole("heading", { name: "Capability Compass return file" })).toBeNull();
  });
});

describe("suggested probes beside an interview guide", () => {
  const guide = (probes?: string[]): GuideView => ({
    id: "g1",
    engagement_id: "e1",
    profile_id: "p1",
    interview_type: "practice",
    version: 1,
    edited: false,
    created_at: "2026-11-10T09:00:00+00:00",
    document: { kind: "practice", title: "Practice interview guide: Ramp agent · Ramp", minutes: 60, generation_note: "", tables: [] },
    ...(probes ? { suggested_probes: probes } : {}),
  });
  const props = { busy: false, error: null, saved: false, onSave: vi.fn(), onClose: vi.fn() };

  it("lists the hand-off's prompts, labelled as prompts and not as evidence", async () => {
    const probes = LINK.interview_prompts;
    expect(probes.length).toBeGreaterThan(0);
    const { container } = render(<GuideEditor guide={guide(probes)} {...props} />);
    const section = screen.getByRole("region", { name: "Suggested probes from Capability Compass" });
    expect(within(section).getAllByRole("listitem").map((li) => li.textContent)).toEqual(probes);
    expect(within(section).getByText(/Prompts only.*nothing here\s+is evidence/s)).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("shows nothing for a guide of an engagement made without a hand-off", () => {
    render(<GuideEditor guide={guide()} {...props} />);
    expect(screen.queryByText("Suggested probes from Capability Compass")).toBeNull();
    cleanup();
    render(<GuideEditor guide={guide([])} {...props} />);
    expect(screen.queryByText("Suggested probes from Capability Compass")).toBeNull();
  });
});
