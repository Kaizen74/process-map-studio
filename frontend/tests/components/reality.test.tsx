import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DiscrepanciesSection } from "../../src/components/reality";
import type { BeliefView, IntentStatement, RealityFigures, RealitySnapshot } from "../../src/lib/reality";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

// The A.12 snapshot as the backend sends it (backend/tests/unit/test_reality_api.py).
const REALITY = JSON.parse(readFileSync(join(__dirname, "..", "fixtures", "reality.json"), "utf-8")) as {
  snapshot: RealitySnapshot;
  decided: RealitySnapshot;
  intent: IntentStatement[];
  leadership_reality: RealityFigures;
  belief_view: BeliefView;
};
const SNAP = REALITY.snapshot;
const VID = SNAP.version_id;

const DRAFT = {
  id: VID,
  engagement_id: "e1",
  label: "v1.0 draft",
  state: "draft",
  created_at: "2026-10-14T09:00:00+00:00",
  published_at: null,
  published_by: null,
  parent_version_id: null,
};

function backend(snapshot: RealitySnapshot = SNAP, versions: unknown[] = [DRAFT]) {
  return fakeApi({
    "GET /api/settings": () => ({ body: { ...SETTINGS, reality_views_enabled: true } }),
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/versions": () => ({ body: versions }),
    "GET /api/engagements/e1/roles": () => ({
      body: [{ id: "lead", engagement_id: "e1", name: "Load control lead", aliases: [], is_system: false, lane_order: 0 }],
    }),
    [`GET /api/versions/${VID}/reality`]: () => ({ body: snapshot }),
    "GET /api/engagements/e1/intent": () => ({ body: REALITY.intent }),
    ...Object.fromEntries(
      REALITY.intent.map((i) => [`PATCH /api/intent/${i.id}`, (body: unknown) => ({ body: { ...i, ...(body as object) } })]),
    ),
    "POST /api/engagements/e1/intent": (body) => ({ status: 201, body }),
    "POST /api/engagements/e1/intent/extract": () => ({ status: 202, body: { job_id: "j1", engagement_id: "e1" } }),
    "GET /api/jobs/j1": () => ({
      body: { id: "j1", status: "done", message: "2 statements proposed from the charter.", error: "" },
    }),
  });
}

const path = (query = "") => `/engagements/e1/reality${query}`;

describe("Reality screen (PRD §5.12, P13b)", () => {
  it("opens on Glance: the question, the computed headline, the tiles and the legend", async () => {
    backend();
    const { container } = renderApp(path());
    expect(await screen.findByRole("heading", { name: SNAP.views.rv1.title })).toBeInTheDocument();
    expect(screen.getByText(SNAP.views.rv1.headline)).toBeInTheDocument();
    for (const tile of SNAP.tiles) expect(screen.getAllByText(tile.figure.text).length).toBeGreaterThan(0);
    expect(screen.getByRole("note")).toHaveTextContent("Draft: figures may change");
    const legend = screen.getByRole("contentinfo", { name: "Legend" });
    for (const word of ["Control exposure", "Time impact", "Capacity drain", "Workaround"]) {
      expect(within(legend).getByText(word)).toBeInTheDocument();
    }
    expect(legend).toHaveTextContent(SNAP.evidence.text);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("switches views, each with its own question and headline, and shows each as a table", async () => {
    backend();
    renderApp(path());
    await screen.findByText(SNAP.views.rv1.headline);
    fireEvent.click(screen.getByRole("radio", { name: "Reality stack" }));
    expect(await screen.findByRole("heading", { name: SNAP.views.rv2.title })).toBeInTheDocument();
    expect(screen.getByText(SNAP.views.rv2.headline)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show as table" }));
    const table = screen.getByRole("table", { name: SNAP.views.rv2.title });
    for (const band of SNAP.views.rv2.table.rows) expect(within(table).getByText(band[0] ?? "")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Fix or keep" }));
    expect(await screen.findByText(SNAP.views.rv3.headline)).toBeInTheDocument();
    const decide = screen.getByRole("region", { name: "Decide first" });
    const rows = within(decide).getAllByRole("listitem");
    expect(rows).toHaveLength(SNAP.views.rv3.fix.limit);
    expect(rows[0]).toHaveTextContent(SNAP.views.rv3.fix.decide_first[0] ?? "");
    fireEvent.click(within(decide).getByRole("button", { name: /Show all/ }));
    expect(within(decide).getAllByRole("listitem")).toHaveLength(SNAP.views.rv3.fix.decide_first.length);
  });

  it("selecting an X code highlights it everywhere and dims the rest; Esc clears it", async () => {
    backend();
    renderApp(path("?view=rv3"));
    const decide = await screen.findByRole("region", { name: "Decide first" });
    const [first] = SNAP.views.rv3.fix.decide_first;
    fireEvent.click(within(decide).getByRole("button", { name: new RegExp(`^${first} `) }));
    const badges = screen.getByRole("list", { name: "Codes on this view" });
    expect(within(badges).getByRole("button", { name: new RegExp(`^${first} `) })).toHaveAttribute("aria-pressed", "true");
    const dimmed = within(badges)
      .getAllByRole("listitem")
      .filter((li) => li.classList.contains("is-dimmed"));
    expect(dimmed.length).toBe(within(badges).getAllByRole("listitem").length - 1);
    const card = screen.getByRole("region", { name: "Discrepancies" });
    expect(within(card).getByRole("button", { name: new RegExp(`^${first} `) })).toHaveAttribute("aria-pressed", "true");
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() =>
      expect(within(badges).getByRole("button", { name: new RegExp(`^${first} `) })).toHaveAttribute(
        "aria-pressed",
        "false",
      ),
    );
  });

  it("a verdict needs a note; the change is sent with it", async () => {
    const api = backend();
    renderApp(path());
    const card = await screen.findByRole("region", { name: "Discrepancies" });
    const row = within(card).getAllByRole("listitem")[0];
    if (!row) throw new Error("a row per code");
    fireEvent.click(within(row).getByRole("button", { name: /Change/ }));
    fireEvent.click(within(row).getByRole("button", { name: "Save verdict" }));
    expect(within(row).getByText("Add a note saying why: it is kept with your verdict.")).toBeInTheDocument();
    expect(api.calls.some((c) => c.key.startsWith("PUT /api/discrepancy-items/"))).toBe(false);
    fireEvent.change(within(row).getByLabelText("Note (why)"), { target: { value: "Keeps the slot." } });
    fireEvent.change(within(row).getByLabelText("Verdict"), { target: { value: "codify" } });
    fireEvent.click(within(row).getByRole("button", { name: "Save verdict" }));
    await waitFor(() => expect(api.calls.some((c) => c.key.startsWith("PUT /api/discrepancy-items/"))).toBe(true));
    const sent = api.calls.find((c) => c.key.startsWith("PUT /api/discrepancy-items/"));
    expect(sent?.key).toBe(`PUT /api/discrepancy-items/${SNAP.codes[0]?.item_id ?? ""}/verdict`);
    expect(sent?.body).toEqual({ verdict: "codify", note: "Keeps the slot." });
  });

  it("a published version's verdicts were frozen with it: no verdict actions", async () => {
    const published = { ...DRAFT, label: "v1.0", state: "published", published_at: "2026-10-14T10:00:00+00:00" };
    backend({ ...SNAP, draft: false, frozen: true, data_label: "Version v1.0, validated by Owner on 2026-10-14" }, [
      published,
    ]);
    renderApp(path());
    const card = await screen.findByRole("region", { name: "Discrepancies" });
    expect(card).toHaveTextContent("Verdicts were frozen when this version was published.");
    expect(within(card).queryByRole("button", { name: /Confirm verdict|Change/ })).toBeNull();
    expect(screen.queryByRole("note")).toBeNull(); // no draft banner
  });

  it("without a map, explains what is missing and links to Draft", async () => {
    backend(SNAP, []);
    const { container } = renderApp(path());
    expect(await screen.findByText(/There is no map yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Draft" })).toHaveAttribute("href", "/engagements/e1/draft");
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("Reality screen II: Redline, time, belief and typical case (PRD §5.12.3, P13c)", () => {
  /** The words of every text shape a view's geometry holds, as the canvas draws them. */
  const shapeText = (svg: Element) => [...svg.querySelectorAll("tspan")].map((t) => t.textContent ?? "");

  it("the switcher offers all seven views in reading order", async () => {
    backend();
    renderApp(path());
    await screen.findByText(SNAP.views.rv1.headline);
    const switcher = screen.getByRole("radiogroup", { name: "Reality view" });
    expect(within(switcher).getAllByRole("radio").map((r) => r.textContent)).toEqual([
      "Glance",
      "Reality stack",
      "Fix or keep",
      "Redline",
      "Where the time goes",
      "Belief vs evidence",
      "Typical case",
    ]);
  });

  it.each(["rv4", "rv5", "rv6", "rv7"] as const)(
    "%s draws the backend's shapes with its question, headline and table, accessibly",
    async (id) => {
      backend();
      const { container } = renderApp(path(`?view=${id}`));
      const view = SNAP.views[id];
      expect(await screen.findByRole("heading", { name: view.title })).toBeInTheDocument();
      expect(screen.getByText(view.headline)).toBeInTheDocument();
      const svg = container.querySelector("svg.reality-canvas");
      if (!svg) throw new Error("the view's canvas");
      expect(svg.getAttribute("viewBox")).toBe(`0 0 ${view.geometry.width} ${view.geometry.height}`);
      expect(svg.querySelectorAll("[data-role]")).toHaveLength(view.geometry.shapes.length);
      const words = view.geometry.shapes.filter((x) => x.kind === "text").flatMap((x) => x.lines);
      expect(shapeText(svg)).toEqual(words); // every word on the canvas is the backend's
      fireEvent.click(screen.getByRole("button", { name: "Show as table" }));
      const table = screen.getByRole("table", { name: view.title });
      expect(within(table).getAllByRole("row")).toHaveLength(view.table.rows.length + 1);
      expect(await seriousViolations(container)).toEqual([]);
    },
  );

  it("the Redline lists the markups not drawn and its codes as badges", async () => {
    backend();
    const { container } = renderApp(path("?view=rv4"));
    await screen.findByText(SNAP.views.rv4.headline);
    const svg = container.querySelector("svg.reality-canvas");
    if (!svg) throw new Error("the Redline canvas");
    for (const code of SNAP.views.rv4.redline.listed) {
      expect(shapeText(svg).some((t) => t.startsWith(`${code} `))).toBe(true);
    }
    const ghosts = svg.querySelectorAll('[data-role="step-ghost"]');
    expect(ghosts.length).toBe(SNAP.views.rv4.redline.steps.filter((x) => x.ghost).length);
    const badges = screen.getByRole("list", { name: "Codes on this view" });
    const codes = [...new Set(SNAP.views.rv4.redline.markups.map((m) => m.code))];
    expect(within(badges).getAllByRole("listitem")).toHaveLength(codes.length);
  });

  it("selecting a code dims the other codes' shapes", async () => {
    backend();
    const { container } = renderApp(path("?view=rv4&code=X1"));
    await screen.findByText(SNAP.views.rv4.headline);
    const coded = [...container.querySelectorAll("svg.reality-canvas [data-role]")].filter((_, i) =>
      Boolean(SNAP.views.rv4.geometry.shapes[i]?.code),
    );
    const others = SNAP.views.rv4.geometry.shapes.filter((x) => x.code && x.code !== "X1").length;
    expect(coded.filter((g) => g.classList.contains("is-dimmed"))).toHaveLength(others);
  });

  it("Where the time goes says it is incomplete and why", async () => {
    backend();
    renderApp(path("?view=rv5"));
    await screen.findByText(SNAP.views.rv5.headline);
    expect(screen.getByText(SNAP.views.rv5.availability.message)).toBeInTheDocument();
  });

  it("Belief vs evidence without a gap says what it needs; with one it shows the neutral note", async () => {
    backend();
    renderApp(path("?view=rv6"));
    await screen.findByText(SNAP.views.rv6.headline);
    expect(screen.getByText(SNAP.views.rv6.availability.message)).toBeInTheDocument();
    const belief = REALITY.belief_view;
    backend({ ...SNAP, views: { ...SNAP.views, rv6: belief } });
    const { container } = renderApp(path("?view=rv6"));
    await screen.findAllByText(belief.headline);
    const svg = container.querySelector("svg.reality-canvas");
    if (!svg) throw new Error("the belief canvas");
    const words = shapeText(svg);
    expect(words).toContain("A visibility gap, not a competence gap.");
    expect(words).toContain(belief.belief.rows[0]?.gap.text);
    expect(words).toContain(belief.belief.rows[0]?.prevalence);
  });

  it("the Typical case is labelled a composite and shows its answer tiles", async () => {
    backend();
    renderApp(path("?view=rv7"));
    const c = SNAP.views.rv7.case;
    expect(await screen.findByText(c.label)).toBeInTheDocument();
    for (const t of c.tiles) expect(screen.getByText(t.caption)).toBeInTheDocument();
    expect(c.cases).toBeGreaterThanOrEqual(5);
  });

  it("without a route of 5 cases the Typical case draws nothing and links to System records", async () => {
    const missing = {
      ...SNAP.views.rv7,
      case: { ...SNAP.views.rv7.case, events: [], lanes: [], tiles: [], cases: 0, label: "" },
      geometry: { ...SNAP.views.rv7.geometry, shapes: [] },
      availability: { state: "missing" as const, message: "A typical case needs a system log.", action: "import_log" as const },
    };
    backend({ ...SNAP, views: { ...SNAP.views, rv7: missing } });
    const { container } = renderApp(path("?view=rv7"));
    expect(await screen.findByText("A typical case needs a system log.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Import a system log on System records" })).toBeInTheDocument();
    expect(container.querySelector("svg.reality-canvas")).toBeNull();
  });
});

describe("The Intent card (constraint 25)", () => {
  it("lists statements by status, confirms one and finds intent in documents", async () => {
    const { calls } = backend();
    renderApp(path());
    const card = await screen.findByRole("region", { name: "Intent" });
    const confirmed = REALITY.intent.filter((i) => i.status === "confirmed");
    const rejected = REALITY.intent.filter((i) => i.verification_status === "rejected");
    expect(await within(card).findByRole("region", { name: "Confirmed" })).toBeInTheDocument();
    for (const s of confirmed) expect(within(card).getByText(s.text)).toBeInTheDocument();
    // A proposal the checks rejected is never offered for confirmation (G16).
    expect(rejected.length).toBeGreaterThan(0);
    for (const s of rejected) expect(within(card).queryByText(s.text)).toBeNull();
    const first = confirmed[0];
    if (!first) throw new Error("the sample has a confirmed statement");
    fireEvent.click(within(card).getByRole("button", { name: `Dismiss “${first.text}”` }));
    await waitFor(() => expect(calls.some((c) => c.key === `PATCH /api/intent/${first.id}`)).toBe(true));
    expect(calls.find((c) => c.key === `PATCH /api/intent/${first.id}`)?.body).toEqual({ status: "dismissed" });
    fireEvent.click(within(card).getByRole("button", { name: "Find intent in documents" }));
    expect(await within(card).findByText("2 statements proposed from the charter.")).toBeInTheDocument();
  });

  it("adds an owner-stated target with its role and date", async () => {
    const { calls } = backend();
    renderApp(path());
    const card = await screen.findByRole("region", { name: "Intent" });
    fireEvent.click(within(card).getByRole("button", { name: "Add a target" }));
    fireEvent.change(within(card).getByLabelText("Target, in the owner's words"), {
      target: { value: "A flight is closed out in 60 minutes." },
    });
    fireEvent.change(within(card).getByLabelText("Value"), { target: { value: "60" } });
    fireEvent.change(within(card).getByLabelText("Owner's role"), { target: { value: "lead" } });
    fireEvent.change(within(card).getByLabelText("Stated on (YYYY-MM-DD)"), { target: { value: "2026-10-01" } });
    fireEvent.click(within(card).getByRole("button", { name: "Save target" }));
    await waitFor(() => expect(calls.some((c) => c.key === "POST /api/engagements/e1/intent")).toBe(true));
    expect(calls.find((c) => c.key === "POST /api/engagements/e1/intent")?.body).toEqual({
      scope: "process",
      kind: "target",
      text: "A flight is closed out in 60 minutes.",
      metric: "cycle_time_min",
      comparator: "at_most",
      target_value: 60,
      unit: "min",
      owner_role_id: "lead",
      stated_on: "2026-10-01",
    });
  });
});

describe("Panel section 12, Discrepancies", () => {
  it("lists the step's codes from the snapshot with a link to the Reality screen", () => {
    const x1 = SNAP.codes.find((c) => c.code === "X1");
    if (!x1) throw new Error("X1 in the sample");
    render(
      <MemoryRouter>
        <DiscrepanciesSection
          codes={[x1]}
          intents={SNAP.intents.filter((i) => i.step_keys.includes(x1.location.keys[0] ?? ""))}
          linkFor={(code) => `/engagements/e1/reality?code=${code}`}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(x1.impact_word)).toBeInTheDocument();
    expect(screen.getByText(/Verdict: Correct \(suggested\)/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open on the Reality screen/ })).toHaveAttribute(
      "href",
      "/engagements/e1/reality?code=X1",
    );
    expect(screen.getByText(/Every load plan is approved/)).toBeInTheDocument();
  });

  it("shows nothing for a step without codes or intent", () => {
    const { container } = render(
      <MemoryRouter>
        <DiscrepanciesSection codes={[]} intents={[]} linkFor={() => ""} />
      </MemoryRouter>,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Reality in the engagement nav and Settings", () => {
  it("shows Reality only while its switch is on", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    });
    renderApp("/engagements/e1/setup");
    await screen.findByRole("link", { name: /Leadership/ });
    expect(screen.queryByRole("link", { name: /^Reality/ })).toBeNull();
    vi.unstubAllGlobals();
    backend();
    renderApp("/engagements/e1/setup");
    expect(await screen.findByRole("link", { name: /^Reality/ })).toHaveAttribute("href", "/engagements/e1/reality");
  });
});

describe("Leadership reads the snapshot (G17)", () => {
  it("shows the Reality tiles with the same figures as the Glance view", async () => {
    const { MetricTiles } = await import("../../src/components/reality");
    render(<MetricTiles tiles={REALITY.leadership_reality.tiles} />);
    for (const t of SNAP.tiles) {
      expect(screen.getByText(t.figure.text)).toBeInTheDocument();
      expect(screen.getByText(t.caption)).toBeInTheDocument();
    }
  });
});
