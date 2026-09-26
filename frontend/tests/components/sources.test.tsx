import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Segment, Source } from "../../src/api/types";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

const PATH = "/engagements/e1/sources";

function source(id: string, filename: string, extra: Partial<Source> = {}): Source {
  return {
    id,
    engagement_id: "e1",
    kind: "sop",
    filename,
    format: filename.split(".").pop() ?? "",
    mime: "",
    version_date: "",
    owner: "",
    controlled_copy: false,
    text_status: "ready",
    error: "",
    segment_count: 2,
    ocr_pages: [],
    suggested_images: 0,
    created_at: "2026-09-26T09:00:00+00:00",
    ...extra,
  };
}

const SOP = source("s1", "sop_LC-07.docx", { version_date: "2026-03-01", owner: "Load Control" });
const TRANSCRIPT = source("s2", "interview_transcript.txt", {
  kind: "interview_transcript",
  text_status: "pending",
  segment_count: 0,
});
const BROKEN = source("s4", "old_scan.pdf", {
  kind: "manual",
  text_status: "failed",
  error: "The PDF could not be read. Check it opens on your computer, then upload it again.",
  segment_count: 0,
});
const MANUAL = source("s3", "manual_extract.pdf", { kind: "manual", ocr_pages: [2], suggested_images: 1 });

function segment(seq: number, anchor: string, text: string): Segment {
  return { id: `g${seq}`, seq, anchor, page: null, section: "", speaker_role: null, text, cited: false, instruction_like: false };
}

function sourcesApi(initial: Source[], extra: Parameters<typeof fakeApi>[0] = {}) {
  let list = [...initial];
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/sources": () => ({ body: list }),
    "GET /api/engagements/e1/roles": () => ({ body: [] }),
    "GET /api/engagements/e1/redaction-terms": () => ({ body: [] }),
    ...Object.fromEntries(
      initial.flatMap((s) => [
        [`GET /api/sources/${s.id}`, () => ({ body: list.find((x) => x.id === s.id) })],
        [
          `PATCH /api/sources/${s.id}`,
          (body: unknown) => {
            list = list.map((x) => (x.id === s.id ? { ...x, ...(body as object) } : x));
            return { body: list.find((x) => x.id === s.id) };
          },
        ],
        [
          `DELETE /api/sources/${s.id}`,
          () => {
            list = list.filter((x) => x.id !== s.id);
            return { status: 204, body: null };
          },
        ],
      ]),
    ),
    "POST /api/engagements/e1/sources": (body) => {
      const file = (body as FormData).get("file") as File;
      const created = source(`n${list.length + 1}`, file.name);
      list = [...list, created];
      return { status: 201, body: created };
    },
    ...extra,
  });
}

const fileInput = () => screen.getByTestId("source-file-input");

describe("Sources: upload", () => {
  it("starts with a drop zone naming the accepted formats and one sentence on what to add", async () => {
    sourcesApi([]);
    renderApp(PATH);
    expect(await screen.findByRole("heading", { level: 1, name: "Sources" })).toBeInTheDocument();
    expect(screen.getByText(".docx .pdf .txt .vtt .srt")).toBeInTheDocument();
    expect(await screen.findByText(/Add the interview transcript and at least one SOP to start/)).toBeInTheDocument();
  });

  it("uploads chosen files one by one and adds them to the registry", async () => {
    const { calls } = sourcesApi([]);
    renderApp(PATH);
    await screen.findByText(/Add the interview transcript/);
    fireEvent.change(fileInput(), {
      target: { files: [new File(["a"], "sop_LC-07.docx"), new File(["b"], "notes.txt")] },
    });
    expect(await screen.findByText("2 files uploaded.")).toBeInTheDocument();
    const uploads = calls.filter((c) => c.key === "POST /api/engagements/e1/sources");
    expect(uploads.map((c) => ((c.body as FormData).get("file") as File).name)).toEqual(["sop_LC-07.docx", "notes.txt"]);
    expect(await screen.findByRole("button", { name: "notes.txt" })).toBeInTheDocument();
  });

  it("accepts files dropped on the drop zone", async () => {
    const { calls } = sourcesApi([]);
    renderApp(PATH);
    const zone = (await screen.findByText("Drop files here")).parentElement as HTMLElement;
    fireEvent.dragOver(zone);
    fireEvent.drop(zone, { dataTransfer: { files: [new File(["a"], "manual.pdf")] } });
    expect(await screen.findByText("1 file uploaded.")).toBeInTheDocument();
    expect(calls.some((c) => c.key === "POST /api/engagements/e1/sources")).toBe(true);
  });

  it("refuses unsupported files before uploading, naming the accepted formats", async () => {
    const { calls } = sourcesApi([]);
    renderApp(PATH);
    await screen.findByText(/Add the interview transcript/);
    fireEvent.change(fileInput(), { target: { files: [new File(["x"], "photo.png")] } });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Not uploaded. Process Map Studio reads .docx, .pdf, .txt, .vtt and .srt files.");
    expect(screen.getByText("photo.png")).toBeInTheDocument();
    expect(calls.some((c) => c.key.startsWith("POST"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Dismiss the message about photo.png" }));
    expect(screen.queryByText("photo.png")).not.toBeInTheDocument();
  });

  it("shows the server's reason when an upload is refused", async () => {
    sourcesApi([], {
      "POST /api/engagements/e1/sources": () => ({
        status: 422,
        body: { error: { code: "VALIDATION", message: "The file is empty.", details: { field: "file" } } },
      }),
    });
    renderApp(PATH);
    await screen.findByText(/Add the interview transcript/);
    fireEvent.change(fileInput(), { target: { files: [new File([""], "empty.docx")] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Not uploaded. The file is empty.");
  });
});

describe("Sources: registry", () => {
  it("lists each source with kind, format, date, owner, controlled copy, status and reason", async () => {
    sourcesApi([SOP, TRANSCRIPT, BROKEN]);
    renderApp(PATH);
    const table = await screen.findByRole("table", { name: "Sources for this engagement" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(3);
    expect(within(rows[0] as HTMLElement).getByRole("combobox", { name: "Kind of sop_LC-07.docx" })).toHaveValue("sop");
    expect(within(rows[0] as HTMLElement).getByLabelText("Version date of sop_LC-07.docx")).toHaveValue("2026-03-01");
    expect(within(rows[0] as HTMLElement).getByLabelText("Owner of sop_LC-07.docx")).toHaveValue("Load Control");
    expect(rows[0]).toHaveTextContent("Ready");
    expect(rows[1]).toHaveTextContent("Reading…");
    expect(rows[2]).toHaveTextContent("Failed");
    expect(rows[2]).toHaveTextContent("The PDF could not be read.");
  });

  it("saves kind, owner, date and controlled copy straight from the table", async () => {
    const { calls } = sourcesApi([SOP]);
    renderApp(PATH);
    fireEvent.change(await screen.findByRole("combobox", { name: "Kind of sop_LC-07.docx" }), {
      target: { value: "manual" },
    });
    await waitFor(() =>
      expect(calls.filter((c) => c.key === "PATCH /api/sources/s1").map((c) => c.body)).toEqual([{ kind: "manual" }]),
    );
    const owner = screen.getByLabelText("Owner of sop_LC-07.docx");
    fireEvent.change(owner, { target: { value: " Ramp  " } });
    fireEvent.blur(owner);
    const date = screen.getByLabelText("Version date of sop_LC-07.docx");
    fireEvent.change(date, { target: { value: "2026-04-02" } });
    fireEvent.blur(date);
    fireEvent.click(screen.getByRole("checkbox", { name: "sop_LC-07.docx is a controlled copy" }));
    await waitFor(() =>
      expect(calls.filter((c) => c.key === "PATCH /api/sources/s1").map((c) => c.body)).toEqual([
        { kind: "manual" },
        { owner: "Ramp" },
        { version_date: "2026-04-02" },
        { controlled_copy: true },
      ]),
    );
  });

  it("keeps looking while a file is being read, then shows it as ready", async () => {
    let reads = 0;
    sourcesApi([], {
      "GET /api/engagements/e1/sources": () => {
        reads += 1;
        return { body: [reads < 2 ? TRANSCRIPT : { ...TRANSCRIPT, text_status: "ready", segment_count: 9 }] };
      },
    });
    renderApp(PATH);
    expect(await screen.findByText("Reading…")).toBeInTheDocument();
    expect(await screen.findByText("Ready", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(reads).toBeGreaterThanOrEqual(2);
  });

  it("does not save a field that didn't change", async () => {
    const { calls } = sourcesApi([SOP]);
    renderApp(PATH);
    const owner = await screen.findByLabelText("Owner of sop_LC-07.docx");
    fireEvent.focus(owner);
    fireEvent.blur(owner);
    expect(calls.some((c) => c.key.startsWith("PATCH"))).toBe(false);
  });

  it("asks before deleting, naming what goes", async () => {
    const { calls } = sourcesApi([SOP]);
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("button", { name: "Delete sop_LC-07.docx" }));
    const dialog = screen.getByRole("dialog", { name: "Delete sop_LC-07.docx?" });
    expect(dialog).toHaveTextContent("its 2 passages");
    expect(dialog).toHaveTextContent("can't be undone");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete source" }));
    expect(await screen.findByText("sop_LC-07.docx deleted.")).toBeInTheDocument();
    expect(calls.some((c) => c.key === "DELETE /api/sources/s1")).toBe(true);
    expect(await screen.findByText(/Add the interview transcript/)).toBeInTheDocument();
  });

  it("shows exactly what the draft still needs, or that it is ready", async () => {
    sourcesApi([SOP]);
    renderApp(PATH);
    expect(await screen.findByText("Add an interview transcript")).toBeInTheDocument();
    expect(screen.getByText("Before drafting:")).toBeInTheDocument();
  });

  it("says Ready to draft when nothing is missing", async () => {
    sourcesApi([SOP], {
      "GET /api/engagements/e1/readiness": () => ({ body: { ...READINESS, missing: [], ready_to_draft: true } }),
    });
    renderApp(PATH);
    expect(await screen.findByText("Ready to draft.")).toBeInTheDocument();
  });

  it("has no serious or critical accessibility violations", async () => {
    sourcesApi([SOP, TRANSCRIPT]);
    const { container } = renderApp(PATH);
    await screen.findByRole("table", { name: "Sources for this engagement" });
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("Sources: viewer", () => {
  it("opens from the file name and shows anchored passages", async () => {
    sourcesApi([SOP], {
      "GET /api/sources/s1/segments": () => ({
        body: {
          segments: [segment(1, "§3.1", "§3.1 The Load Controller shall check the load plan."), segment(2, "¶ 2", "Second.")],
          total: 2,
          page: 1,
          pages: 1,
          coverage_pct: null,
        },
      }),
    });
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("button", { name: "sop_LC-07.docx" }));
    const viewer = await screen.findByRole("region", { name: "sop_LC-07.docx" });
    const passages = await within(viewer).findByRole("list", { name: "Passages" });
    expect(within(passages).getAllByRole("listitem")[0]).toHaveTextContent("§3.1§3.1 The Load Controller shall");
    expect(viewer).toHaveTextContent("Speaker names are replaced by roles.");
    fireEvent.click(within(viewer).getByRole("button", { name: "Close viewer" }));
    expect(screen.queryByRole("region", { name: "sop_LC-07.docx" })).not.toBeInTheDocument();
  });

  it("opens from a row click and notes scanned pages and suggested images", async () => {
    sourcesApi([MANUAL], {
      "GET /api/sources/s3/segments": () => ({
        body: { segments: [segment(1, "p. 1", "Text")], total: 1, page: 1, pages: 1, coverage_pct: null },
      }),
    });
    renderApp(PATH);
    const cell = await screen.findByText("pdf");
    fireEvent.click(cell);
    const viewer = await screen.findByRole("region", { name: "manual_extract.pdf" });
    expect(await within(viewer).findByText(/almost no text \(probably scanned\)/)).toHaveTextContent("Page 2 has");
    expect(viewer).toHaveTextContent("1 image found in this file is kept as a suggestion");
  });

  it("does not open the viewer when editing a field in the row", async () => {
    sourcesApi([SOP]);
    renderApp(PATH);
    fireEvent.click(await screen.findByLabelText("Owner of sop_LC-07.docx"));
    expect(screen.queryByRole("region", { name: "sop_LC-07.docx" })).not.toBeInTheDocument();
  });

  it("loads more passages on request", async () => {
    let calls = 0;
    sourcesApi([SOP], {
      "GET /api/sources/s1/segments": () => {
        calls += 1;
        return calls === 1
          ? { body: { segments: [segment(1, "¶ 1", "First")], total: 2, page: 1, pages: 2, coverage_pct: null } }
          : { body: { segments: [segment(2, "¶ 2", "Second")], total: 2, page: 2, pages: 2, coverage_pct: null } };
      },
    });
    renderApp(`${PATH}?source=s1`);
    fireEvent.click(await screen.findByRole("button", { name: "Show more passages (1 of 2 shown)" }));
    expect(await screen.findByText("Second")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show more passages/ })).not.toBeInTheDocument();
  });
});
