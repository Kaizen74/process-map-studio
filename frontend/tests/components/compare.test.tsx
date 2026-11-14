import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Candidate, Comparison, ComparisonSummary } from "../../src/lib/comparisons";
import { seriousViolations } from "../axe";
import sample from "../fixtures/comparison_sample.json";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp, type Handler } from "../renderApp";

// Compare countries (2026-11-13, Eric's brief §4.3-4.5; DECISIONS 98), on the backend's own output.
afterEach(() => vi.unstubAllGlobals());

const CANDIDATES = sample.candidates as Candidate[];
const VIEW = sample.comparison as Comparison;
const LIST = sample.comparisons as ComparisonSummary[];
const BELMAR = { ...ENGAGEMENT, id: "id-4", name: VIEW.other.name, country: "Belmar" };
const PATH = `/engagements/id-4/compare`;

function backend(extra: Record<string, Handler> = {}) {
  return fakeApi({
    "GET /api/settings": () => ({ body: SETTINGS }),
    "GET /api/engagements/id-4": () => ({ body: BELMAR }),
    "GET /api/engagements/id-4/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/id-4/comparison-candidates": () => ({ body: CANDIDATES }),
    "GET /api/engagements/id-4/comparisons": () => ({ body: LIST }),
    "GET /api/comparisons/id-3": () => ({ body: VIEW }),
    "PUT /api/comparisons/id-3/pairs": () => ({ body: VIEW }),
    ...extra,
  });
}

function rowOf(title: string): HTMLElement {
  const rows = [...document.querySelectorAll<HTMLElement>("li.difference")];
  const row = rows.find((li) => li.querySelector(".difference__title")?.textContent?.endsWith(title));
  if (!row) throw new Error(`No difference titled ${title}`);
  return row;
}

describe("Compare countries", () => {
  it("lists the pairs in process order, each code with its country, and slims the buttons once decided", async () => {
    backend();
    renderApp(`${PATH}?comparison=id-3`);
    const table = await screen.findByRole("table", { name: "Step pairs between Arden and Belmar" });
    const rows = within(table).getAllByRole("row").slice(1);
    // Eric, 2026-11-13: process order, not the order the pairs were confirmed in.
    expect(rows.map((r) => r.querySelector("td")?.textContent)).toEqual([
      "Arden S-01 Receive the renewal request",
      "Arden S-02 Build the bid solution",
      "Arden S-03 Draft the renewal price",
      "Arden S-04 Approve the renewal price",
      "Not in Arden",
      "Arden S-05 Legal review of terms",
      "Arden S-06 Send the renewal offer",
    ]);
    // The same code names different steps in each country, so the country is always shown.
    const credit = rows[4] as HTMLElement;
    expect(within(credit).getByText("Belmar S-05 Check the credit limit")).toBeInTheDocument();
    // A decided pair offers only Clear and Choose another step.
    const approve = rows[3] as HTMLElement;
    expect(within(approve).queryByRole("button", { name: /^Only in/ })).toBeNull();
    expect(within(approve).getByRole("button", { name: /^Clear/ })).toBeInTheDocument();
    expect(within(approve).getByLabelText("Pair Arden S-04 Approve the renewal price with")).toBeInTheDocument();
    expect(within(credit).queryByRole("button", { name: /^Only in/ })).toBeNull();
  });

  it("an undecided proposal still offers Confirm and Only in each country", async () => {
    const proposed = {
      ...VIEW,
      pairs: VIEW.pairs.map((p, i) => (i === 0 ? { ...p, status: "proposed" as const } : p)),
    };
    backend({ "GET /api/comparisons/id-3": () => ({ body: proposed }) });
    renderApp(`${PATH}?comparison=id-3`);
    const table = await screen.findByRole("table", { name: "Step pairs between Arden and Belmar" });
    const first = within(table).getAllByRole("row")[1] as HTMLElement;
    for (const name of [/^Confirm/, /^Only in Arden/, /^Only in Belmar/]) {
      expect(within(first).getByRole("button", { name })).toBeInTheDocument();
    }
    expect(within(first).queryByRole("button", { name: /^Clear/ })).toBeNull();
  });

  it("offers only the same process, published, and starts the comparison with Belmar compared with Arden", async () => {
    const { calls } = backend({ "POST /api/comparisons": () => ({ status: 201, body: VIEW }) });
    const { container } = renderApp(PATH);
    const chooser = (await screen.findByRole("heading", { name: "Choose the two maps" })).closest(".card") as HTMLElement;
    expect(within(chooser).getByLabelText("Compare with")).toHaveDisplayValue(
      "Arden · MERIDIAN VS-01 Bid to contract renewal (this map started from it)",
    );
    fireEvent.click(within(chooser).getByRole("button", { name: "Compare" }));
    expect(await screen.findByRole("heading", { name: "Arden and Belmar" })).toBeInTheDocument();
    expect(calls.find((c) => c.key === "POST /api/comparisons")?.body).toEqual({
      reference_engagement_id: "id-1",
      other_engagement_id: "id-4",
    });
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("says there is nothing to compare yet and where to start", async () => {
    backend({ "GET /api/engagements/id-4/comparison-candidates": () => ({ body: [] }) });
    renderApp(PATH);
    expect(await screen.findByText(/No other country maps this process yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Setup" })).toHaveAttribute("href", "/engagements/id-4/setup");
  });

  // Eric, 2026-11-14: the reference choice starts on the country the other map began from (or
  // the existing comparison's reference), on either country's screen.
  const reference = async () => {
    const field = (await screen.findByLabelText("Reference country")) as HTMLSelectElement;
    return field.selectedOptions[0]?.textContent ?? "";
  };
  const ARDEN = { ...ENGAGEMENT, id: "id-4", name: VIEW.reference.name, country: "Arden" };
  const BELMAR_CANDIDATE: Candidate = {
    ...(CANDIDATES[0] as Candidate),
    engagement_id: "id-9",
    name: VIEW.other.name,
    country: "Belmar",
    why: "started from this map",
  };

  it("starts the reference on Arden on Belmar's screen", async () => {
    backend({ "GET /api/engagements/id-4/comparisons": () => ({ body: [] }) });
    renderApp(PATH);
    expect(await reference()).toBe(`Arden · ${VIEW.reference.name}`);
  });

  it("starts the reference on Arden on Arden's screen too", async () => {
    backend({
      "GET /api/engagements/id-4": () => ({ body: ARDEN }),
      "GET /api/engagements/id-4/comparison-candidates": () => ({ body: [BELMAR_CANDIDATE] }),
      "GET /api/engagements/id-4/comparisons": () => ({ body: [] }),
    });
    renderApp(PATH);
    expect(await reference()).toBe(`Arden · ${VIEW.reference.name}`);
  });

  it("follows the existing comparison when there is one", async () => {
    const existing = {
      ...(LIST[0] as ComparisonSummary),
      reference: { ...(LIST[0] as ComparisonSummary).other, engagement_id: "id-9", country: "Belmar" },
      other: { ...(LIST[0] as ComparisonSummary).reference, engagement_id: "id-4", country: "Arden" },
    };
    backend({
      "GET /api/engagements/id-4": () => ({ body: ARDEN }),
      "GET /api/engagements/id-4/comparison-candidates": () => ({ body: [BELMAR_CANDIDATE] }),
      "GET /api/engagements/id-4/comparisons": () => ({ body: [existing] }),
    });
    renderApp(PATH);
    await screen.findByRole("heading", { name: "Comparisons of this map" });
    expect(await reference()).toBe(`Belmar · ${VIEW.other.name}`);
  });

  it("keeps Eric's own choice of reference", async () => {
    backend({ "GET /api/engagements/id-4/comparisons": () => ({ body: [] }) });
    renderApp(PATH);
    fireEvent.change(await screen.findByLabelText("Reference country"), { target: { value: "us" } });
    expect(await reference()).toBe(`Belmar · ${BELMAR.name}`);
  });

  it("says which map started from which, by country", async () => {
    backend();
    renderApp(`${PATH}?comparison=id-3`);
    expect(
      await screen.findByText("Arden v1.0 is the reference; Belmar v1.0 is compared with it (Belmar's map started from Arden's)."),
    ).toBeInTheDocument();
  });

  it("counts every status in the list of comparisons, dismissed included", async () => {
    // Eric, 2026-11-14: the list line matches the comparison card's counts.
    backend();
    renderApp(PATH);
    const list = await screen.findByRole("heading", { name: "Comparisons of this map" });
    const card = list.closest("section") ?? document.body;
    const d = LIST[0]?.differences;
    expect(within(card as HTMLElement).getByText(/\(reference\) and Belmar/)).toHaveTextContent(
      `Arden v1.0 (reference) and Belmar v1.0: ${d?.open} not classed yet, ${d?.classed} classed, ${d?.kept} kept, ${d?.dismissed} dismissed`,
    );
  });

  it("shows the pairs with their reasons and sends Eric's decisions", async () => {
    const { calls } = backend();
    const { container } = renderApp(`${PATH}?comparison=id-3`);
    const table = await screen.findByRole("table", { name: "Step pairs between Arden and Belmar" });
    expect(within(table).getAllByText("Confirmed").length).toBeGreaterThan(0);
    const legal = within(table).getByText("Arden S-05 Legal review of terms").closest("tr") as HTMLElement;
    expect(within(legal).getByText("Not in Belmar")).toBeInTheDocument();
    fireEvent.click(within(legal).getByRole("button", { name: /Clear/ }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "PUT /api/comparisons/id-3/pairs")).toBe(true));
    expect(calls.find((c) => c.key === "PUT /api/comparisons/id-3/pairs")?.body).toEqual({
      reference_key: "legal-review-of-terms",
      other_key: null,
      decision: "clear",
    });
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("lists each difference with both values, its code and grade, and classes it in Eric's words", async () => {
    const open = VIEW.differences.find((d) => d.status === "open");
    expect(open).toBeDefined();
    const { calls } = backend({
      [`PUT /api/comparisons/id-3/differences/${encodeURIComponent(open?.key ?? "")}`]: () => ({ body: open }),
    });
    renderApp(`${PATH}?comparison=id-3`);
    const classed = VIEW.differences.find((d) => d.code === "V1");
    await screen.findByRole("heading", { name: "Differences" });
    expect(rowOf(classed?.title ?? "")).toHaveTextContent(`V1 ${classed?.title ?? ""}`);
    expect(screen.getByText("Reason: Inherited (Belmar kept its pre-merger delegation.)")).toBeInTheDocument();
    expect(screen.getByText("60 min in Belmar vs 120 min in Arden (stated)")).toBeInTheDocument();
    const row = rowOf(open?.title ?? "");
    expect(within(row).getByText("Not classed yet")).toBeInTheDocument();
    expect(within(row).getByText(/^Grade: /)).toBeInTheDocument();
    fireEvent.click(within(row).getByRole("button", { name: /^Class/ }));
    fireEvent.click(within(row).getByRole("radio", { name: /^Chosen:/ }));
    fireEvent.change(within(row).getByLabelText("One line of reason"), { target: { value: "Agreed locally." } });
    fireEvent.click(within(row).getByRole("button", { name: "Save the reason" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key.startsWith("PUT /api/comparisons/id-3/differences/"))).toBe(true));
    const sent = calls.find((c) => c.key.startsWith("PUT /api/comparisons/id-3/differences/"));
    expect(sent?.body).toEqual({ action: "class", reason_class: "chosen", reason_note: "Agreed locally." });
  });

  it("updates the list of comparisons after a difference is classed or a pair changes", async () => {
    // Eric, 2026-11-14: the list line keeps up with the comparison card, with no reload.
    const open = VIEW.differences.find((d) => d.status === "open");
    const before = LIST[0] as ComparisonSummary;
    let decided = 0;
    const after = (): ComparisonSummary => ({
      ...before,
      differences: { ...before.differences, open: before.differences.open - decided, classed: before.differences.classed + decided },
    });
    backend({
      "GET /api/engagements/id-4/comparisons": () => ({ body: [after()] }),
      [`PUT /api/comparisons/id-3/differences/${encodeURIComponent(open?.key ?? "")}`]: () => {
        decided = 1;
        return { body: open };
      },
      "PUT /api/comparisons/id-3/pairs": () => {
        decided = 2;
        return { body: VIEW };
      },
    });
    renderApp(`${PATH}?comparison=id-3`);
    const line = async (n: number) =>
      screen.findByText(
        new RegExp(`: ${before.differences.open - n} not classed yet, ${before.differences.classed + n} classed,`),
      );
    await line(0);
    await screen.findByRole("heading", { name: "Differences" });
    const row = rowOf(open?.title ?? "");
    fireEvent.click(within(row).getByRole("button", { name: /^Class/ }));
    fireEvent.click(within(row).getByRole("radio", { name: /^Chosen:/ }));
    fireEvent.change(within(row).getByLabelText("One line of reason"), { target: { value: "Agreed locally." } });
    fireEvent.click(within(row).getByRole("button", { name: "Save the reason" }));
    expect(await line(1)).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Step pairs between Arden and Belmar" });
    fireEvent.click(within(table).getAllByRole("button", { name: /^Clear/ })[0] as HTMLElement);
    expect(await line(2)).toBeInTheDocument();
  });

  it("says when a newer version exists and refreshes keeping the decisions", async () => {
    const stale: Comparison = { ...VIEW, other: { ...VIEW.other, newer_version_label: "v2.0" } };
    const { calls } = backend({
      "GET /api/comparisons/id-3": () => ({ body: stale }),
      "POST /api/comparisons/id-3/refresh": () => ({ body: VIEW }),
    });
    renderApp(`${PATH}?comparison=id-3`);
    const note = await screen.findByRole("note");
    expect(note).toHaveTextContent("A newer version exists: Belmar v2.0. Refresh to compare it; your pairs and classes are kept.");
    fireEvent.click(within(note).getByRole("button", { name: "Refresh" }));
    await vi.waitFor(() => expect(calls.some((c) => c.key === "POST /api/comparisons/id-3/refresh")).toBe(true));
  });
});
