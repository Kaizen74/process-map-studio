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

/** The Interviewees and their guides are on the Guide tab (PRD §5.4 tabs; C5c). */
async function openGuideTab() {
  fireEvent.click(await screen.findByRole("tab", { name: "Guide" }));
}

function interviewApi(extra: Parameters<typeof fakeApi>[0] = {}) {
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    // C5a: the Interviewees section reads the profiles and the roles.
    "GET /api/engagements/e1/profiles": () => ({ body: [] }),
    "GET /api/engagements/e1/roles": () => ({ body: ROLES }),
    // G2: each interviewee's latest tailored guide.
    "GET /api/engagements/e1/interview-guides": () => ({ body: [] }),
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
    expect(screen.getByText(/The coverage report is not available on this screen yet; the standard templates and tailored guides work/)).toBeInTheDocument();
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
    await openGuideTab();
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
    await openGuideTab();
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
    await openGuideTab();
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

describe("Tailored guides (G2, C5b; PRD Appendix F.8, F.9, criteria 69 and 80)", () => {
  const GUIDE = { id: "g1", profile_id: "p1", interview_type: "landscape", version: 1, created_at: "2026-10-06T09:00:00+00:00" };
  const JOB = {
    id: "j1", engagement_id: "e1", type: "interview_guide", target_id: "p1", status: "done", stage: "",
    progress: 1, message: "Guide version 1 made. 4 role-module questions drafted and checked.", error: "",
    usage: { calls: 1, input_tokens: 900, output_tokens: 300 }, claims: { verified: 0, rejected: 0 },
    stages: [], created_at: "2026-10-06T09:00:00+00:00",
  };

  it("makes a guide for an interviewee, then offers Word and Markdown downloads and a new version", async () => {
    let guides: unknown[] = [];
    const api = interviewApi({
      "GET /api/engagements/e1/profiles": () => ({ body: [PROFILE] }),
      "GET /api/engagements/e1/interview-guides": () => ({ body: guides }),
      // C5b: making a guide is a background job; the screen follows it, then lists the guide.
      "POST /api/engagements/e1/interview-guide": () => {
        guides = [GUIDE];
        return { status: 202, body: { job_id: "j1", profile_id: "p1" } };
      },
      "GET /api/jobs/j1": () => ({ body: JOB }),
    });
    const { container } = renderApp(PATH);
    await openGuideTab();
    const section = await screen.findByRole("region", { name: "Interviewees" });
    const list = await within(section).findByRole("list", { name: "Interviewees" });
    expect(await within(list).findByText("No guide yet")).toBeInTheDocument();
    expect(within(list).queryByRole("link", { name: /Download Word/ })).toBeNull();
    fireEvent.click(within(list).getByRole("button", { name: "Make guide for Ramp agent · Ramp" }));
    await waitFor(() =>
      expect(api.calls.find((c) => c.key === "POST /api/engagements/e1/interview-guide")?.body).toEqual({
        profile_id: "p1",
      }),
    );
    expect(await within(list).findByText("Guide version 1 (Landscape)")).toBeInTheDocument();
    expect(await within(list).findByRole("status")).toHaveTextContent(
      "Guide version 1 made. 4 role-module questions drafted and checked.",
    );
    expect(within(list).getByRole("link", { name: "Download Word guide for Ramp agent · Ramp" })).toHaveAttribute(
      "href",
      "/api/engagements/e1/interview-guide/export?profile_id=p1&format=docx",
    );
    expect(within(list).getByRole("link", { name: "Download Markdown guide for Ramp agent · Ramp" })).toHaveAttribute(
      "href",
      "/api/engagements/e1/interview-guide/export?profile_id=p1&format=md",
    );
    expect(within(list).getByRole("button", { name: "Make new version for Ramp agent · Ramp" })).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("shows a refusal under the interviewee and a plain error when the guides can't be loaded", async () => {
    interviewApi({
      "GET /api/engagements/e1/profiles": () => ({ body: [PROFILE] }),
      "GET /api/engagements/e1/interview-guides": () => ({
        status: 500,
        body: { error: { code: "INTERNAL", message: "Something went wrong on our side.", details: {} } },
      }),
      "POST /api/engagements/e1/interview-guide": () => ({
        status: 422,
        body: { error: { code: "VALIDATION", message: "Choose one of this engagement's interviewees.", details: { field: "profile_id" } } },
      }),
    });
    renderApp(PATH);
    await openGuideTab();
    const section = await screen.findByRole("region", { name: "Interviewees" });
    expect(await within(section).findByText("The tailored guides couldn't be loaded")).toBeInTheDocument();
    const list = within(section).getByRole("list", { name: "Interviewees" });
    fireEvent.click(within(list).getByRole("button", { name: "Make guide for Ramp agent · Ramp" }));
    expect(await within(list).findByRole("alert")).toHaveTextContent("Choose one of this engagement's interviewees.");
  });

  it("says plainly when making the guide failed", async () => {
    interviewApi({
      "GET /api/engagements/e1/profiles": () => ({ body: [PROFILE] }),
      "POST /api/engagements/e1/interview-guide": () => ({ status: 202, body: { job_id: "j1", profile_id: "p1" } }),
      "GET /api/jobs/j1": () => ({
        body: { ...JOB, status: "failed", message: "", error: "Something went wrong while making this guide. Nothing was saved." },
      }),
    });
    renderApp(PATH);
    await openGuideTab();
    const list = await screen.findByRole("list", { name: "Interviewees" });
    fireEvent.click(within(list).getByRole("button", { name: "Make guide for Ramp agent · Ramp" }));
    expect(await within(list).findByRole("alert")).toHaveTextContent("Something went wrong while making this guide.");
    expect(within(list).getByText("No guide yet")).toBeInTheDocument();
  });
});

describe("Guide editor (C5c; PRD §5.4 Guide tab, criterion 49)", () => {
  const SUMMARY = { id: "g1", profile_id: "p1", interview_type: "practice", version: 1, created_at: "2026-10-06T09:00:00+00:00" };
  const row = (over: Record<string, unknown>) => ({
    id: "", lead_in: "", wording: "", note: "", probes: [], minutes: "2", signifier: false, movement: "",
    targets: [], priority: "standard", held_back: [], ...over,
  });
  const GUIDE_VIEW = {
    id: "g1", engagement_id: "e1", profile_id: "p1", interview_type: "practice", version: 1, edited: false,
    created_at: "2026-10-06T09:00:00+00:00",
    document: {
      kind: "practice", title: "Practice interview guide: Ramp agent · Ramp", minutes: 60, generation_note: "",
      tables: [
        { label: "M2 — The last real case: the As done spine", minutes: 14, note: "", rows: [
          row({ id: "M2.2", wording: "Walk me through what happened, step by step.", probes: ["And then?"],
                movement: "M2", targets: ["Flow (steps)"], priority: "core", minutes: "3½" }),
          row({}),
        ] },
        { label: "M6 — Contrast: official vs lived; now bring the documents", minutes: 6, note: "", rows: [
          row({ id: "M6.5", wording: "SOP-derived (generator inserts, max 5):", movement: "M6", targets: ["Reality gap"],
                held_back: ["The procedure mentions “Approve load plan”. Where does that happen in practice?"] }),
        ] },
      ],
    },
  };

  function editorApi(patch: (body: unknown) => { status?: number; body: unknown }) {
    return interviewApi({
      "GET /api/engagements/e1/profiles": () => ({ body: [{ ...PROFILE, interview_type: "practice" }] }),
      "GET /api/engagements/e1/interview-guides": () => ({ body: [SUMMARY] }),
      "GET /api/engagements/e1/interview-guide": () => ({ body: GUIDE_VIEW }),
      "PATCH /api/engagements/e1/interview-guide": patch,
    });
  }

  it("opens the guide as editable cards, parks SOP probes in M6, and saves the edits", async () => {
    const api = editorApi((body) => ({ body: { ...GUIDE_VIEW, edited: true, document: GUIDE_VIEW.document, _sent: body } }));
    const { container } = renderApp(PATH);
    await openGuideTab();
    const list = await screen.findByRole("list", { name: "Interviewees" });
    fireEvent.click(await within(list).findByRole("button", { name: "Edit guide for Ramp agent · Ramp" }));
    const form = await screen.findByRole("form", { name: "Edit Practice interview guide: Ramp agent · Ramp" });
    expect(within(form).getByRole("heading", { name: /M2 — The last real case/ })).toBeInTheDocument();
    expect(form).toHaveTextContent("M2.2 · 3½ min · for: Flow (steps)");
    const question = within(form).getByRole("textbox", { name: "Question M2.2" });
    expect(question).toHaveValue("Walk me through what happened, step by step.");
    const held = within(form).getByRole("textbox", { name: "Held-back probes for M6.5 (one per line)" });
    expect(held).toHaveValue("The procedure mentions “Approve load plan”. Where does that happen in practice?");
    expect(within(form).getByText(/Held back to avoid anchoring the SME/)).toBeInTheDocument();
    fireEvent.change(question, { target: { value: "Walk me through the last flight you loaded." } });
    fireEvent.change(within(form).getByRole("textbox", { name: "Probes for M2.2 (one per line)" }), {
      target: { value: "And then?\nWho did that?" },
    });
    fireEvent.change(within(form).getByRole("textbox", { name: /^Your question \(M2/ }), {
      target: { value: "What would a new colleague find hardest?" },
    });
    expect(await seriousViolations(container)).toEqual([]);
    fireEvent.click(within(form).getByRole("button", { name: "Save guide" }));
    await waitFor(() => expect(api.calls.some((c) => c.key === "PATCH /api/engagements/e1/interview-guide")).toBe(true));
    const sent = api.calls.find((c) => c.key === "PATCH /api/engagements/e1/interview-guide")?.body as {
      tables: { label: string; rows: { id: string; wording: string; probes: string[]; held_back: string[] }[] }[];
    };
    expect(sent.tables.map((t) => t.label)).toEqual(GUIDE_VIEW.document.tables.map((t) => t.label));
    expect(sent.tables[0]?.rows[0]).toEqual({
      id: "M2.2", wording: "Walk me through the last flight you loaded.", probes: ["And then?", "Who did that?"], held_back: [],
    });
    expect(sent.tables[0]?.rows[1]).toMatchObject({ id: "", wording: "What would a new colleague find hardest?" });
    expect(await within(form).findByRole("status")).toHaveTextContent("Saved.");
  });

  it("shows a refusal under the question it names and keeps the edits", async () => {
    editorApi(() => ({
      status: 422,
      body: { error: { code: "VALIDATION", message: "Keep what the documents say for M6, after the interviewee has described the work in their own words.", details: { field: "tables[0].rows[0].wording" } } },
    }));
    renderApp(PATH);
    await openGuideTab();
    fireEvent.click(await screen.findByRole("button", { name: "Edit guide for Ramp agent · Ramp" }));
    const form = await screen.findByRole("form", { name: /^Edit Practice interview guide/ });
    const question = within(form).getByRole("textbox", { name: "Question M2.2" });
    fireEvent.change(question, { target: { value: "The SOP says to walk through it. Do you?" } });
    fireEvent.click(within(form).getByRole("button", { name: "Save guide" }));
    await waitFor(() => expect(question).toHaveAttribute("aria-invalid", "true"));
    expect(within(form).getByRole("alert")).toHaveTextContent("Not saved: Keep what the documents say for M6");
    expect(question).toHaveValue("The SOP says to walk through it. Do you?");
    fireEvent.click(within(form).getByRole("button", { name: "Close editor" }));
    expect(screen.queryByRole("form", { name: /^Edit Practice interview guide/ })).toBeNull();
  });
});
