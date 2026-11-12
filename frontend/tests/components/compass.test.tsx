import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CompassLink, Engagement, HandoffPreview, TestingItem } from "../../src/api/types";
import { seriousViolations } from "../axe";
import sample from "../fixtures/compass_sample.json";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp, type Handler } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

// The backend's own output for Eric's sample hand-off (fictional data), DECISIONS 95.
const PREVIEW = sample.preview as HandoffPreview;
const LINK = sample.link as CompassLink;
const TESTING = sample.testing as TestingItem[];
const MADE: Engagement = { ...ENGAGEMENT, id: "e9", name: "MERIDIAN VS-01 Bid to contract renewal", compass: LINK };

function home(extra: Record<string, Handler> = {}) {
  return fakeApi({
    "GET /api/settings": () => ({ body: SETTINGS }),
    "GET /api/engagements": () => ({ body: [] }),
    "POST /api/compass/preview": () => ({ body: PREVIEW }),
    "POST /api/engagements": () => ({ status: 201, body: MADE }),
    "GET /api/engagements/e9": () => ({ body: MADE }),
    "GET /api/engagements/e9/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e9/roles": () => ({ body: [] }),
    "GET /api/engagements/e9/testing": () => ({ body: TESTING }),
    ...extra,
  });
}

async function openDialog() {
  renderApp("/");
  fireEvent.click(await screen.findByRole("button", { name: "New engagement" }));
  return screen.getByRole("dialog", { name: "New engagement" });
}

function choose(dialog: HTMLElement, text: string) {
  const file = new File([text], "meridian_compass_handoff.json", { type: "application/json" });
  fireEvent.change(within(dialog).getByTestId("handoff-file-input"), { target: { files: [file] } });
}

describe("New engagement from a Capability Compass hand-off (DECISIONS 95)", () => {
  it("previews the file, pre-fills the chosen pilot and creates only after Eric confirms", async () => {
    const { calls } = home();
    const dialog = await openDialog();
    expect(within(dialog).getByRole("button", { name: "Start from a Capability Compass hand-off…" })).toBeVisible();
    choose(dialog, JSON.stringify({ format: "compass-handoff" }));
    const pilot = await within(dialog).findByLabelText("Pilot");
    expect(calls.find((c) => c.key === "POST /api/compass/preview")?.body).toEqual({
      handoff: { format: "compass-handoff" },
    });
    expect(calls.some((c) => c.key === "POST /api/engagements")).toBe(false); // nothing applied yet
    expect(dialog).toHaveTextContent("MERIDIAN · Meridian Group (fictional demo)");
    // The first pilot in the file is offered first; Eric picks the other.
    expect(within(dialog).getByLabelText("Engagement name")).toHaveValue("MERIDIAN VS-02 Roster to shift cover");
    fireEvent.change(pilot, { target: { value: "VS-01" } });
    expect(within(dialog).getByLabelText("Engagement name")).toHaveValue("MERIDIAN VS-01 Bid to contract renewal");
    expect(within(dialog).getByLabelText("Process name")).toHaveValue("Bid to contract renewal");
    expect(within(dialog).getByLabelText("Industry")).toHaveValue("Aviation, Logistics & Transportation");
    const roles = within(dialog).getByRole("group", { name: "Roles to create as lanes" });
    expect(within(roles).getAllByRole("checkbox")).toHaveLength(4);
    fireEvent.click(within(roles).getByRole("checkbox", { name: "VP Global Account Management" }));
    expect(dialog).toHaveTextContent("Cluster CAP-04 Commercial Leadership");
    expect(dialog).toHaveTextContent("4 design principles to test");
    expect(dialog).toHaveTextContent("2 suggested interview probes");
    fireEvent.change(within(dialog).getByLabelText("Process KPI"), { target: { value: "Renewal win rate" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create engagement" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Setup" })).toBeInTheDocument();
    const sent = calls.find((c) => c.key === "POST /api/engagements")?.body as Record<string, unknown>;
    expect(sent).toMatchObject({
      name: "MERIDIAN VS-01 Bid to contract renewal",
      process_name: "Bid to contract renewal",
      process_kpi: "Renewal win rate", // what Eric typed wins
      industry: "Aviation, Logistics & Transportation",
      compass: { handoff: { format: "compass-handoff" }, pilot_ref: "VS-01" },
      role_names: [
        "Head of Pricing / Revenue Management",
        "Global Head, Commercial Excellence",
        "Bid & Solutions Architect",
      ],
    });
    expect(sent.in_scope_roles).toEqual(sent.role_names);
  });

  it("warns, without blocking, when the hand-off says it isn't ready", async () => {
    home({
      "POST /api/compass/preview": () => ({
        body: { ...PREVIEW, ready: false, verdict: "Two clusters unscored", open: ["Score CAP-05"] },
      }),
    });
    const dialog = await openDialog();
    choose(dialog, "{}");
    const note = await within(dialog).findByRole("note");
    expect(note).toHaveTextContent("Capability Compass marks this hand-off as not ready: Two clusters unscored.");
    expect(note).toHaveTextContent("Score CAP-05");
    expect(within(dialog).getByRole("button", { name: "Create engagement" })).toBeEnabled();
  });

  it("says plainly when the file can't be read, and keeps the plain form usable", async () => {
    const { calls } = home({
      "POST /api/compass/preview": () => ({
        status: 422,
        body: {
          error: {
            code: "VALIDATION",
            message: "This isn't a Capability Compass hand-off file (its format is “x”, not “compass-handoff”).",
            details: { field: "handoff" },
          },
        },
      }),
    });
    const dialog = await openDialog();
    choose(dialog, "not json at all");
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "This file couldn't be read as a hand-off: it isn't a JSON file.",
    );
    expect(calls.some((c) => c.key === "POST /api/compass/preview")).toBe(false);
    choose(dialog, JSON.stringify({ format: "x" }));
    await waitFor(() =>
      expect(within(dialog).getByRole("alert")).toHaveTextContent("This isn't a Capability Compass hand-off file"),
    );
    expect(within(dialog).queryByLabelText("Pilot")).toBeNull();
    // Standalone still works: a name is all it needs.
    fireEvent.change(within(dialog).getByLabelText("Engagement name"), { target: { value: "Load control" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create engagement" }));
    await waitFor(() =>
      expect(calls.find((c) => c.key === "POST /api/engagements")?.body).toEqual({ name: "Load control" }),
    );
  });

  it("can drop the hand-off again before creating", async () => {
    const { calls } = home();
    const dialog = await openDialog();
    choose(dialog, "{}");
    await within(dialog).findByLabelText("Pilot");
    expect(await seriousViolations(dialog)).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Don't use this hand-off" }));
    expect(within(dialog).queryByLabelText("Pilot")).toBeNull();
    expect(within(dialog).queryByLabelText("Process KPI")).toBeNull();
    fireEvent.change(within(dialog).getByLabelText("Engagement name"), { target: { value: "Plain" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create engagement" }));
    await waitFor(() => expect(calls.find((c) => c.key === "POST /api/engagements")?.body).toEqual({ name: "Plain" }));
  });
});

function setup(engagement: Engagement, testing: TestingItem[], extra: Record<string, Handler> = {}) {
  let items = [...testing];
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: engagement }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/roles": () => ({ body: [] }),
    "GET /api/engagements/e1/testing": () => ({ body: items }),
    "POST /api/engagements/e1/testing": (body) => {
      const sent = body as Pick<TestingItem, "ref" | "text" | "refuted_by">;
      const made: TestingItem = { id: "t9", origin: "owner", verdict: "open", evidence_refs: [], note: "", ...sent };
      items = [...items, made];
      return { status: 201, body: made };
    },
    "PATCH /api/testing/t1": (body) => {
      items = items.map((i) => (i.id === "t1" ? { ...i, ...(body as object) } : i));
      return { body: items[0] };
    },
    "DELETE /api/testing/t9": () => {
      items = items.filter((i) => i.id !== "t9");
      return { status: 204, body: null };
    },
    ...extra,
  });
}

const compassCard = () => screen.getByRole("region", { name: "Capability Compass" });
const testingCard = () => screen.getByRole("region", { name: "What we are testing" });

describe("Setup: the hand-off's IDs and What we are testing (DECISIONS 95)", () => {
  it("shows the IDs exactly as received and the suggested probes as prompts", async () => {
    setup({ ...ENGAGEMENT, compass: LINK }, TESTING);
    const { container } = renderApp("/engagements/e1/setup");
    await screen.findByLabelText("Engagement name");
    const card = compassCard();
    expect(card).toHaveTextContent("MERIDIAN:VS-01");
    expect(card).toHaveTextContent("MERIDIAN:CAP-04 Commercial Leadership");
    expect(card).toHaveTextContent("CAP-04.Structure");
    expect(card).toHaveTextContent("CAP-04.Culture");
    expect(card).toHaveTextContent("2 suggested interview probes");
    expect(card).toHaveTextContent("They are prompts, not evidence");
    expect(await within(testingCard()).findByText("P1")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("sets a verdict with the codes behind it", async () => {
    const { calls } = setup({ ...ENGAGEMENT, compass: LINK }, TESTING);
    renderApp("/engagements/e1/setup");
    const card = await screen.findByRole("region", { name: "What we are testing" });
    const list = await within(card).findByRole("list", { name: "Items being tested" });
    const [p1] = within(list).getAllByRole("listitem");
    expect(p1).toHaveTextContent("Decisions are made at the station, by one named role.");
    expect(p1).toHaveTextContent("Refuted by: Event records showing a different role deciding");
    expect(within(p1 as HTMLElement).getByText("From the hand-off")).toBeInTheDocument();
    fireEvent.click(within(p1 as HTMLElement).getByRole("button", { name: "Set verdict for P1" }));
    const dialog = screen.getByRole("dialog", { name: "Verdict for P1" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Refuted" }));
    fireEvent.change(within(dialog).getByLabelText("Step, discrepancy or intent codes"), {
      target: { value: "X2, S-04" },
    });
    fireEvent.change(within(dialog).getByLabelText("Note (optional)"), { target: { value: "Two roles decide." } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save verdict" }));
    expect(await screen.findByText("Verdict for P1 saved.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PATCH /api/testing/t1")?.body).toEqual({
      verdict: "refuted",
      evidence_refs: ["X2", "S-04"],
      note: "Two roles decide.",
    });
    await waitFor(() => expect(within(list).getAllByRole("listitem")[0]).toHaveTextContent("Refuted · X2, S-04"));
  });

  it("shows the server's reason in the verdict box", async () => {
    setup({ ...ENGAGEMENT, compass: LINK }, TESTING, {
      "PATCH /api/testing/t1": () => ({
        status: 422,
        body: {
          error: {
            code: "VALIDATION",
            message: "Add the step or discrepancy codes this verdict rests on.",
            details: { field: "evidence_refs" },
          },
        },
      }),
    });
    renderApp("/engagements/e1/setup");
    const card = await screen.findByRole("region", { name: "What we are testing" });
    fireEvent.click(await within(card).findByRole("button", { name: "Set verdict for P1" }));
    const dialog = screen.getByRole("dialog", { name: "Verdict for P1" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "Supported" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Save verdict" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Add the step or discrepancy codes this verdict rests on.",
    );
  });

  it("works with no hand-off: no Compass card, and a hypothesis can be added and removed by hand", async () => {
    const { calls } = setup(ENGAGEMENT, []);
    const { container } = renderApp("/engagements/e1/setup");
    await screen.findByLabelText("Engagement name");
    expect(screen.queryByRole("region", { name: "Capability Compass" })).toBeNull();
    const card = testingCard();
    expect(
      await within(card).findByText(
        "Nothing to test yet. Design principles arrive with a Capability Compass hand-off; you can also add a hypothesis by hand.",
      ),
    ).toBeInTheDocument();
    fireEvent.change(within(card).getByLabelText("ID"), { target: { value: "H2" } });
    fireEvent.change(within(card).getByLabelText("What is being tested"), {
      target: { value: "Pricing sits with regional sales." },
    });
    fireEvent.click(within(card).getByRole("button", { name: "Add item" }));
    expect(await screen.findByText("H2 added.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "POST /api/engagements/e1/testing")?.body).toEqual({
      ref: "H2",
      text: "Pricing sits with regional sales.",
      refuted_by: "",
    });
    const list = await within(card).findByRole("list", { name: "Items being tested" });
    expect(within(list).getByText("Added by you")).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
    fireEvent.click(within(list).getByRole("button", { name: "Remove H2" }));
    expect(await screen.findByText("H2 removed.")).toBeInTheDocument();
  });
});
