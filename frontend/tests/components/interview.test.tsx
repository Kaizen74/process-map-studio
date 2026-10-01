import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

const PATH = "/engagements/e1/interview";

function interviewApi(extra: Parameters<typeof fakeApi>[0] = {}) {
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
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
