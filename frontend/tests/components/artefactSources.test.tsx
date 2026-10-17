import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RedactionTerm, Role, Segment, Source, Speaker } from "../../src/api/types";
import { ACCEPTED_FORMATS, BAD_FORMAT, kindLabel, uploadProblem } from "../../src/lib/sources";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";

// R11 (criterion 92; API_CONTRACT.md → Sources): working spreadsheets and email threads, on the
// shapes the backend really sends (backend/tests/unit/test_sources_artefacts_api.py).

interface Page {
  segments: Segment[];
  total: number;
  page: number;
  pages: number;
  coverage_pct: number | null;
}
const SAMPLE = JSON.parse(readFileSync(join(__dirname, "..", "fixtures", "artefact_sources.json"), "utf-8")) as {
  sources: Source[];
  sheet_segments: Page;
  email_segments: Page;
  email_speakers: Speaker[];
  redaction_terms: RedactionTerm[];
};
const [SHEET, EMAIL] = SAMPLE.sources as [Source, Source];
const ROLES: Role[] = [
  { id: "r1", engagement_id: "e1", name: "Load controller", aliases: [], is_system: false, lane_order: 1 },
];

afterEach(() => vi.unstubAllGlobals());

describe("accepted files (R11)", () => {
  it("takes spreadsheets and emails, and names every format when refusing one", () => {
    expect(ACCEPTED_FORMATS).toEqual([".docx", ".pdf", ".txt", ".vtt", ".srt", ".xlsx", ".csv", ".eml"]);
    for (const name of ["plan.xlsx", "Tracker.CSV", "thread.eml"]) expect(uploadProblem({ name, size: 10 })).toBeNull();
    for (const name of ["old.xls", "macro.xlsm", "outlook.msg"]) expect(uploadProblem({ name, size: 10 })).toBe(BAD_FORMAT);
    expect(BAD_FORMAT).toBe("Process Map Studio reads .docx, .pdf, .txt, .vtt, .srt, .xlsx, .csv and .eml files.");
    expect(kindLabel(SHEET.kind)).toBe("Working spreadsheet");
    expect(kindLabel(EMAIL.kind)).toBe("Email thread");
  });
});

describe("Sources screen with a spreadsheet and an email (R11)", () => {
  function backend() {
    let speakers = SAMPLE.email_speakers;
    return fakeApi({
      "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
      "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
      "GET /api/engagements/e1/sources": () => ({ body: SAMPLE.sources }),
      "GET /api/engagements/e1/roles": () => ({ body: ROLES }),
      "GET /api/engagements/e1/redaction-terms": () => ({ body: SAMPLE.redaction_terms }),
      [`GET /api/sources/${SHEET.id}`]: () => ({ body: SHEET }),
      [`GET /api/sources/${SHEET.id}/segments`]: () => ({ body: SAMPLE.sheet_segments }),
      [`GET /api/sources/${SHEET.id}/speakers`]: () => ({ body: [] }),
      [`GET /api/sources/${EMAIL.id}`]: () => ({ body: EMAIL }),
      [`GET /api/sources/${EMAIL.id}/segments`]: () => ({ body: SAMPLE.email_segments }),
      [`GET /api/sources/${EMAIL.id}/speakers`]: () => ({ body: speakers }),
      [`PUT /api/sources/${EMAIL.id}/speakers`]: (body) => {
        const mapping = body as Record<string, string | null>;
        speakers = speakers.map((s) => (s.label in mapping ? { ...s, role_id: mapping[s.label] ?? null } : s));
        return { body: speakers };
      },
    });
  }

  it("lists both with their kinds, and shows a spreadsheet's rows with sheet and cell anchors", async () => {
    backend();
    const { container } = renderApp(`/engagements/e1/sources?source=${SHEET.id}`);
    expect(await screen.findByText("Plan!A4")).toBeInTheDocument();
    expect(
      screen.getByText("Flight: SQ 221 | Step: Draft load plan | Owner: Load controller | Minutes: 20 | Date: 2026-03-02"),
    ).toBeInTheDocument();
    expect(screen.getByText("'Shift log'!A2")).toBeInTheDocument();
    expect(screen.getAllByText("Working spreadsheet").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Email thread").length).toBeGreaterThan(0);
    expect(screen.queryByText("Sender mapping")).toBeNull();
    expect(screen.queryByText("Speaker mapping")).toBeNull();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("an email shows names hidden, maps its senders (no interviewer) and lists names from the email", async () => {
    const { calls } = backend();
    const { container } = renderApp(`/engagements/e1/sources?source=${EMAIL.id}`);
    const table = await screen.findByRole("table", { name: "Senders in this email" });
    expect(screen.getByText("Sender mapping")).toBeInTheDocument();
    expect(within(table).getAllByRole("rowheader").map((th) => th.textContent)).toEqual(
      SAMPLE.email_speakers.map((s) => s.label),
    );
    const select = within(table).getByRole("combobox", { name: "Role for Tan, Wei Ming" });
    expect(within(select).queryByRole("option", { name: "Interviewer" })).toBeNull();
    expect(screen.getByText(/From: \[name\] · To: LC Ops Desk, \[name\]/)).toBeInTheDocument();
    fireEvent.change(select, { target: { value: "r1" } });
    fireEvent.click(screen.getByRole("button", { name: "Save senders" }));
    await waitFor(() =>
      expect(calls.find((c) => c.key === `PUT /api/sources/${EMAIL.id}/speakers`)?.body).toEqual({ "Tan, Wei Ming": "r1" }),
    );
    expect(await screen.findByText("1 sender saved.")).toBeInTheDocument();
    const names = screen.getByRole("list", { name: "Names hidden in this engagement" });
    expect(within(names).getAllByText("from an email")).toHaveLength(SAMPLE.redaction_terms.length);
    expect(await seriousViolations(container)).toEqual([]);
  });
});
