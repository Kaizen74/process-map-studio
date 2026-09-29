import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { QualityCard, VersionDetail, VersionSummary } from "../../src/lib/reviewTypes";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp, type Handler } from "../renderApp";

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

const version = (id: string, label: string, state: string, at: string): VersionSummary => ({
  id,
  engagement_id: "e1",
  label,
  state,
  created_at: at,
  published_at: state === "draft" ? null : at,
  published_by: state === "draft" ? null : "Eric",
  parent_version_id: null,
});

function backend(versions: VersionSummary[], analyses: Record<string, unknown[]> = {}) {
  const routes: Record<string, Handler> = {
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/versions": () => ({ body: versions }),
  };
  for (const v of versions) {
    const detail: VersionDetail = { ...v, review: { reviewed: 8, total: 8 }, change_log: [], quality_card: GREEN };
    routes[`GET /api/versions/${v.id}`] = () => ({ body: detail });
    routes[`GET /api/versions/${v.id}/gap-analyses`] = () => ({ body: analyses[v.id] ?? [] });
  }
  return fakeApi(routes);
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe("the Exports screen (PRD §5.4, §7.3)", () => {
  it("explains that exports need a published version with a green card", async () => {
    backend([version("d1", "v0.1", "draft", "2026-09-28T08:00:00+00:00")]);
    renderApp(PATH);
    expect(
      await screen.findByText(/Publish a version with a green quality card first. Exports are made from published versions only./),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Review" })).toHaveAttribute("href", "/engagements/e1/review");
    expect(screen.queryByRole("link", { name: /Download/ })).toBeNull();
  });

  it("offers the four exports of the published version, each saying what it leaves out", async () => {
    backend([version("p2", "v1.1", "published", "2026-09-28T10:00:00+00:00"), version("p1", "v1.0", "superseded", "2026-09-27T10:00:00+00:00")]);
    renderApp(PATH);
    const md = await screen.findByRole("link", { name: "Download Master Process Map (.md) of v1.1" });
    expect(md).toHaveAttribute("href", "/api/versions/p2/export/md");
    expect(md).toHaveAttribute("download");
    for (const [name, fmt] of [["Graph (.json)", "json"], ["RACI (.csv)", "csv"], ["Interactive map (.html)", "html"]]) {
      expect(screen.getByRole("link", { name: `Download ${name} of v1.1` })).toHaveAttribute("href", `/api/versions/p2/export/${fmt}`);
    }
    expect(screen.getAllByText("No images, verbatim quotes or names.")).toHaveLength(4);
    expect((await screen.findAllByText(/Quality card: 9 of 9 green/)).length).toBe(4);
    const gap = screen.getByRole("region", { name: "Gap analysis reports" });
    expect(await within(gap).findByText(/No finalised reports for v1.1 yet./)).toBeInTheDocument();
    expect(within(gap).getByRole("link", { name: "Go to Gap analysis" })).toHaveAttribute(
      "href",
      "/engagements/e1/gap-analysis",
    );
    expect(await seriousViolations(document.body)).toEqual([]);
  });

  it("shows the version's signal strength with what it means (P12)", async () => {
    const signal = {
      level: "limited" as const,
      label: "Limited",
      score: 1,
      detail: "Built from interviews only. Every step is 'practiced only': confirm it with a document or another SME before relying on it.",
    };
    backend([{ ...version("p2", "v1.1", "published", "2026-09-28T10:00:00+00:00"), signal }]);
    const { container } = renderApp(PATH);
    await screen.findByRole("link", { name: "Download Master Process Map (.md) of v1.1" });
    const meter = container.querySelector(".exports__signal");
    expect(meter).toHaveTextContent("Signal strength: Limited (1 of 3)");
    expect(meter).toHaveTextContent(/Built from interviews only/);
    expect(await seriousViolations(document.body)).toEqual([]);
  });

  it("lists the version's finalised gap analysis reports with Download .md (P10)", async () => {
    const report = (id: string, mode: string, status: string) => ({
      id, version_id: "p2", version_label: "v1.1", mode, status, job_id: null, error: "",
      created_at: "2026-09-28T10:00:00+00:00", completed_at: "2026-09-28T10:01:00+00:00",
      finalised_at: status === "finalised" ? "2026-09-28T11:00:00+00:00" : null, notes: [],
      counts: { kept: 4, rejected: 0, open: 0, needs_check: 0 },
    }); // prettier-ignore
    backend([version("p2", "v1.1", "published", "2026-09-28T10:00:00+00:00")], {
      p2: [report("g2", "external", "draft_report"), report("g1", "internal", "finalised")],
    });
    renderApp(PATH);
    const link = await screen.findByRole("link", { name: /^Download \.md\s*Documents vs practice report of v1\.1$/ });
    expect(link).toHaveAttribute("href", "/api/gap-analyses/g1/export");
    const gap = screen.getByRole("region", { name: "Gap analysis reports" });
    expect(within(gap).queryByText(/External best practice/)).toBeNull(); // not finalised
  });

  it("can export an earlier, superseded version", async () => {
    backend([version("p2", "v1.1", "published", "2026-09-28T10:00:00+00:00"), version("p1", "v1.0", "superseded", "2026-09-27T10:00:00+00:00")]);
    renderApp(PATH);
    fireEvent.change(await screen.findByLabelText("Version"), { target: { value: "p1" } });
    expect(await screen.findByRole("link", { name: "Download RACI (.csv) of v1.0" })).toHaveAttribute(
      "href",
      "/api/versions/p1/export/csv",
    );
  });
});
