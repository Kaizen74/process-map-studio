import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Role } from "../../src/api/types";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

const PATH = "/engagements/e1/setup";

function role(id: string, name: string, lane: number, extra: Partial<Role> = {}): Role {
  return { id, engagement_id: "e1", name, aliases: [], is_system: false, lane_order: lane, ...extra };
}

/** A fake backend whose roles behave like the real one (new roles go to the bottom; moves renumber). */
function setupApi(initialRoles: Role[] = [], extra: Parameters<typeof fakeApi>[0] = {}) {
  let roles = [...initialRoles];
  let engagement = { ...ENGAGEMENT };
  const patchRole = (id: string) => (body: unknown) => {
    const patch = body as Partial<Role>;
    const current = roles.find((r) => r.id === id);
    if (!current) return { status: 404, body: { error: { code: "NOT_FOUND", message: "Gone.", details: {} } } };
    const updated = { ...current, ...patch };
    roles = roles.filter((r) => r.id !== id);
    const lane = patch.lane_order ?? current.lane_order ?? roles.length + 1;
    roles.splice(lane - 1, 0, updated);
    roles = roles.map((r, i) => ({ ...r, lane_order: i + 1 }));
    return { body: roles.find((r) => r.id === id) };
  };
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: engagement }),
    "PATCH /api/engagements/e1": (body) => {
      engagement = { ...engagement, ...(body as object) };
      return { body: engagement };
    },
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/roles": () => ({ body: roles }),
    "POST /api/engagements/e1/roles": (body) => {
      const created = role(`r${roles.length + 1}`, (body as Role).name, roles.length + 1, body as Partial<Role>);
      roles = [...roles, created];
      return { status: 201, body: created };
    },
    ...Object.fromEntries(initialRoles.map((r) => [`PATCH /api/roles/${r.id}`, patchRole(r.id)])),
    ...extra,
  });
}

const scope = () => screen.getByRole("region", { name: "Process scope" });
const SEVERAL_FLOWS =
  "One engagement maps one flow, from its trigger to its end point. If your documents cover several flows (for example import, export and transhipment), use Map another flow from these sources below for each of the others.";
const rolesCard = () => screen.getByRole("region", { name: "Roles and lanes" });

describe("Setup: process scope", () => {
  it("shows the engagement's scope and saves every field, including chips", async () => {
    const { calls } = setupApi();
    renderApp(PATH);
    expect(await screen.findByRole("heading", { level: 1, name: "Setup" })).toBeInTheDocument();
    expect(await screen.findByLabelText("Engagement name")).toHaveValue("Load control");
    const card = scope();
    expect(within(card).getByLabelText("Process name")).toHaveValue("Aircraft load control");

    fireEvent.change(within(card).getByLabelText("Trigger"), { target: { value: "Flight scheduled" } });
    fireEvent.change(within(card).getByLabelText("End point"), { target: { value: "Load sheet issued" } });
    const terms = within(card).getByLabelText("Confidential terms");
    fireEvent.change(terms, { target: { value: "Acme Ground Services" } });
    fireEvent.keyDown(terms, { key: "Enter" });
    fireEvent.change(terms, { target: { value: "acme ground services" } });
    fireEvent.keyDown(terms, { key: "Enter" });
    fireEvent.change(terms, { target: { value: "DCS-9" } });
    fireEvent.keyDown(terms, { key: "," });
    const roles = within(card).getByLabelText("In-scope roles");
    fireEvent.change(roles, { target: { value: "Ramp" } });
    fireEvent.blur(roles);
    fireEvent.click(within(card).getByRole("button", { name: "Remove DCS-9" }));

    fireEvent.click(within(card).getByRole("button", { name: "Save scope" }));
    expect(await screen.findByText("Scope saved.")).toBeInTheDocument();
    const body = calls.find((c) => c.key === "PATCH /api/engagements/e1")?.body as Record<string, unknown>;
    expect(body).toMatchObject({
      name: "Load control",
      trigger: "Flight scheduled",
      end_point: "Load sheet issued",
      confidential_terms: ["Acme Ground Services"],
      in_scope_roles: ["Ramp"],
    });
  });

  it("asks whether the process starts or ends outside the organisation, and saves the answer", async () => {
    const { calls } = setupApi();
    const { container } = renderApp(PATH);
    await screen.findByLabelText("Engagement name");
    const starts = within(scope()).getByRole("checkbox", { name: "Starts outside the organisation" });
    const ends = within(scope()).getByRole("checkbox", { name: "Ends outside the organisation" });
    expect(starts).not.toBeChecked();
    expect(ends).not.toBeChecked();
    fireEvent.click(starts);
    fireEvent.click(within(scope()).getByRole("button", { name: "Save scope" }));
    expect(await screen.findByText("Scope saved.")).toBeInTheDocument();
    const body = calls.find((c) => c.key === "PATCH /api/engagements/e1")?.body as Record<string, unknown>;
    expect(body).toMatchObject({ trigger_external: true, end_point_external: false });
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("says one engagement maps one flow, for documents that cover several (2026-10-28)", async () => {
    setupApi();
    renderApp(PATH);
    await screen.findByLabelText("Engagement name");
    expect(within(scope()).getByText(SEVERAL_FLOWS)).toBeInTheDocument();
  });

  it("explains a missing name without saving", async () => {
    const { calls } = setupApi();
    renderApp(PATH);
    const name = await screen.findByLabelText("Engagement name");
    fireEvent.change(name, { target: { value: "  " } });
    fireEvent.click(within(scope()).getByRole("button", { name: "Save scope" }));
    expect(await within(scope()).findByText(/Please give the engagement a name/)).toBeInTheDocument();
    expect(name).toHaveAttribute("aria-invalid", "true");
    expect(calls.some((c) => c.key.startsWith("PATCH"))).toBe(false);
  });

  it("shows the server's message under the field it names", async () => {
    setupApi([], {
      "PATCH /api/engagements/e1": () => ({
        status: 422,
        body: { error: { code: "VALIDATION", message: "Trigger: at most 2000 characters.", details: { field: "trigger" } } },
      }),
    });
    renderApp(PATH);
    await screen.findByLabelText("Trigger");
    fireEvent.click(within(scope()).getByRole("button", { name: "Save scope" }));
    expect(await within(scope()).findByText("Trigger: at most 2000 characters.")).toBeInTheDocument();
    expect(within(scope()).getByLabelText("Trigger")).toHaveAttribute("aria-invalid", "true");
  });

  it("says plainly when the engagement no longer exists", async () => {
    fakeApi({});
    renderApp("/engagements/gone/setup");
    expect(await screen.findByRole("heading", { name: "Engagement not found" })).toBeInTheDocument();
  });
});

describe("Setup: roles and lanes", () => {
  const ROLES = [
    role("r1", "Load controller", 1, { aliases: ["LC"] }),
    role("r2", "Ramp agent", 2),
    role("r3", "Departure control system", 3, { is_system: true }),
  ];

  it("explains that roles also come from the sources when there are none", async () => {
    setupApi();
    renderApp(PATH);
    expect(
      await screen.findByText("Roles are also created from your sources when the draft runs. Add any you already know."),
    ).toBeInTheDocument();
  });

  it("lists roles in lane order with aliases and a lane preview", async () => {
    setupApi(ROLES);
    renderApp(PATH);
    const list = await screen.findByRole("list", { name: "Roles in lane order" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows.map((r) => r.querySelector(".role-row__name")?.textContent)).toEqual([
      "Lane 1: Load controller",
      "Lane 2: Ramp agent",
      "Lane 3: Departure control system",
    ]);
    expect(rows[0]).toHaveTextContent("LC");
    const preview = screen.getByRole("figure", { name: "Lane preview, top to bottom" });
    expect(within(preview).getAllByRole("listitem").map((l) => l.textContent)).toEqual([
      "Load controller",
      "Ramp agent",
      "Departure control systemSystem",
    ]);
  });

  it("adds a role to the bottom lane", async () => {
    const { calls } = setupApi(ROLES);
    renderApp(PATH);
    await screen.findByRole("list", { name: "Roles in lane order" });
    const add = within(rolesCard()).getByRole("heading", { name: "Add a role" }).parentElement as HTMLElement;
    fireEvent.change(within(add).getByLabelText("Role name"), { target: { value: "Load planner" } });
    fireEvent.click(within(add).getByRole("checkbox", { name: "System role" }));
    fireEvent.click(within(add).getByRole("button", { name: "Add role" }));
    expect(await screen.findByText("Load planner added as lane 4.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "POST /api/engagements/e1/roles")?.body).toEqual({
      name: "Load planner",
      aliases: [],
      is_system: true,
    });
    expect(within(add).getByLabelText("Role name")).toHaveValue("");
  });

  it("keeps what was typed when the name is already taken", async () => {
    setupApi(ROLES, {
      "POST /api/engagements/e1/roles": () => ({
        status: 409,
        body: { error: { code: "CONFLICT", message: "There is already a role called Ramp agent.", details: {} } },
      }),
    });
    renderApp(PATH);
    await screen.findByRole("list", { name: "Roles in lane order" });
    const add = within(rolesCard()).getByRole("heading", { name: "Add a role" }).parentElement as HTMLElement;
    fireEvent.change(within(add).getByLabelText("Role name"), { target: { value: "ramp agent" } });
    fireEvent.click(within(add).getByRole("button", { name: "Add role" }));
    expect(await within(add).findByText("There is already a role called Ramp agent.")).toBeInTheDocument();
    expect(within(add).getByLabelText("Role name")).toHaveValue("ramp agent");
  });

  it("explains a missing role name", async () => {
    const { calls } = setupApi(ROLES);
    renderApp(PATH);
    await screen.findByRole("list", { name: "Roles in lane order" });
    fireEvent.click(within(rolesCard()).getByRole("button", { name: "Add role" }));
    expect(await within(rolesCard()).findByText(/Please give the role a name/)).toBeInTheDocument();
    expect(calls.some((c) => c.key.startsWith("POST"))).toBe(false);
  });

  it("moves a role down and up with buttons (keyboard-friendly lane order)", async () => {
    const { calls } = setupApi(ROLES);
    renderApp(PATH);
    await screen.findByRole("list", { name: "Roles in lane order" });
    expect(screen.queryByRole("button", { name: "Move Load controller up" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Move Load controller down" }));
    expect(await screen.findByText("Load controller moved to lane 2.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PATCH /api/roles/r1")?.body).toEqual({ lane_order: 2 });
    await screen.findByRole("button", { name: "Move Ramp agent down" });
    const names = () =>
      within(screen.getByRole("list", { name: "Roles in lane order" }))
        .getAllByRole("listitem")
        .map((r) => r.querySelector(".role-row__name")?.textContent);
    expect(names()[0]).toBe("Lane 1: Ramp agent");
    fireEvent.click(screen.getByRole("button", { name: "Move Departure control system up" }));
    expect(await screen.findByText("Departure control system moved to lane 2.")).toBeInTheDocument();
  });

  it("moves a role by dragging it onto another", async () => {
    const { calls } = setupApi(ROLES);
    renderApp(PATH);
    const list = await screen.findByRole("list", { name: "Roles in lane order" });
    const [first, , third] = within(list).getAllByRole("listitem");
    const dataTransfer = { setData: vi.fn(), effectAllowed: "" };
    fireEvent.dragStart(third as HTMLElement, { dataTransfer });
    fireEvent.dragOver(first as HTMLElement, { dataTransfer });
    fireEvent.drop(first as HTMLElement, { dataTransfer });
    expect(await screen.findByText("Departure control system moved to lane 1.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PATCH /api/roles/r3")?.body).toEqual({ lane_order: 1 });
  });

  it("switches the system role setting straight away", async () => {
    const { calls } = setupApi(ROLES);
    renderApp(PATH);
    const list = await screen.findByRole("list", { name: "Roles in lane order" });
    const [, ramp] = within(list).getAllByRole("listitem");
    fireEvent.click(within(ramp as HTMLElement).getByRole("checkbox", { name: "System role" }));
    expect(await screen.findByText("Ramp agent is a system role.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PATCH /api/roles/r2")?.body).toEqual({ is_system: true });
  });

  it("edits a role's name and aliases", async () => {
    const { calls } = setupApi(ROLES);
    renderApp(PATH);
    await screen.findByRole("list", { name: "Roles in lane order" });
    fireEvent.click(screen.getByRole("button", { name: "Edit Load controller" }));
    const form = screen.getByRole("button", { name: "Save role" }).closest("form") as HTMLElement;
    fireEvent.change(within(form).getByLabelText("Role name"), { target: { value: "Load control agent" } });
    const aliases = within(form).getByLabelText("Aliases");
    fireEvent.change(aliases, { target: { value: "LCA" } });
    fireEvent.keyDown(aliases, { key: "Enter" });
    fireEvent.click(within(form).getByRole("button", { name: "Save role" }));
    expect(await screen.findByText("Role saved.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PATCH /api/roles/r1")?.body).toEqual({
      name: "Load control agent",
      aliases: ["LC", "LCA"],
    });
  });

  it("removes a role nothing uses after asking, and the lanes close up (DECISIONS 93)", async () => {
    let gone = false;
    const { calls } = setupApi(ROLES, {
      "DELETE /api/roles/r2": () => {
        gone = true;
        return { status: 204, body: null };
      },
    });
    const { container } = renderApp(PATH);
    const list = await screen.findByRole("list", { name: "Roles in lane order" });
    fireEvent.click(within(list).getByRole("button", { name: "Remove Ramp agent" }));
    const dialog = screen.getByRole("dialog", { name: "Remove Ramp agent?" });
    expect(dialog).toHaveTextContent(
      "Its lane leaves this engagement and the roles below it move up. You can add it again later.",
    );
    expect(await seriousViolations(container)).toEqual([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    expect(await screen.findByText("Ramp agent removed. The lanes below it moved up.")).toBeInTheDocument();
    expect(gone).toBe(true);
    expect(calls.some((c) => c.key === "DELETE /api/roles/r2")).toBe(true);
    expect(screen.queryByRole("dialog", { name: "Remove Ramp agent?" })).toBeNull();
  });

  it("keeps a role still in use and says why, in the box", async () => {
    const why = "Load controller can't be removed: 3 steps use it (“Draft load plan”, “Busy wave?” and 1 more).";
    setupApi(ROLES, {
      "DELETE /api/roles/r1": () => ({
        status: 409,
        body: { error: { code: "CONFLICT", message: why, details: {} } },
      }),
    });
    renderApp(PATH);
    const list = await screen.findByRole("list", { name: "Roles in lane order" });
    fireEvent.click(within(list).getByRole("button", { name: "Remove Load controller" }));
    const dialog = screen.getByRole("dialog", { name: "Remove Load controller?" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove" }));
    const refused = await screen.findByRole("dialog", { name: "Load controller stays" });
    expect(within(refused).getByRole("alert")).toHaveTextContent(why);
    // No Remove that would only be refused again.
    expect(within(refused).queryByRole("button", { name: "Remove" })).toBeNull();
    fireEvent.click(within(refused).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(within(list).getByText("Load controller")).toBeInTheDocument();
  });

  it("has no serious or critical accessibility violations", async () => {
    setupApi(ROLES);
    const { container } = renderApp(PATH);
    await screen.findByRole("list", { name: "Roles in lane order" });
    await screen.findByLabelText("Engagement name");
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("Mapping conventions (C7a; PRD §5.4 Setup, Appendix E tier 2, criterion 58)", () => {
  it("shows the defaults, saves Eric's choices and says when they apply", async () => {
    const api = setupApi([], {
      "PATCH /api/engagements/e1": (body) => ({
        body: { ...ENGAGEMENT, ...(body as object) },
      }),
    });
    const { container } = renderApp(PATH);
    const card = await screen.findByRole("form", { name: "Mapping conventions" });
    const granularity = within(card).getByRole("radiogroup", { name: "Granularity" });
    expect(within(granularity).getByRole("radio", { name: "Standard" })).toHaveAttribute("aria-checked", "true");
    expect(card).toHaveTextContent("about 12–20 steps");
    expect(within(card).getByRole("button", { name: "Saved" })).toBeInTheDocument();
    fireEvent.click(within(granularity).getByRole("radio", { name: "Fine" }));
    fireEvent.click(within(within(card).getByRole("radiogroup", { name: "Step labels" })).getByRole("radio", { name: "SME wording" }));
    expect(card).toHaveTextContent("about 20–25 steps");
    expect(card).toHaveTextContent("The interviewee's own everyday name for a step");
    expect(await seriousViolations(container)).toEqual([]);
    fireEvent.click(within(card).getByRole("button", { name: "Save conventions" }));
    expect(await screen.findByText("Mapping conventions saved. They apply from the next draft or refresh.")).toBeInTheDocument();
    expect(api.calls.find((c) => c.key === "PATCH /api/engagements/e1")?.body).toEqual({
      conventions: { granularity: "fine", label_style: "sme", phase_naming: "sme" },
    });
  });
});
