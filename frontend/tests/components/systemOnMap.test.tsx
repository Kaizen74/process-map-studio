import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SystemDataSection } from "../../src/components/panel";
import { VariantsTab } from "../../src/components/tabs";
import { hiddenWorkStepForm, newStepBody, validateNewStep } from "../../src/lib/addStep";
import { ALL_LENSES, LENSES, lensLine, lensesFor } from "../../src/lib/lens";
import { shortcutFor, shortcutList } from "../../src/lib/shortcuts";
import {
  shortDuration,
  volumeLines,
  volumeText,
  type SystemTrace,
  type SystemVariants,
} from "../../src/lib/systemRecords";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp } from "../renderApp";
import { SAMPLE, elementByLabel, graphFor, layoutFor } from "../sampleMap";

// R8 (PRD §5.5, §5.6, §5.7.7 4e; criterion 89): the Volume and wait lens, panel 4e and the
// Variants tab with Hidden work and Add as step, on the shapes the backend really sends.

const SYSTEM = JSON.parse(readFileSync(join(__dirname, "..", "fixtures", "system_records.json"), "utf-8")) as {
  system_traces: SystemTrace[];
  system_variants: SystemVariants;
};
const VID = SAMPLE.graph.version.id;
/** The backend sample's steps carry their own IDs; put them on the sample map's steps by label. */
const idOf = (label: string) => elementByLabel(label).id;
const TRACES: SystemTrace[] = SYSTEM.system_traces.map((t) => ({ ...t, element_id: idOf(t.label) }));
const VARIANTS: SystemVariants = {
  ...SYSTEM.system_variants,
  logs: SYSTEM.system_variants.logs.map((log) => ({
    ...log,
    variants: log.variants.map((v) => ({
      ...v,
      path: v.path.map((p) => ({ ...p, element_id: p.element_id ? idOf(p.label) : null })),
    })),
    hidden_work: log.hidden_work.map((h) => ({
      ...h,
      role_id: elementByLabel(h.after_label).lane_role_id,
      after_element_id: h.after_label ? idOf(h.after_label) : null,
      before_element_id: h.before_label ? idOf(h.before_label) : null,
    })),
  })),
};
const trace = (label: string) => TRACES.find((t) => t.label === label) as SystemTrace;

describe("the Volume and wait lens (R8)", () => {
  it("is offered only while System records is on, as the seventh lens and key 7", () => {
    expect(lensesFor(false)).toEqual(LENSES);
    expect(lensesFor(true).map((l) => l.label).at(-1)).toBe("Volume and wait");
    expect(shortcutFor({ key: "7", target: null, ctrlKey: false, altKey: false, metaKey: false })).toBeNull();
    expect(shortcutFor({ key: "7", target: null, ctrlKey: false, altKey: false, metaKey: false }, ALL_LENSES)).toEqual({
      kind: "lens",
      lens: "volume",
    });
    expect(shortcutList(ALL_LENSES).find((s) => s.keys === "1 – 7")?.action).toMatch(/Volume and wait$/);
  });

  it("says cases per month and the median wait, in a few characters", () => {
    expect(volumeText(trace("Load and return LIR"))).toBe("108 cases/mo · wait 39 min (median)");
    expect(volumeText(trace("Draft load plan"))).toBe("108 cases/mo"); // the case starts here
    expect(volumeText({ ...trace("Draft load plan"), cases_per_month: 1240, wait_before: { median_min: 240, p90_min: 300, n: 9 } })).toBe(
      "1,240 cases/mo · wait 4 h (median)",
    );
    expect([shortDuration(14.4), shortDuration(90), shortDuration(720)]).toEqual(["14 min", "1.5 h", "12 h"]);
  });

  it("shows the line, 'too few cases' or 'No system data', and nothing until the figures arrive", () => {
    const lines = volumeLines(TRACES, [idOf("Approve deviation")]);
    const report = elementByLabel("Load and return LIR");
    expect(lensLine(report, "volume")).toEqual({ kind: "none" });
    expect(lensLine(report, "volume", 0, "done", undefined, lines)).toEqual({
      kind: "text", text: "108 cases/mo · wait 39 min (median)", danger: false, muted: false,
    }); // prettier-ignore
    expect(lensLine(elementByLabel("Approve deviation"), "volume", 0, "done", undefined, lines)).toMatchObject({
      text: "too few cases",
      muted: true,
    });
    expect(lensLine(elementByLabel("Busy wave?"), "volume", 0, "done", undefined, lines)).toMatchObject({
      text: "No system data",
      muted: true,
    });
  });
});

describe("panel section 4e, System data (R8)", () => {
  it("shows volume, cases, wait and work, rework, variants, the window and the time comparison", async () => {
    const report = elementByLabel("Load and return LIR");
    const { container } = render(<SystemDataSection traces={[trace("Load and return LIR")]} element={report} />);
    const section = screen.getByRole("region", { name: "System data" });
    expect(section).toHaveTextContent("DCS extract (DCS)");
    expect(section).toHaveTextContent("108 cases/mo (25 a week)");
    expect(section).toHaveTextContent("Wait beforemedian 39.1 min · 90th percentile 51.2 min");
    expect(section).toHaveTextContent("Workmedian 13.4 min");
    expect(section).toHaveTextContent(/of the top variants, \d+% of cases/);
    expect(section).toHaveTextContent(/SME estimate .+ · measured median 13\.4 min/);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("says when a matched step has too few cases, and nothing when it has no match", () => {
    const { rerender } = render(<SystemDataSection traces={[]} element={elementByLabel("Busy wave?")} tooFew />);
    expect(screen.getByText(/too few cases to show figures/)).toBeInTheDocument();
    rerender(<SystemDataSection traces={[]} element={elementByLabel("Busy wave?")} />);
    expect(screen.queryByRole("region", { name: "System data" })).toBeNull();
  });
});

describe("the Variants tab and Hidden work (R8)", () => {
  it("lists each variant with its path and whether it fits each view, in words", async () => {
    const onSelect = vi.fn();
    const { container } = render(<VariantsTab data={VARIANTS} onSelect={onSelect} onAddHidden={vi.fn()} />);
    const first = screen.getByRole("listitem", { name: "Variant 1" });
    expect(first).toHaveTextContent("Variant 1 · 141 cases (71%)");
    expect(within(first).getByText("Fits As done")).toBeInTheDocument();
    fireEvent.click(within(first).getByRole("button", { name: "Draft load plan" }));
    expect(onSelect).toHaveBeenCalledWith(idOf("Draft load plan"));
    expect(screen.getAllByText("Doesn't fit As done").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Manual weight override is hidden work: no step on the map.").length).toBeGreaterThan(0);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("offers Add as step for hidden work only where the version can change", () => {
    const onAdd = vi.fn();
    const { rerender } = render(<VariantsTab data={VARIANTS} onSelect={vi.fn()} onAddHidden={onAdd} />);
    const list = screen.getByRole("region", { name: "Hidden work in DCS extract" });
    expect(list).toHaveTextContent("23 cases (12%), mostly after Deviation in limits?, before Issue load sheet");
    fireEvent.click(within(list).getByRole("button", { name: "Add Manual weight override as a step" }));
    expect(onAdd).toHaveBeenCalledWith(VARIANTS.logs[0]?.hidden_work[0], VARIANTS.logs[0]);
    rerender(<VariantsTab data={VARIANTS} onSelect={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /as a step/ })).toBeNull();
  });

  it("fills in the new step from the hidden work, with the system record as its evidence", () => {
    const log = VARIANTS.logs[0] as SystemVariants["logs"][number];
    const item = log.hidden_work[0] as SystemVariants["logs"][number]["hidden_work"][number];
    const form = hiddenWorkStepForm(SAMPLE.graph, item, log, "start");
    expect([form.label, form.after_element_id, form.provenance]).toEqual([
      "Manual weight override",
      idOf("Deviation in limits?"),
      "O",
    ]);
    expect(validateNewStep(form)).toEqual({}); // no passage needed: the system record is the evidence
    expect(newStepBody(form)).toMatchObject({
      provenance: "O",
      segment_ids: [],
      system_activity: { log_id: log.log_id, activity: "Manual weight override" },
    });
    expect(validateNewStep({ ...form, system_activity: null }).segment_ids).toBe("Pick the passage this step comes from.");
  });
});

describe("Review with System records on (R8)", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => vi.unstubAllGlobals());

  function backend(on: boolean) {
    return fakeApi({
      "GET /api/settings": () => ({ body: { ...SETTINGS, system_records_enabled: on } }),
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/event-logs": () => ({ body: [] }),
      "GET /api/engagements/e1/draft": () => ({
        body: { job: null, version: { id: VID, engagement_id: "e1", label: "v0.1", state: "draft",
          created_at: "2026-09-27T10:00:00+00:00" }, summary: null }, // prettier-ignore
      }),
      [`GET /api/versions/${VID}/graph`]: (_body, url) => ({ body: graphFor(url) }),
      [`GET /api/versions/${VID}/layout`]: (_body, url) => ({ body: layoutFor(url) }),
      [`GET /api/versions/${VID}/system-traces`]: () => ({ body: TRACES }),
      [`GET /api/versions/${VID}/system-variants`]: () => ({ body: VARIANTS }),
      ...Object.fromEntries(
        Object.entries(SAMPLE.elements).map(([id, element]) => [`GET /api/elements/${id}`, () => ({ body: element })]),
      ),
    });
  }

  it("while off: no Volume and wait lens, no Variants tab, and no system figures are asked for", async () => {
    const { calls } = backend(false);
    renderApp("/engagements/e1/review");
    const lenses = await screen.findByRole("radiogroup", { name: "Lens" });
    await waitFor(() => expect(calls.some((c) => c.key === "GET /api/settings")).toBe(true));
    expect(within(lenses).queryByRole("radio", { name: "Volume and wait" })).toBeNull();
    expect(screen.queryByRole("tab", { name: "Variants" })).toBeNull();
    expect(calls.some((c) => c.key.includes("/system-"))).toBe(false);
  });

  it("while on: the lens shows each step's line, the panel its System data, and the Variants tab adds hidden work", async () => {
    backend(true);
    const { container } = renderApp("/engagements/e1/review");
    const lenses = await screen.findByRole("radiogroup", { name: "Lens" });
    fireEvent.click(await within(lenses).findByRole("radio", { name: "Volume and wait" }));
    const lines = () => [...container.querySelectorAll(".map-lens")].map((l) => l.textContent);
    await waitFor(() => expect(lines()).toContain("108 cases/mo · wait 39 min (median)"));
    expect(lines()).toContain("No system data");
    expect(screen.getByRole("list", { name: "Lens key" })).toHaveTextContent("too few cases");
    expect(await seriousViolations(container)).toEqual([]);
    // Panel 4e.
    fireEvent.click(screen.getByRole("button", { name: /^Activity, Load and return LIR/ }));
    expect(await screen.findByRole("region", { name: "System data" })).toHaveTextContent("108 cases/mo");
    // The Variants tab: Add as step opens the add form filled in from the hidden work.
    fireEvent.click(screen.getByRole("tab", { name: "Variants" }));
    fireEvent.click(await screen.findByRole("button", { name: "Add Manual weight override as a step" }));
    const panel = await screen.findByRole("complementary", { name: "Add missing step" });
    expect(within(panel).getByRole("textbox", { name: "Name" })).toHaveValue("Manual weight override");
    expect(within(panel).getByText(/recorded in 23 cases/)).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
  });
});
