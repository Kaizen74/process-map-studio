import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ActivityTable,
  LogList,
  RoleMapTable,
  ValidationReportView,
} from "../../src/components/system";
import type {
  ActivityMetrics,
  Alignment,
  EventLog,
  MetricScope,
  MetricsResponse,
  ValidationReport,
} from "../../src/lib/systemRecords";
import { seriousViolations } from "../axe";
import {
  ENGAGEMENT,
  READINESS,
  SETTINGS,
  fakeApi,
  moreSteps,
  renderApp,
  type Handler,
} from "../renderApp";

// System records, R7a (PRD §5.4, §3.13.3; decision A): the module switch, the nav step, the screen,
// the upload and the stepped import wizard, against the shapes the backend really sends.

afterEach(() => vi.unstubAllGlobals());

const SYSTEM = JSON.parse(
  readFileSync(
    join(__dirname, "..", "fixtures", "system_records.json"),
    "utf-8",
  ),
) as {
  held_log: EventLog;
  imported_log: EventLog;
  alignment: Alignment;
  metrics: Record<MetricScope, MetricsResponse<unknown>>;
};
const HELD: EventLog = { ...SYSTEM.held_log, id: "l1", engagement_id: "e1" };
const IMPORTED: EventLog = {
  ...SYSTEM.imported_log,
  id: "l2",
  engagement_id: "e1",
};
const IMPORTED_REPORT = SYSTEM.imported_log
  .validation_report as ValidationReport;
const HELD_REPORT = SYSTEM.held_log.validation_report as ValidationReport;
const ROLES = [
  {
    id: "id-3",
    engagement_id: "e1",
    name: "Load controller",
    aliases: [],
    is_system: false,
    lane_order: 0,
  },
  {
    id: "r2",
    engagement_id: "e1",
    name: "Ramp agent",
    aliases: [],
    is_system: false,
    lane_order: 1,
  },
];
const PATH = "/engagements/e1/system-records";
const JOB = { id: "j1", engagement_id: "e1", type: "event_log_import", target_id: "l1", stage: "", progress: 1,
  message: "Imported 2 events.", error: "", usage: null, claims: { verified: 0, rejected: 0 }, stages: [],
  created_at: "2026-10-08T00:00:00Z" }; // prettier-ignore

function systemApi(
  options: {
    on?: boolean;
    logs?: EventLog[];
    extra?: Record<string, Handler>;
  } = {},
) {
  let on = options.on ?? true;
  let logs = options.logs ?? [];
  const replace = (log: EventLog) => {
    logs = logs.map((l) => (l.id === log.id ? log : l));
    return log;
  };
  return fakeApi({
    "GET /api/settings": () => ({
      body: { ...SETTINGS, system_records_enabled: on },
    }),
    "PUT /api/settings/modules": (body) => {
      on = (body as { system_records_enabled: boolean }).system_records_enabled;
      return { body: { ...SETTINGS, system_records_enabled: on } };
    },
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/roles": () => ({ body: ROLES }),
    "GET /api/engagements/e1/event-logs": () => ({ body: logs }),
    "POST /api/engagements/e1/event-logs": () => {
      logs = [...logs, HELD];
      return { status: 201, body: HELD };
    },
    "PUT /api/event-logs/l1/column-map": (body) => {
      const b = body as {
        columns: Record<string, string | null>;
        timezone?: string;
      };
      return {
        body: replace({
          ...HELD,
          status: "mapped",
          column_map: b.columns,
          timezone: b.timezone ?? HELD.timezone,
        }),
      };
    },
    "PUT /api/event-logs/l1/role-map": (body) => {
      const roles = (body as { roles: Record<string, string | null> }).roles;
      return { body: replace({ ...HELD, status: "mapped", role_map: roles }) };
    },
    "POST /api/event-logs/l1/import": (body) => {
      const b = body as { confirm_approval: boolean; approved_by_role: string };
      if (!b.confirm_approval || !b.approved_by_role) {
        return { status: 409, body: { error: { code: "APPROVAL_REQUIRED", details: {},
          message: "Tick that the data owner approved this extract for this purpose, and give the approver's role." } } }; // prettier-ignore
      }
      return { status: 202, body: { job_id: "j1", log_id: "l1" } };
    },
    "GET /api/jobs/j1": () => {
      logs = logs.map((l) =>
        l.id === "l1" ? { ...IMPORTED, id: "l1", name: HELD.name } : l,
      );
      return { body: { ...JOB, status: "done" } };
    },
    "DELETE /api/event-logs/l2": () => {
      logs = logs.filter((l) => l.id !== "l2");
      return { status: 204, body: null };
    },
    ...options.extra,
  });
}

const nav = () => screen.findByRole("navigation", { name: "Engagement steps" });

describe("System records: the module switch and the nav (decision A)", () => {
  it("keeps the step out of the nav while the module is off", async () => {
    systemApi({ on: false });
    renderApp("/engagements/e1/setup");
    const steps = await nav();
    await moreSteps();
    await waitFor(() =>
      expect(within(steps).getAllByRole("link")).toHaveLength(11),
    ); // 6 in the bar, 5 under More
    expect(
      within(steps).queryByRole("link", { name: /System records/ }),
    ).toBeNull();
  });

  it("lists it under More after Interview, labelled optional and never Next, once switched on", async () => {
    systemApi({ logs: [IMPORTED] });
    renderApp("/engagements/e1/setup");
    const more = await moreSteps();
    const link = await within(more).findByRole("link", {
      name: /^System records/,
    });
    await waitFor(() =>
      expect(link).toHaveAccessibleName("System records, done, optional"),
    );
    const names = within(more)
      .getAllByRole("link")
      .map((l) => l.textContent);
    expect(names.indexOf("System records" + "Optional")).toBe(
      names.indexOf("Interview") + 1,
    );
    expect(link.getAttribute("href")).toBe(PATH);
  });

  it("is switched on and off in Settings, Optional modules", async () => {
    const { calls } = systemApi({ on: false });
    renderApp("/settings");
    const card = (
      await screen.findByRole("heading", { name: "Optional modules" })
    ).closest("section");
    const box = within(card as HTMLElement).getByRole("checkbox", {
      name: "System records",
    });
    expect(box).not.toBeChecked();
    fireEvent.click(box);
    expect(
      await screen.findByText("System records switched on."),
    ).toBeInTheDocument();
    expect(
      calls.find((c) => c.key === "PUT /api/settings/modules")?.body,
    ).toEqual({ system_records_enabled: true });
    await waitFor(() => expect(box).toBeChecked());
  });
});

describe("System records screen", () => {
  it("says the module is off and links to Settings", async () => {
    const { calls } = systemApi({ on: false });
    renderApp(PATH);
    expect(
      await screen.findByText(/System records is switched off/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Go to Settings" }),
    ).toHaveAttribute("href", "/settings");
    expect(
      calls.some((c) => c.key === "GET /api/engagements/e1/event-logs"),
    ).toBe(false);
  });

  it("explains what system records add and offers the data request template", async () => {
    systemApi();
    const view = renderApp(PATH);
    expect(
      await screen.findByText(/No logs yet\. A system's event log shows/),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Download Word" })).toHaveAttribute(
      "href",
      "/api/templates/data-request?format=docx",
    );
    expect(
      screen.getByRole("link", { name: "Download Markdown" }),
    ).toHaveAttribute("href", "/api/templates/data-request?format=md");
    expect(
      screen.getByRole("link", { name: "Download CSV header" }),
    ).toHaveAttribute("href", "/api/templates/data-request?format=csv");
    expect(await seriousViolations(view.container)).toEqual([]);
  });

  it("asks for a file before uploading, then uploads the form and opens the wizard", async () => {
    const { calls } = systemApi();
    renderApp(PATH);
    await screen.findByText(/No logs yet/);
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(
      await screen.findByText("Choose the file from IT first."),
    ).toBeInTheDocument();
    // R11b: CSV or Excel.
    expect(
      screen.getByTestId("log-file-input").getAttribute("accept")?.split(","),
    ).toEqual(expect.arrayContaining([".csv", ".xlsx"]));
    expect(
      screen.getByText(
        /or an Excel workbook \(.xlsx; its first sheet is read\)/,
      ),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("log-file-input"), {
      target: {
        files: [
          new File(["Case ID,Event Name\n"], "dcs.csv", { type: "text/csv" }),
        ],
      },
    });
    expect(screen.getByLabelText("Name")).toHaveValue("dcs");
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Small extract" },
    });
    fireEvent.change(screen.getByLabelText("Window starts (optional)"), {
      target: { value: "2026-03-02" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Upload" }));
    expect(
      await screen.findByRole("heading", { name: "Import Small extract" }),
    ).toBeInTheDocument();
    const form = calls.find(
      (c) => c.key === "POST /api/engagements/e1/event-logs",
    )?.body as FormData;
    expect((form.get("file") as File).name).toBe("dcs.csv");
    expect([
      form.get("name"),
      form.get("timezone"),
      form.get("window_start"),
      form.get("window_end"),
    ]).toEqual(["Small extract", "Asia/Singapore", "2026-03-02", ""]);
    expect(screen.getByText("Step 1 of 5: Map columns")).toBeInTheDocument();
  });

  it("walks the wizard: columns, time zone, roles (not stored), report, approval, import", async () => {
    const { calls } = systemApi({ logs: [HELD] });
    const view = renderApp(`${PATH}?log=l1`);
    // 1 Map columns: the backend's suggestions, each column changeable.
    const column = await screen.findByLabelText("Column “Team”");
    expect(column).toHaveValue("role");
    expect(
      screen.getByText(/Case ID, activity and timestamp are all mapped/),
    ).toBeInTheDocument();
    fireEvent.change(column, { target: { value: "" } });
    expect(await seriousViolations(view.container)).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: "Next: time zone" }));
    // 2 Time zone, saved with the column map in one step.
    fireEvent.change(
      await screen.findByLabelText("Time zone of the times in the file"),
      {
        target: { value: "Europe/London" },
      },
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Next: map users to roles" }),
    );
    expect(
      await screen.findByText("These are not stored."),
    ).toBeInTheDocument();
    expect(
      calls.find((c) => c.key === "PUT /api/event-logs/l1/column-map")?.body,
    ).toEqual({
      columns: { ...HELD.column_map, Team: null },
      timestamp_format: null,
      timezone: "Europe/London",
    });
    // 3 Users to roles: the suggestion is filled in; every ID needs a choice.
    expect(screen.getByLabelText("User ID U1")).toHaveValue("id-3");
    fireEvent.click(
      screen.getByRole("button", { name: "Next: validation report" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Choose a role or Unknown role for every user ID (1 left).",
    );
    fireEvent.change(screen.getByLabelText("User ID U2"), {
      target: { value: "unknown" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Next: validation report" }),
    );
    // 4 Validation report.
    expect(await screen.findByText("Ready to import.")).toBeInTheDocument();
    expect(
      calls.find((c) => c.key === "PUT /api/event-logs/l1/role-map")?.body,
    ).toEqual({
      roles: { U1: "id-3", U2: null },
    });
    expect(
      screen.getByText(
        "1 event with an unknown role: their figures show under Unknown role.",
      ),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Next: approve and import" }),
    );
    // 5 Approval first: the backend refuses without it, in plain words.
    fireEvent.click(await screen.findByRole("button", { name: "Import" }));
    expect(
      await screen.findByText(/Tick that the data owner approved this extract/),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("checkbox", {
        name: "The data owner approved this extract for this purpose",
      }),
    );
    fireEvent.change(screen.getByLabelText("Approver's role"), {
      target: { value: "Head of ground operations" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(
      await screen.findByText("Small extract imported."),
    ).toBeInTheDocument();
    expect(
      calls.filter((c) => c.key === "POST /api/event-logs/l1/import").at(-1)
        ?.body,
    ).toEqual({
      approved_by_role: "Head of ground operations",
      confirm_approval: true,
    });
    // The imported log opens on its matching tab (R7b); its final report is a tab, and no user ID
    // shows anywhere on the screen (constraint 24).
    fireEvent.click(await screen.findByRole("tab", { name: "Import report" }));
    expect(await screen.findByText("Imported.")).toBeInTheDocument();
    expect(screen.queryByText("These are not stored.")).toBeNull();
    expect(document.body.textContent).not.toMatch(/\bU[12]\b/);
  });

  it("goes back to the column step when the backend blames a column", async () => {
    systemApi({
      logs: [HELD],
      extra: {
        "PUT /api/event-logs/l1/column-map": () => ({
          status: 422,
          body: { error: { code: "VALIDATION", message: "Each field can be used for one column only: timestamp.",
            details: { field: "columns" } } }, // prettier-ignore
        }),
      },
    });
    renderApp(`${PATH}?log=l1`);
    fireEvent.click(
      await screen.findByRole("button", { name: "Next: time zone" }),
    );
    fireEvent.click(
      await screen.findByRole("button", { name: "Next: map users to roles" }),
    );
    expect(
      await screen.findByText(
        "Each field can be used for one column only: timestamp.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Step 1 of 5: Map columns")).toBeInTheDocument();
  });

  it("deletes a log after asking", async () => {
    const { calls } = systemApi({ logs: [IMPORTED] });
    renderApp(PATH);
    fireEvent.click(
      await screen.findByRole("button", { name: `Delete ${IMPORTED.name}` }),
    );
    const dialog = await screen.findByRole("dialog", {
      name: `Delete ${IMPORTED.name}?`,
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete log" }));
    expect(
      await screen.findByText(`${IMPORTED.name} deleted.`),
    ).toBeInTheDocument();
    expect(calls.some((c) => c.key === "DELETE /api/event-logs/l2")).toBe(true);
    expect(await screen.findByText(/No logs yet/)).toBeInTheDocument();
  });

  it("says a log whose file is gone can't be imported", async () => {
    systemApi({ logs: [{ ...HELD, file_held: false, resources: [] }] });
    renderApp(`${PATH}?log=l1`);
    expect(
      await screen.findByText(/The file is no longer in memory/),
    ).toBeInTheDocument();
  });
});

describe("System records pieces", () => {
  it("lists each log with status, window, cases and events", () => {
    render(
      <LogList logs={[IMPORTED, HELD]} onOpen={vi.fn()} onDelete={vi.fn()} />,
    );
    const report = IMPORTED_REPORT;
    expect(
      screen.getByText(
        new RegExp(`${report.cases} cases · ${report.rows_kept} events`),
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Uploaded: map the columns")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: `Continue ${HELD.name}` }),
    ).toBeInTheDocument();
  });

  it("shows a refusal with how to fix the extract", () => {
    const report = {
      ...HELD_REPORT,
      refused: true,
      missing_columns: ["timestamp"],
      refusal:
        "The extract has no column for: timestamp. Map one, or ask for a new extract.",
    };
    render(<ValidationReportView report={report} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("The import would be refused");
    expect(alert).toHaveTextContent(
      "The extract has no column for: timestamp.",
    );
    expect(alert).toHaveTextContent(
      "How to fix it: Map the column that holds it",
    );
  });

  it("says when there is no user ID column to map", () => {
    render(
      <RoleMapTable
        resources={[]}
        roles={ROLES}
        value={{}}
        onChange={vi.fn()}
      />,
    );
    expect(
      screen.getByText(
        "The file has no user ID column, so there is nothing to map.",
      ),
    ).toBeInTheDocument();
  });
});

// --- R7b: matching activities to map steps, Ask Claude, the Metrics tab ------------------------

const ALIGNMENT: Alignment = { ...SYSTEM.alignment, log_id: "l2" };
const GRAPH = {
  elements: [
    {
      id: "s0",
      kind: "start",
      label: "Flight closes",
      review_status: "unreviewed",
    },
    ...ALIGNMENT.rows
      .filter((r) => r.element_id)
      .map((r) => ({
        id: r.element_id,
        kind: "activity",
        label: r.element_label,
        review_status: "unreviewed",
      }))
      .filter((e, n, all) => all.findIndex((x) => x.id === e.id) === n),
    {
      id: "x1",
      kind: "activity",
      label: "Rejected step",
      review_status: "rejected",
    },
  ],
  edges: [],
};
const LOG_PATH = `${PATH}?log=l2`;

function matchingApi(extra: Record<string, Handler> = {}) {
  let alignment = ALIGNMENT;
  return systemApi({
    logs: [IMPORTED],
    extra: {
      "GET /api/event-logs/l2/alignment": () => ({ body: alignment }),
      "PUT /api/event-logs/l2/alignment": () => {
        alignment = {
          ...alignment,
          summary: {
            ...alignment.summary,
            waiting: alignment.summary.waiting - 1,
          },
        };
        return { body: alignment };
      },
      [`GET /api/versions/${ALIGNMENT.version_id}/graph`]: () => ({
        body: GRAPH,
      }),
      "GET /api/event-logs/l2/metrics": (_body, url) => {
        const scope = new URL(url, "http://x").searchParams.get(
          "scope",
        ) as MetricScope;
        return { body: SYSTEM.metrics[scope] };
      },
      ...extra,
    },
  });
}

const putRows = (calls: { key: string; body: unknown }[]) =>
  calls
    .filter((c) => c.key === "PUT /api/event-logs/l2/alignment")
    .map((c) => (c.body as { rows: unknown[] }).rows);

describe("System records: matching activities to map steps (R7b)", () => {
  it("lists each activity with its step, reason and status, and the steps with no record", async () => {
    matchingApi();
    const view = renderApp(LOG_PATH);
    const table = await screen.findByRole("table", {
      name: "System activities",
    });
    expect(
      screen.getByText(
        "7 activities: 6 matched, 1 hidden work. 5 steps with no system record. 5 waiting for your decision.",
      ),
    ).toBeInTheDocument();
    const revised = within(table).getByRole("row", { name: /^Plan revised/ });
    expect(revised).toHaveTextContent("Draft load plan");
    expect(revised).toHaveTextContent("Proposed match: waiting");
    expect(revised).toHaveTextContent(
      "Suggested by the app. Same words: plan. Same role: Load controller.",
    );
    expect(
      within(table).getByRole("row", { name: /^Manual weight override/ }),
    ).toHaveTextContent("Hidden work (no step)");
    const offline = screen.getByRole("table", {
      name: "Steps with no system record",
    });
    expect(
      within(offline).getByRole("row", { name: /^Read report at aircraft/ }),
    ).toHaveTextContent("Decided");
    expect(await seriousViolations(view.container)).toEqual([]);
  });

  it("saves each decision as one row: confirm, another step, hidden work, no record", async () => {
    const { calls } = matchingApi();
    renderApp(LOG_PATH);
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Confirm Plan revised as Draft load plan",
      }),
    );
    await waitFor(() => expect(putRows(calls)).toHaveLength(1));
    const ids = Object.fromEntries(GRAPH.elements.map((e) => [e.label, e.id]));
    expect(putRows(calls)[0]).toEqual([
      {
        activity: "Plan revised",
        element_id: ids["Draft load plan"],
        status: "confirmed",
      },
    ]);

    fireEvent.click(
      screen.getByRole("button", {
        name: "Choose another step for Manual weight override",
      }),
    );
    const choose = screen.getByLabelText("Step for Manual weight override");
    const offered = within(choose)
      .getAllByRole("option")
      .map((o) => o.textContent);
    expect(offered).not.toContain("Flight closes"); // start and end are not steps
    expect(offered).not.toContain("Rejected step");
    fireEvent.change(choose, { target: { value: ids["Approve deviation"] } });
    fireEvent.click(screen.getByRole("button", { name: "Match to this step" }));
    await waitFor(() => expect(putRows(calls)).toHaveLength(2));
    expect(putRows(calls)[1]).toEqual([
      {
        activity: "Manual weight override",
        element_id: ids["Approve deviation"],
        status: "confirmed",
      },
    ]);

    fireEvent.click(
      screen.getByRole("button", { name: "Mark Plan created as hidden work" }),
    );
    await waitFor(() => expect(putRows(calls)).toHaveLength(3));
    expect(putRows(calls)[2]).toEqual([
      { activity: "Plan created", element_id: null, status: "hidden_work" },
    ]);

    fireEvent.click(
      screen.getByRole("button", {
        name: "Confirm Approve load plan has no system record",
      }),
    );
    await waitFor(() => expect(putRows(calls)).toHaveLength(4));
    expect(putRows(calls)[3]).toEqual([
      {
        activity: "",
        element_id: ids["Approve load plan"],
        status: "no_system_record",
      },
    ]);
    expect(
      (
        await screen.findAllByText(
          /Decision saved\. The map uses confirmed matches only\./,
        )
      ).length,
    ).toBeGreaterThan(0);
  });

  it("shows the backend's reason when a decision is refused", async () => {
    matchingApi({
      "PUT /api/event-logs/l2/alignment": () => ({
        status: 422,
        body: { error: { code: "VALIDATION", details: { field: "rows" },
          message: "Issue load sheet has a system record: Load sheet issued is matched to it." } }, // prettier-ignore
      }),
    });
    renderApp(LOG_PATH);
    fireEvent.click(
      await screen.findByRole("button", {
        name: "Confirm Plan revised as Draft load plan",
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Issue load sheet has a system record",
    );
  });

  it("asks for a draft map first when there is none", async () => {
    matchingApi({
      "GET /api/event-logs/l2/alignment": () => ({
        status: 409,
        body: { error: { code: "NO_MAP", details: {},
          message: "Draft the map first: the log's activities are matched to its steps." } }, // prettier-ignore
      }),
    });
    renderApp(LOG_PATH);
    expect(await screen.findByText(/Draft the map first/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Go to Draft" })).toHaveAttribute(
      "href",
      "/engagements/e1/draft",
    );
  });

  it("asks Claude for suggestions as a job and says what came back", async () => {
    const { calls } = matchingApi({
      "POST /api/event-logs/l2/alignment/suggest": () => ({
        status: 202,
        body: { job_id: "j2", log_id: "l2" },
      }),
      "GET /api/jobs/j2": () => ({
        body: {
          ...JOB,
          id: "j2",
          type: "event_log_alignment",
          status: "done",
          message: "Claude suggested 1 match.",
        },
      }),
    });
    renderApp(LOG_PATH);
    fireEvent.click(
      await screen.findByRole("button", { name: "Ask Claude for suggestions" }),
    );
    expect(
      await screen.findByText(
        /Claude suggested 1 match\. Suggestions are proposals/,
      ),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(
        calls.filter((c) => c.key === "GET /api/event-logs/l2/alignment")
          .length,
      ).toBeGreaterThan(1),
    );
  });

  it("says when there is nothing for Claude to suggest", async () => {
    matchingApi({
      "POST /api/event-logs/l2/alignment/suggest": () => ({
        status: 409,
        body: {
          error: {
            code: "NOTHING_TO_SUGGEST",
            details: {},
            message: "Every activity already has a match or a decision.",
          },
        },
      }),
    });
    renderApp(LOG_PATH);
    fireEvent.click(
      await screen.findByRole("button", { name: "Ask Claude for suggestions" }),
    );
    expect(
      await screen.findByText(
        "Every activity already has a match or a decision.",
      ),
    ).toBeInTheDocument();
  });
});

describe("System records: the Metrics tab (R7b)", () => {
  it("shows volume, waits, rework, handoffs, variants with coverage and roles, never a person", async () => {
    matchingApi();
    const view = renderApp(LOG_PATH);
    fireEvent.click(await screen.findByRole("tab", { name: "Metrics" }));
    const all = await screen.findByRole("region", { name: "All cases" });
    expect(all).toHaveTextContent("Cases200");
    expect(all).toHaveTextContent("2 per case");
    expect(all).toHaveTextContent(
      "30% of cases don't follow the most common one",
    );
    const activities = screen.getByRole("region", {
      name: "Volume and waits per activity",
    });
    expect(
      within(activities).getByRole("row", { name: /^Plan created/ }),
    ).toBeInTheDocument();
    const variants = screen.getByRole("region", { name: "Variants (top 10)" });
    expect(
      within(variants).getByRole("row", { name: /^1 / }),
    ).toHaveTextContent("71%");
    expect(variants).toHaveTextContent(/These variants cover \d+% of cases\./);
    expect(
      screen.getByRole("region", {
        name: "Handoffs and waits between activities",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Per role" })).toHaveTextContent(
      "Load controller",
    );
    expect(document.body.textContent).not.toMatch(/\bLC\d+\b|\bU[12]\b/);
    expect(await seriousViolations(view.container)).toEqual([]);
  });

  it("says how many groups were left out for having fewer than 5 cases", () => {
    const data = {
      ...(SYSTEM.metrics.activity as MetricsResponse<ActivityMetrics>),
      too_few: 2,
    };
    render(<ActivityTable data={data} />);
    expect(
      screen.getByText("2 activities not shown: fewer than 5 cases each."),
    ).toBeInTheDocument();
  });
});
