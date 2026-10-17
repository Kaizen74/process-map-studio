import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CaseKeyMapList } from "../../src/components/system";
import { shortDuration, type CaseKeyMap, type EventLog } from "../../src/lib/systemRecords";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, SETTINGS, fakeApi, renderApp } from "../renderApp";

// R11c (PRD §3.13.1; API_CONTRACT.md → Case-key maps): linking two imported logs, on the shapes
// the backend really sends (backend/tests/unit/test_case_key_maps_api.py).

const SAMPLE = JSON.parse(readFileSync(join(__dirname, "..", "fixtures", "case_key_maps.json"), "utf-8")) as {
  logs: EventLog[];
  maps: CaseKeyMap[];
};
const [MAP] = SAMPLE.maps as [CaseKeyMap];
const [DCS, RAMP] = SAMPLE.logs as [EventLog, EventLog];

afterEach(() => vi.unstubAllGlobals());

describe("Linked logs list (R11c)", () => {
  it("says what each link found and the end-to-end time, measured", async () => {
    const onRemove = vi.fn();
    const { container } = render(<CaseKeyMapList maps={SAMPLE.maps} busy={false} onRemove={onRemove} />);
    const row = within(screen.getByRole("list", { name: "Linked logs" })).getByRole("listitem");
    expect(row).toHaveTextContent("DCS extract and Ramp log");
    expect(row).toHaveTextContent("150 pairs in the file: 150 found in DCS extract, 150 in Ramp log, 150 cases in both.");
    const spread = MAP.end_to_end as NonNullable<CaseKeyMap["end_to_end"]>;
    expect(row).toHaveTextContent(
      `End to end across both systems: median ${shortDuration(spread.median_min)}, 90th percentile ${shortDuration(spread.p90_min)} (150 cases, measured; work and wait).`,
    );
    fireEvent.click(within(row).getByRole("button", { name: "Unlink DCS extract and Ramp log" }));
    expect(onRemove).toHaveBeenCalledWith(MAP);
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("shows no time under 5 linked cases, and says when nothing is linked", () => {
    const few = { ...MAP, linked_cases: 4, end_to_end: null };
    const { rerender } = render(<CaseKeyMapList maps={[few]} busy={false} onRemove={vi.fn()} />);
    expect(screen.getByText("Too few linked cases to show a time: fewer than 5.")).toBeInTheDocument();
    expect(screen.queryByText(/End to end/)).toBeNull();
    rerender(<CaseKeyMapList maps={[]} busy={false} onRemove={vi.fn()} />);
    expect(screen.getByText("No logs are linked yet. Each log is analysed on its own.")).toBeInTheDocument();
  });
});

describe("System records screen: Linked logs (R11c)", () => {
  function backend(logs: EventLog[]) {
    let maps: CaseKeyMap[] = [];
    const urls: string[] = [];
    const api = fakeApi({
      "GET /api/settings": () => ({ body: { ...SETTINGS, system_records_enabled: true } }),
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/event-logs": () => ({ body: logs }),
      "GET /api/engagements/e1/case-key-maps": () => ({ body: maps }),
      "POST /api/engagements/e1/case-key-maps": () => {
        maps = [MAP];
        return { status: 201, body: MAP };
      },
      "DELETE /api/engagements/e1/case-key-maps": (_body, url) => {
        urls.push(url ?? "");
        maps = [];
        return { status: 204, body: null };
      },
    });
    return { ...api, urls };
  }

  it("appears once two logs are imported, links them with a file and unlinks them", async () => {
    const { calls, urls } = backend(SAMPLE.logs);
    const { container } = renderApp("/engagements/e1/system-records");
    const card = (await screen.findByRole("heading", { name: "Linked logs" })).closest("section, div.card") as HTMLElement;
    expect(await within(card).findByText("No logs are linked yet. Each log is analysed on its own.")).toBeInTheDocument();
    expect(within(card).getByLabelText("First log (first column)")).toHaveValue(DCS.id);
    expect(within(card).getByLabelText("Second log (second column)")).toHaveValue(RAMP.id);
    fireEvent.click(within(card).getByRole("button", { name: "Link logs" }));
    expect(await within(card).findByRole("alert")).toHaveTextContent("Choose the file of case IDs first.");
    fireEvent.change(screen.getByTestId("case-key-file-input"), {
      target: { files: [new File(["DCS,Ramp\nFL1000,R-1000\n"], "keys.csv", { type: "text/csv" })] },
    });
    fireEvent.click(within(card).getByRole("button", { name: "Link logs" }));
    expect(await screen.findByText("DCS extract and Ramp log linked.")).toBeInTheDocument();
    const form = calls.find((c) => c.key === "POST /api/engagements/e1/case-key-maps")?.body as FormData;
    expect([(form.get("file") as File).name, form.get("from_log_id"), form.get("to_log_id")]).toEqual([
      "keys.csv",
      DCS.id,
      RAMP.id,
    ]);
    expect(await within(card).findByText(/End to end across both systems/)).toBeInTheDocument();
    expect(await seriousViolations(container)).toEqual([]);
    fireEvent.click(within(card).getByRole("button", { name: "Unlink DCS extract and Ramp log" }));
    expect(await screen.findByText("DCS extract and Ramp log unlinked.")).toBeInTheDocument();
    await waitFor(() => expect(urls[0]).toContain(`from_log_id=${DCS.id}&to_log_id=${RAMP.id}`));
  });

  it("refuses the same log twice before sending anything", async () => {
    const { calls } = backend(SAMPLE.logs);
    renderApp("/engagements/e1/system-records");
    const second = await screen.findByLabelText("Second log (second column)");
    fireEvent.change(second, { target: { value: DCS.id } });
    fireEvent.click(screen.getByRole("button", { name: "Link logs" }));
    expect(await screen.findByText("Choose two different logs.")).toBeInTheDocument();
    expect(calls.some((c) => c.key === "POST /api/engagements/e1/case-key-maps")).toBe(false);
  });

  it("is not shown with only one imported log", async () => {
    backend([DCS]);
    renderApp("/engagements/e1/system-records");
    expect(await screen.findByRole("button", { name: `Open ${DCS.name}` })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Linked logs" })).toBeNull();
  });
});
