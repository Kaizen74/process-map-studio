import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

const PATH = "/engagements/e1/interview";
const ROLES = [
  { id: "r1", engagement_id: "e1", name: "Load controller", aliases: [], is_system: false, lane_order: 1 },
  { id: "r2", engagement_id: "e1", name: "Ramp agent", aliases: [], is_system: false, lane_order: 2 },
];
const PROFILE = {
  id: "p1", engagement_id: "e1", role_id: "r2", role_name: "Ramp agent", stakeholder_group: "Ramp",
  interview_type: "landscape", referred_by_role: "Load controller", previous_profile_id: null,
  created_at: "2026-10-05T09:00:00+00:00",
};

function interviewApi(extra: Parameters<typeof fakeApi>[0] = {}) {
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    // C5a: the Interviewees section reads the profiles and the roles.
    "GET /api/engagements/e1/profiles": () => ({ body: [] }),
    "GET /api/engagements/e1/roles": () => ({ body: ROLES }),
    ...extra,
  });
}

describe("Interview templates (PRD v1.10 §5.4, F.9)", () => {
  it("offers the three templates on the home screen before any engagement exists", async () => {
    fakeApi({
      "GET /api/settings": () => ({ body: SETTINGS }),
      "GET /api/engagements": () => ({ body: [] }),
    });
    const { container } = renderApp("/");
    const card = await screen.findByRole("region", { name: "Interview templates" });
    const list = await within(card).findByRole("list", { name: "Interview templates" });
    const items = within(list).getAllByRole("listitem");
    expect(items.map((i) => i.querySelector(".template-list__title")?.textContent)).toEqual([
      "Landscape (60 min)",
      "Practice (60 min)",
      "Follow-up (30 min)",
    ]);
    expect(within(card).getByRole("link", { name: "Download Word Practice interview template" })).toHaveAttribute(
      "href",
      "/api/templates/interview?type=practice&format=docx",
    );
    expect(
      within(card).getByRole("link", { name: "Download Markdown Follow-up interview template" }),
    ).toHaveAttribute("href", "/api/templates/interview?type=follow_up&format=md");
    expect(within(card).getAllByRole("link", { name: /^Download/ })).toHaveLength(6);
    expect(card).toHaveTextContent("Say or note the question ID (for example [M2.2]) when you ask it");
    expect(card).toHaveTextContent("No engagement needed.");
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("shows each template's purpose, minute plan and downloads on the Interview screen", async () => {
    interviewApi();
    const { container } = renderApp(PATH);
    expect(await screen.findByRole("heading", { level: 1, name: "Interview" })).toBeInTheDocument();
    const practice = await screen.findByRole("region", { name: "Practice (60 min)" });
    expect(practice).toHaveTextContent("The workflow as actually performed");
    expect(practice).toHaveTextContent("For: People who do the work (one per person)");
    const plan = within(practice).getByRole("table", { name: "Minute plan of the Practice template" });
    const rows = within(plan).getAllByRole("row");
    expect(rows).toHaveLength(1 + 8 + 1); // header, eight movements, total
    expect(rows.at(-1)).toHaveTextContent("Total60");
    expect(practice).toHaveTextContent("45 question IDs · question bank v1.0");
    expect(within(practice).getByRole("link", { name: "Download Word Practice interview template" })).toHaveAttribute(
      "download",
    );
    expect(screen.getByRole("region", { name: "Landscape (60 min)" })).toBeInTheDocument();
    const followUp = screen.getByRole("region", { name: "Follow-up (30 min)" });
    expect(within(followUp).getAllByRole("row").at(-1)).toHaveTextContent("Total30");
    expect(screen.getByText(/Say or note the question ID \(for example \[M2\.2\]\)/)).toBeInTheDocument();
    expect(screen.getByText(/Tailored interview guides and the coverage report are not available yet/)).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("says plainly when the templates can't be loaded, with Try again", async () => {
    let fail = true;
    const api = interviewApi({
      "GET /api/templates/interview/plans": () =>
        fail
          ? { status: 500, body: { error: { code: "IO", message: "The interview question bank is missing or damaged in the app.", details: {} } } }
          : { body: [] },
    });
    renderApp(PATH);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The interview templates couldn't be loaded");
    expect(alert).toHaveTextContent("The interview question bank is missing or damaged in the app.");
    fail = false;
    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    await waitFor(() =>
      expect(api.calls.filter((c) => c.key === "GET /api/templates/interview/plans")).toHaveLength(2),
    );
  });

  it("puts Interview between Setup and Sources in the guided path", async () => {
    interviewApi({
      "GET /api/engagements/e1/readiness": () => ({
        body: { ...READINESS, nav: { ...READINESS.nav, setup: "done" }, next_step: "interview" },
      }),
    });
    renderApp(PATH);
    const nav = await screen.findByRole("navigation", { name: "Engagement steps" });
    const links = within(nav).getAllByRole("link");
    expect(links.slice(0, 3).map((l) => l.getAttribute("href"))).toEqual([
      "/engagements/e1/setup",
      "/engagements/e1/interview",
      "/engagements/e1/sources",
    ]);
    await waitFor(() => expect(links[1]).toHaveAccessibleName(/^Interview, not started.*recommended next step/));
  });
});

describe("Interviewees (C5a; PRD Appendix F.8 rule 1)", () => {
  it("starts empty with one action, adds a profile by role and group, and lists it", async () => {
    let profiles: unknown[] = [];
    const api = interviewApi({
      "GET /api/engagements/e1/profiles": () => ({ body: profiles }),
      "POST /api/engagements/e1/profiles": (body) => {
        profiles = [{ ...PROFILE, ...(body as object) }];
        return { status: 201, body: profiles[0] };
      },
    });
    const { container } = renderApp(PATH);
    const section = await screen.findByRole("region", { name: "Interviewees" });
    expect(await within(section).findByText(/No interviewees yet/)).toBeInTheDocument();
    fireEvent.click(within(section).getByRole("button", { name: "Add interviewee" }));
    const form = within(section).getByRole("form", { name: "Add interviewee" });
    fireEvent.click(within(form).getByRole("radio", { name: "Landscape" }));
    fireEvent.change(within(form).getByRole("combobox", { name: "Role" }), { target: { value: "r2" } });
    fireEvent.change(within(form).getByRole("textbox", { name: "Stakeholder group" }), { target: { value: " Ramp " } });
    fireEvent.change(within(form).getByRole("textbox", { name: "Referred by (role)" }), {
      target: { value: "Load controller" },
    });
    expect(await seriousViolations(container)).toEqual([]);
    fireEvent.click(within(form).getByRole("button", { name: "Add interviewee" }));
    await waitFor(() =>
      expect(api.calls.find((c) => c.key === "POST /api/engagements/e1/profiles")?.body).toEqual({
        interview_type: "landscape", role_id: "r2", stakeholder_group: "Ramp",
        referred_by_role: "Load controller", previous_profile_id: null,
      }),
    );
    const list = await within(section).findByRole("list", { name: "Interviewees" });
    expect(list).toHaveTextContent("Ramp agent · Ramp");
    expect(list).toHaveTextContent("Landscape · referred by Load controller");
    expect(within(section).queryByRole("form")).toBeNull();
  });

  it("asks for a role or a group before saving, and shows the server's refusal under its field", async () => {
    const api = interviewApi({
      "POST /api/engagements/e1/profiles": () => ({
        status: 422,
        body: { error: { code: "VALIDATION", message: "The stakeholder group contains a name from your list of names to hide. Use the role instead.", details: { field: "stakeholder_group" } } },
      }),
    });
    renderApp(PATH);
    const section = await screen.findByRole("region", { name: "Interviewees" });
    fireEvent.click(await within(section).findByRole("button", { name: "Add interviewee" }));
    const form = within(section).getByRole("form", { name: "Add interviewee" });
    fireEvent.click(within(form).getByRole("button", { name: "Add interviewee" }));
    expect(within(form).getByText(/choose a role or name the stakeholder group/)).toBeInTheDocument();
    expect(api.calls.some((c) => c.key === "POST /api/engagements/e1/profiles")).toBe(false);
    fireEvent.change(within(form).getByRole("textbox", { name: "Stakeholder group" }), { target: { value: "Team X" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add interviewee" }));
    const field = within(form).getByRole("textbox", { name: "Stakeholder group" });
    await waitFor(() => expect(field).toHaveAttribute("aria-invalid", "true"));
    expect(within(form).getByText(/names to hide. Use the role instead./)).toBeInTheDocument();
  });

  it("edits a profile; a follow-up chooses the earlier interview it builds on", async () => {
    const api = interviewApi({
      "GET /api/engagements/e1/profiles": () => ({ body: [PROFILE] }),
      "POST /api/engagements/e1/profiles": (body) => ({ status: 201, body: { ...PROFILE, id: "p2", ...(body as object) } }),
    });
    renderApp(PATH);
    const section = await screen.findByRole("region", { name: "Interviewees" });
    fireEvent.click(await within(section).findByRole("button", { name: "Add interviewee" }));
    const form = within(section).getByRole("form", { name: "Add interviewee" });
    expect(within(form).queryByRole("combobox", { name: "Earlier interview" })).toBeNull();
    fireEvent.click(within(form).getByRole("radio", { name: "Follow-up" }));
    const earlier = within(form).getByRole("combobox", { name: "Earlier interview" });
    expect(within(earlier).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "None",
      "Ramp agent · Ramp (Landscape)",
    ]);
    fireEvent.change(earlier, { target: { value: "p1" } });
    fireEvent.change(within(form).getByRole("combobox", { name: "Role" }), { target: { value: "r2" } });
    fireEvent.click(within(form).getByRole("button", { name: "Add interviewee" }));
    await waitFor(() =>
      expect(api.calls.find((c) => c.key === "POST /api/engagements/e1/profiles")?.body).toMatchObject({
        interview_type: "follow_up", previous_profile_id: "p1",
      }),
    );
    fireEvent.click(within(section).getByRole("button", { name: "Edit Ramp agent · Ramp" }));
    const editForm = within(section).getByRole("form", { name: "Edit interviewee" });
    expect(within(editForm).getByRole("textbox", { name: "Stakeholder group" })).toHaveValue("Ramp");
    expect(within(editForm).getByRole("radio", { name: "Landscape" })).toHaveAttribute("aria-checked", "true");
  });
});
