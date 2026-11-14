import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CompassLink, Engagement, EngagementSummary, HandoffPreview } from "../../src/api/types";
import { seriousViolations } from "../axe";
import sample from "../fixtures/compass_sample.json";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp, type Handler } from "../renderApp";

// The same process in another country (2026-11-13, Eric's brief; DECISIONS 98).
afterEach(() => vi.unstubAllGlobals());

const PREVIEW = sample.preview as HandoffPreview;
const LINK = sample.link as CompassLink;
const ARDEN: Engagement = {
  ...ENGAGEMENT,
  id: "arden",
  name: "MERIDIAN VS-01 Bid to contract renewal",
  process_name: "Bid to contract renewal",
  trigger: "Renewal due in 120 days",
  end_point: "Contract signed",
  process_kpi: "Win rate on renewals",
  country: "Arden",
  compass: { ...LINK, country: "Arden" },
};
const BELMAR_PREVIEW: HandoffPreview = {
  ...PREVIEW,
  key: "MERIDIANBE",
  country: "Belmar",
  pilots: PREVIEW.pilots
    .filter((p) => p.ref === "VS-01")
    .map((p) => ({
      ...p,
      name: "MERIDIANBE VS-01 Bid to contract renewal",
      same_process: [
        { engagement_id: "arden", name: ARDEN.name, country: "Arden", process_name: ARDEN.process_name, has_published: true },
      ],
    })),
};
const MADE: Engagement = { ...ARDEN, id: "belmar", country: "Belmar", reference_engagement_id: "arden" };
const LANES = ["Regional finance controller", "Bid & Solutions Architect"].map((name, i) => ({
  id: `r${i}`,
  engagement_id: "arden",
  name,
  aliases: [],
  is_system: false,
  lane_order: i + 1,
}));

function choose(dialog: HTMLElement) {
  const file = new File(["{}"], "belmar_compass_handoff.json", { type: "application/json" });
  fireEvent.change(within(dialog).getByTestId("handoff-file-input"), { target: { files: [file] } });
}

function home(extra: Record<string, Handler> = {}) {
  const summary: EngagementSummary = {
    ...ARDEN,
    latest_version: { label: "v1.0", state: "published" },
    review_progress: { reviewed: 8, total: 8 },
    sources_count: 3,
  };
  return fakeApi({
    "GET /api/settings": () => ({ body: SETTINGS }),
    "GET /api/engagements": () => ({ body: [summary] }),
    "POST /api/compass/preview": () => ({ body: BELMAR_PREVIEW }),
    "POST /api/engagements": () => ({ status: 201, body: MADE }),
    "GET /api/engagements/arden": () => ({ body: ARDEN }),
    "GET /api/engagements/arden/roles": () => ({ body: LANES }),
    "GET /api/engagements/belmar": () => ({ body: MADE }),
    "GET /api/engagements/belmar/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/belmar/roles": () => ({ body: [] }),
    ...extra,
  });
}

describe("the country on an engagement", () => {
  it("shows the country next to the engagement's name on Home", async () => {
    home();
    const { container } = renderApp("/");
    const card = (await screen.findByRole("link", { name: ARDEN.name })).closest("article") as HTMLElement;
    expect(within(card).getByText("· Arden")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("keeps a country from the hand-off and lets Eric type one otherwise", async () => {
    const plain: Engagement = { ...ENGAGEMENT, country: "" };
    const { calls } = fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements/e1": () => ({ body: plain }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/roles": () => ({ body: [] }),
      "PATCH /api/engagements/e1": () => ({ body: { ...plain, country: "Caldera" } }),
    });
    renderApp("/engagements/e1/setup");
    const country = await screen.findByLabelText("Country");
    fireEvent.change(country, { target: { value: "Caldera" } });
    fireEvent.click(screen.getByRole("button", { name: "Save scope" }));
    await screen.findByText("Scope saved.");
    expect(calls.find((c) => c.key === "PATCH /api/engagements/e1")?.body).toMatchObject({ country: "Caldera" });
  });

  it("shows the hand-off's country without a field to change it", async () => {
    const { calls } = fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements/arden": () => ({ body: ARDEN }),
      "GET /api/engagements/arden/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/arden/roles": () => ({ body: LANES }),
      "PATCH /api/engagements/arden": () => ({ body: ARDEN }),
    });
    renderApp("/engagements/arden/setup");
    expect(await screen.findByText("Country: Arden, from the Capability Compass hand-off.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Country")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save scope" }));
    await screen.findByText("Scope saved.");
    expect(calls.find((c) => c.key === "PATCH /api/engagements/arden")?.body).not.toHaveProperty("country");
  });
});

describe("starting Belmar from Arden (DECISIONS 98)", () => {
  async function openBelmar() {
    const api = home();
    renderApp("/");
    fireEvent.click(await screen.findByRole("button", { name: "New engagement" }));
    const dialog = screen.getByRole("dialog", { name: "New engagement" });
    choose(dialog);
    await within(dialog).findByLabelText("Pilot");
    return { dialog, ...api };
  }

  it("asks whether to start from Arden and sends only the reference and the ticked lanes", async () => {
    const { dialog, calls } = await openBelmar();
    const question = within(dialog).getByRole("group", {
      name: "Arden already maps VS-01 Bid to contract renewal. Start from its scope card, conventions and lanes?",
    });
    expect(within(question).getByRole("radio", { name: "No, use the hand-off only" })).toBeChecked();
    fireEvent.click(within(question).getByRole("radio", { name: `Yes, start from ${ARDEN.name} (Arden)` }));
    expect(await within(dialog).findByRole("note")).toHaveTextContent(
      `From ${ARDEN.name}: process name “Bid to contract renewal”, trigger “Renewal due in 120 days”`,
    );
    expect(within(dialog).queryByLabelText("Process name")).toBeNull(); // Arden's is used
    const lanes = within(dialog).getByRole("group", { name: "Roles to create as lanes" });
    expect(within(lanes).getAllByRole("checkbox")).toHaveLength(2); // Arden's lanes, not the packet's four
    fireEvent.click(within(lanes).getByRole("checkbox", { name: "Regional finance controller" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Create engagement" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Setup" })).toBeInTheDocument();
    const sent = calls.find((c) => c.key === "POST /api/engagements")?.body as Record<string, unknown>;
    expect(sent).toMatchObject({
      name: "MERIDIANBE VS-01 Bid to contract renewal",
      reference_engagement_id: "arden",
      role_names: ["Bid & Solutions Architect"],
      compass: { pilot_ref: "VS-01" },
    });
    // The scope fields are left to the backend to copy from Arden.
    for (const field of ["process_name", "process_kpi", "trigger", "end_point", "in_scope_roles"]) {
      expect(sent).not.toHaveProperty(field);
    }
  });

  it("answering no keeps the hand-off's own fields, as before", async () => {
    const { dialog, calls } = await openBelmar();
    expect(within(dialog).getByLabelText("Process name")).toHaveValue("Bid to contract renewal");
    expect(await seriousViolations(dialog)).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Create engagement" }));
    await screen.findByRole("heading", { level: 1, name: "Setup" });
    const sent = calls.find((c) => c.key === "POST /api/engagements")?.body as Record<string, unknown>;
    expect(sent).not.toHaveProperty("reference_engagement_id");
    expect(sent.process_name).toBe("Bid to contract renewal");
  });
});

describe("Map this process in another country", () => {
  function setup(published: boolean) {
    return fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements/e1": () => ({ body: { ...ENGAGEMENT, country: "Arden" } }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/roles": () => ({ body: LANES.map((l) => ({ ...l, engagement_id: "e1" })) }),
      "GET /api/engagements/e1/versions": () => ({
        body: published
          ? [{ id: "v1", engagement_id: "e1", label: "v1.0", state: "published", created_at: "", published_at: "", published_by: "Eric", parent_version_id: null }]
          : [],
      }),
      "POST /api/engagements/e1/another-country": () => ({ status: 201, body: { ...MADE, id: "belmar" } }),
      "GET /api/engagements/belmar": () => ({ body: MADE }),
      "GET /api/engagements/belmar/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/belmar/roles": () => ({ body: [] }),
    });
  }

  it("explains what is missing before a version is published", async () => {
    setup(false);
    renderApp("/engagements/e1/setup");
    expect(
      await screen.findByText("Publish a version of this map first: another country starts from a published map."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Map this process in another country…" })).toBeNull();
  });

  it("starts the other country with the country typed and the lanes ticked", async () => {
    const { calls } = setup(true);
    renderApp("/engagements/e1/setup");
    fireEvent.click(await screen.findByRole("button", { name: "Map this process in another country…" }));
    const dialog = screen.getByRole("dialog", { name: "Map this process in another country" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Start this country" }));
    expect(within(dialog).getByText("Type the country this map will cover.")).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText("Country"), { target: { value: "Belmar" } });
    fireEvent.click(within(dialog).getByRole("checkbox", { name: "Regional finance controller" }));
    expect(await seriousViolations(dialog)).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Start this country" }));
    await screen.findByRole("heading", { level: 1, name: "Setup" });
    expect(calls.find((c) => c.key === "POST /api/engagements/e1/another-country")?.body).toEqual({
      country: "Belmar",
      role_ids: ["r1"],
    });
  });
});
