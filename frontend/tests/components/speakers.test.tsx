import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RedactionTerm, Role, Segment, Source, Speaker } from "../../src/api/types";
import { seriousViolations } from "../axe";
import { ENGAGEMENT, READINESS, fakeApi, renderApp } from "../renderApp";

afterEach(() => vi.unstubAllGlobals());

const NAME = "Priya Nair";
const PATH = "/engagements/e1/sources?source=t1";

const TRANSCRIPT: Source = {
  id: "t1",
  engagement_id: "e1",
  kind: "interview_transcript",
  filename: "[name] interview.txt",
  format: "txt",
  mime: "",
  version_date: "",
  owner: "",
  controlled_copy: false,
  text_status: "ready",
  error: "",
  segment_count: 3,
  ocr_pages: [],
  suggested_images: 0,
  created_at: "2026-09-26T09:00:00+00:00",
};

const ROLES: Role[] = [
  { id: "r1", engagement_id: "e1", name: "Load controller", aliases: [], is_system: false, lane_order: 1 },
];

function segment(seq: number, text: string, role: string | null): Segment {
  return {
    id: `g${seq}`,
    seq,
    anchor: `06:${String(37 + seq).padStart(2, "0")}`,
    page: null,
    section: "",
    speaker_role: role,
    text,
    cited: false,
    instruction_like: false,
  };
}

/** A fake backend that behaves like the real one: names only in the owner-only endpoints. */
function speakersApi(extra: Parameters<typeof fakeApi>[0] = {}) {
  let speakers: Speaker[] = [
    { label: "Interviewer", segment_count: 1, role_id: null, is_interviewer: false },
    { label: NAME, segment_count: 2, role_id: null, is_interviewer: false },
  ];
  let terms: RedactionTerm[] = [
    { id: "n1", engagement_id: "e1", term: NAME, replacement: "[name]", origin: "speaker_map" },
  ];
  const shown = () => terms[0]?.replacement ?? NAME;
  return fakeApi({
    "GET /api/engagements/e1": () => ({ body: ENGAGEMENT }),
    "GET /api/engagements/e1/readiness": () => ({ body: READINESS }),
    "GET /api/engagements/e1/sources": () => ({ body: [TRANSCRIPT] }),
    "GET /api/engagements/e1/roles": () => ({ body: ROLES }),
    "GET /api/sources/t1": () => ({ body: TRANSCRIPT }),
    "GET /api/sources/t1/segments": () => ({
      body: {
        segments: [
          segment(1, "Walk me through it.", speakers[0]?.is_interviewer ? "Interviewer" : null),
          segment(2, "I build the plan.", speakers[1]?.role_id ? "Load controller" : null),
          segment(3, `Thanks, ${shown()}.`, null),
        ],
        total: 3,
        page: 1,
        pages: 1,
        coverage_pct: null,
      },
    }),
    "GET /api/sources/t1/speakers": () => ({ body: speakers }),
    "PUT /api/sources/t1/speakers": (body) => {
      const mapping = body as Record<string, string | null>;
      speakers = speakers.map((s) =>
        s.label in mapping
          ? {
              ...s,
              role_id: mapping[s.label] === "interviewer" ? null : (mapping[s.label] ?? null),
              is_interviewer: mapping[s.label] === "interviewer",
            }
          : s,
      );
      if (mapping[NAME] === "r1") terms = terms.map((t) => ({ ...t, replacement: "Load controller" }));
      return { body: speakers };
    },
    "GET /api/engagements/e1/redaction-terms": () => ({ body: terms }),
    "POST /api/engagements/e1/redaction-terms": (body) => {
      const created = { id: "n2", engagement_id: "e1", origin: "manual", ...(body as { term: string; replacement: string }) };
      terms = [...terms, created];
      return { status: 201, body: created };
    },
    "DELETE /api/redaction-terms/n1": () => {
      terms = terms.filter((t) => t.id !== "n1");
      return { status: 204, body: null };
    },
    ...extra,
  });
}

/** Text of the page outside the owner-only places (PRD §6.2 item 8). */
function publicText(): string {
  const copy = document.body.cloneNode(true) as HTMLElement;
  copy.querySelectorAll("[data-owner-only]").forEach((el) => el.remove());
  return copy.textContent ?? "";
}

describe("Speaker mapping", () => {
  it("lists each speaker with a role choice, and saves only what changed", async () => {
    const { calls } = speakersApi();
    renderApp(PATH);
    const card = await screen.findByRole("region", { name: "Speaker mapping" });
    const table = await within(card).findByRole("table", { name: "Speakers in this transcript" });
    expect(within(table).getAllByRole("row").slice(1).map((r) => r.textContent)).toEqual([
      expect.stringContaining("Interviewer1"),
      expect.stringContaining(`${NAME}2`),
    ]);
    expect(within(card).getByText("2 speakers not mapped yet.")).toBeInTheDocument();

    fireEvent.change(within(card).getByRole("combobox", { name: "Role for Interviewer" }), {
      target: { value: "interviewer" },
    });
    fireEvent.change(within(card).getByRole("combobox", { name: `Role for ${NAME}` }), {
      target: { value: "r1" },
    });
    expect(within(card).getByText("Every speaker is mapped.")).toBeInTheDocument();
    fireEvent.click(within(card).getByRole("button", { name: "Save speakers" }));
    expect(await screen.findByText("2 speakers saved.")).toBeInTheDocument();
    expect(calls.find((c) => c.key === "PUT /api/sources/t1/speakers")?.body).toEqual({
      Interviewer: "interviewer",
      [NAME]: "r1",
    });
    const passages = await screen.findByRole("list", { name: "Passages" });
    await waitFor(() => expect(passages).toHaveTextContent("Thanks, Load controller."));
  });

  it("explains instead of saving when nothing changed", async () => {
    const { calls } = speakersApi();
    renderApp(PATH);
    const card = await screen.findByRole("region", { name: "Speaker mapping" });
    await within(card).findByRole("table");
    fireEvent.click(within(card).getByRole("button", { name: "Save speakers" }));
    expect(await within(card).findByRole("alert")).toHaveTextContent("Nothing has changed.");
    expect(calls.some((c) => c.key.startsWith("PUT"))).toBe(false);
  });

  it("points to Setup when there are no roles yet", async () => {
    speakersApi({ "GET /api/engagements/e1/roles": () => ({ body: [] }) });
    renderApp(PATH);
    const card = await screen.findByRole("region", { name: "Speaker mapping" });
    expect(await within(card).findByRole("link", { name: "Add roles on the Setup screen" })).toHaveAttribute(
      "href",
      "/engagements/e1/setup",
    );
  });

  it("shows the server's message when saving fails", async () => {
    speakersApi({
      "PUT /api/sources/t1/speakers": () => ({
        status: 422,
        body: { error: { code: "VALIDATION", message: "Choose one of this engagement's roles, or Interviewer.", details: {} } },
      }),
    });
    renderApp(PATH);
    const card = await screen.findByRole("region", { name: "Speaker mapping" });
    fireEvent.change(await within(card).findByRole("combobox", { name: `Role for ${NAME}` }), {
      target: { value: "r1" },
    });
    fireEvent.click(within(card).getByRole("button", { name: "Save speakers" }));
    expect(await within(card).findByRole("alert")).toHaveTextContent("Choose one of this engagement's roles");
  });

  it("is not shown for documents", async () => {
    speakersApi({
      "GET /api/engagements/e1/sources": () => ({ body: [{ ...TRANSCRIPT, kind: "sop" }] }),
    });
    renderApp(PATH);
    await screen.findByRole("list", { name: "Passages" });
    expect(screen.queryByRole("region", { name: "Speaker mapping" })).not.toBeInTheDocument();
  });
});

describe("Names to hide", () => {
  it("lists names with what they show as and where they came from", async () => {
    speakersApi();
    renderApp(PATH);
    const list = await screen.findByRole("list", { name: "Names hidden in this engagement" });
    expect(list).toHaveTextContent(`${NAME} → shown as [name]`);
    expect(list).toHaveTextContent("from speaker label");
  });

  it("adds a name with what to show instead", async () => {
    const { calls } = speakersApi();
    renderApp(PATH);
    const card = await screen.findByRole("region", { name: "Names to hide" });
    fireEvent.change(within(card).getByLabelText("Name to hide"), { target: { value: " Priya " } });
    fireEvent.change(within(card).getByLabelText("Show instead (optional)"), {
      target: { value: "Load controller" },
    });
    fireEvent.click(within(card).getByRole("button", { name: "Add name" }));
    expect(await screen.findByText(/Name added/)).toBeInTheDocument();
    expect(calls.find((c) => c.key === "POST /api/engagements/e1/redaction-terms")?.body).toEqual({
      term: "Priya",
      replacement: "Load controller",
    });
    expect(within(card).getByLabelText("Name to hide")).toHaveValue("");
  });

  it("explains an empty name and a duplicate", async () => {
    speakersApi({
      "POST /api/engagements/e1/redaction-terms": () => ({
        status: 409,
        body: { error: { code: "CONFLICT", message: "That name is already on the list.", details: {} } },
      }),
    });
    renderApp(PATH);
    const card = await screen.findByRole("region", { name: "Names to hide" });
    fireEvent.click(within(card).getByRole("button", { name: "Add name" }));
    expect(await within(card).findByText(/Please enter a name/)).toBeInTheDocument();
    fireEvent.change(within(card).getByLabelText("Name to hide"), { target: { value: NAME } });
    fireEvent.click(within(card).getByRole("button", { name: "Add name" }));
    expect(await within(card).findByText("That name is already on the list.")).toBeInTheDocument();
  });

  it("removes a name", async () => {
    const { calls } = speakersApi();
    renderApp(PATH);
    fireEvent.click(await screen.findByRole("button", { name: `Stop hiding ${NAME}` }));
    expect(await screen.findByText("Name removed from the list.")).toBeInTheDocument();
    expect(calls.some((c) => c.key === "DELETE /api/redaction-terms/n1")).toBe(true);
  });
});

describe("Privacy (PRD §6.2 item 8)", () => {
  it("shows the name only inside the owner-only places", async () => {
    speakersApi();
    renderApp(PATH);
    await screen.findByRole("list", { name: "Names hidden in this engagement" });
    await screen.findByRole("table", { name: "Speakers in this transcript" });
    await screen.findByRole("list", { name: "Passages" });
    expect(document.body.textContent).toContain(NAME);
    expect(publicText()).not.toContain(NAME);
    expect(publicText()).not.toContain("Priya");
  });

  it("has no serious or critical accessibility violations", async () => {
    speakersApi();
    const { container } = renderApp(PATH);
    await screen.findByRole("table", { name: "Speakers in this transcript" });
    await screen.findByRole("list", { name: "Names hidden in this engagement" });
    expect(await seriousViolations(container)).toEqual([]);
  });
});
