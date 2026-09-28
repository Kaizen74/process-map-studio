import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ImageGallery } from "../../src/components/panel";
import { ToastProvider } from "../../src/components/shell";
import { ImagesSection } from "../../src/features/review/ImagesSection";
import { checkImageDetails, EMPTY_DETAILS, type StepImage } from "../../src/lib/images";
import { seriousViolations } from "../axe";
import { fakeApi, type Handler } from "../renderApp";

const SUGGESTED: StepImage = {
  id: "i1",
  element_id: "s1",
  caption: "Image from manual_extract.pdf, page 3",
  image_type: null,
  origin: "extracted",
  status: "suggested",
  redaction_confirmed: false,
  source_name: "manual_extract.pdf",
  page: 3,
  created_at: "2026-09-28T09:00:00+00:00",
};

const UPLOADED: StepImage = {
  ...SUGGESTED,
  id: "i2",
  caption: "Load sheet on the ramp printer",
  image_type: "workplace_photo",
  origin: "uploaded",
  status: "kept",
  redaction_confirmed: true,
  source_name: "",
  page: null,
};

function renderSection(routes: Record<string, Handler>, editable = true) {
  const api = fakeApi(routes);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ImagesSection elementId="s1" versionId="v1" engagementId="e1" editable={editable} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...api, ...view };
}

const LIST = "GET /api/elements/s1/images";

describe("the gallery (PRD §5.7.7 item 10)", () => {
  it("a suggestion is dashed, says Suggested and where from, with Keep and Discard", async () => {
    const onKeep = vi.fn();
    const onDiscard = vi.fn();
    const onRemove = vi.fn();
    const { container } = render(
      <ImageGallery
        images={[SUGGESTED, UPLOADED]}
        readOnly={false}
        busyId={null}
        onKeep={onKeep}
        onDiscard={onDiscard}
        onRemove={onRemove}
      />,
    );
    const [first, second] = screen.getAllByRole("listitem");
    if (!first || !second) throw new Error("two cards");
    expect(first).toHaveClass("image-card--suggested");
    expect(first).toHaveTextContent("Suggested from manual_extract.pdf, page 3");
    const img = within(first).getByRole("img", { name: SUGGESTED.caption });
    expect(img).toHaveAttribute("src", "/api/images/i1/file?size=thumb");
    fireEvent.click(within(first).getByRole("button", { name: `Keep ${SUGGESTED.caption}` }));
    fireEvent.click(within(first).getByRole("button", { name: `Discard ${SUGGESTED.caption}` }));
    expect(onKeep).toHaveBeenCalledWith(SUGGESTED);
    expect(onDiscard).toHaveBeenCalledWith(SUGGESTED);
    expect(within(first).queryByRole("button", { name: /Remove/ })).toBeNull();
    // Uploaded: its type, and Remove only.
    expect(second).not.toHaveClass("image-card--suggested");
    expect(second).toHaveTextContent("Workplace photo");
    fireEvent.click(within(second).getByRole("button", { name: `Remove ${UPLOADED.caption}` }));
    expect(onRemove).toHaveBeenCalledWith(UPLOADED);
    expect(within(second).queryByRole("button", { name: /Keep|Discard/ })).toBeNull();
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("read-only (published): pictures, no actions", () => {
    render(
      <ImageGallery images={[SUGGESTED, UPLOADED]} readOnly busyId={null} onKeep={vi.fn()} onDiscard={vi.fn()} onRemove={vi.fn()} />,
    );
    expect(screen.getAllByRole("img")).toHaveLength(2);
    expect(screen.queryAllByRole("button")).toEqual([]);
  });
});

describe("checking the details before anything is sent", () => {
  it("names every missing field in the server's words", () => {
    expect(checkImageDetails(EMPTY_DETAILS, true)).toEqual({
      file: "Choose a JPG, PNG or WebP picture.",
      caption: "Add a caption of up to 300 characters.",
      image_type: "Choose what kind of picture this is.",
      redaction_confirmed: "Confirm that faces, names, badge numbers and flight identifiers are removed or not shown.",
    });
    const big = new File(["x"], "big.jpg", { type: "image/jpeg" });
    Object.defineProperty(big, "size", { value: 10 * 1024 * 1024 + 1 });
    const details = { file: big, caption: "Ramp printer", imageType: "workplace_photo" as const, confirmed: true };
    expect(checkImageDetails(details, true)).toEqual({ file: "Pictures can be up to 10 MB." });
    expect(checkImageDetails({ ...details, file: new File(["x"], "a.gif", { type: "image/gif" }) }, true).file).toBe(
      "Choose a JPG, PNG or WebP picture.",
    );
    expect(checkImageDetails({ ...details, file: null }, false)).toEqual({});
    expect(checkImageDetails({ ...details, caption: "a".repeat(301) }, false).caption).toBeDefined();
  });
});

describe("the Images section", () => {
  it("empty: says so, with the in-app note and Add image to this step", async () => {
    renderSection({ [LIST]: () => ({ body: [] }) });
    expect(await screen.findByText("No pictures on this step yet.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Images" })).toHaveTextContent(
      "In-app only · never exported · metadata stripped",
    );
    expect(screen.getByRole("button", { name: "Add image to this step" })).toBeInTheDocument();
  });

  it("adding: nothing is sent until every field passes, then the picture is uploaded", async () => {
    const { calls } = renderSection({
      [LIST]: () => ({ body: [] }),
      "POST /api/elements/s1/images": () => ({ status: 201, body: UPLOADED }),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Add image to this step" }));
    const form = screen.getByRole("form", { name: "Add image to this step" });
    fireEvent.click(within(form).getByRole("button", { name: "Add picture" }));
    expect(within(form).getByText("4 things to fix before saving.")).toBeInTheDocument();
    expect(within(form).getByLabelText("Caption")).toHaveAttribute("aria-invalid", "true");
    expect(calls.some((c) => c.key.startsWith("POST"))).toBe(false);
    expect(await seriousViolations(form)).toEqual([]);

    const file = new File(["jpeg"], "ramp.jpg", { type: "image/jpeg" });
    fireEvent.change(within(form).getByLabelText("Picture"), { target: { files: [file] } });
    fireEvent.change(within(form).getByLabelText("Caption"), { target: { value: " Load sheet on the ramp printer " } });
    fireEvent.change(within(form).getByLabelText("Type of picture"), { target: { value: "workplace_photo" } });
    fireEvent.click(within(form).getByLabelText(/Faces, names, badge numbers and flight identifiers/));
    fireEvent.click(within(form).getByRole("button", { name: "Add picture" }));
    await screen.findByText("Picture added. Location and camera details were removed.");
    const sent = calls.find((c) => c.key === "POST /api/elements/s1/images")?.body as FormData;
    expect(sent.get("file")).toBe(file);
    expect([sent.get("caption"), sent.get("image_type"), sent.get("redaction_confirmed")]).toEqual([
      "Load sheet on the ramp printer",
      "workplace_photo",
      "true",
    ]);
    await waitFor(() => expect(screen.queryByRole("form")).toBeNull());
  });

  it("a refusal about one field is shown under that field", async () => {
    renderSection({
      [LIST]: () => ({ body: [] }),
      "POST /api/elements/s1/images": () => ({
        status: 422,
        body: {
          error: {
            code: "VALIDATION",
            message: "The caption contains a name from your list of names to hide. Use the role instead.",
            details: { field: "caption" },
          },
        },
      }),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Add image to this step" }));
    const form = screen.getByRole("form");
    fireEvent.change(within(form).getByLabelText("Picture"), {
      target: { files: [new File(["png"], "a.png", { type: "image/png" })] },
    });
    fireEvent.change(within(form).getByLabelText("Caption"), { target: { value: "At the printer" } });
    fireEvent.change(within(form).getByLabelText("Type of picture"), { target: { value: "workplace_photo" } });
    fireEvent.click(within(form).getByRole("checkbox"));
    fireEvent.click(within(form).getByRole("button", { name: "Add picture" }));
    expect(await within(form).findByText(/Use the role instead/)).toHaveClass("field__error");
    expect(within(form).getByLabelText("Caption")).toHaveAttribute("aria-invalid", "true");
  });

  it("keeping a suggestion asks for its type and the confirmation, then keeps it", async () => {
    const { calls } = renderSection({
      [LIST]: () => ({ body: [SUGGESTED] }),
      "PATCH /api/images/i1": () => ({ body: { ...SUGGESTED, status: "kept", image_type: "document_extract" } }),
    });
    fireEvent.click(await screen.findByRole("button", { name: `Keep ${SUGGESTED.caption}` }));
    const form = screen.getByRole("form", { name: "Keep suggested picture" });
    expect(form).toHaveTextContent("From manual_extract.pdf, page 3.");
    expect(within(form).queryByLabelText("Picture")).toBeNull();
    expect(within(form).getByLabelText("Caption")).toHaveValue(SUGGESTED.caption);
    fireEvent.click(within(form).getByRole("button", { name: "Keep picture" }));
    expect(within(form).getByText("2 things to fix before saving.")).toBeInTheDocument();
    fireEvent.change(within(form).getByLabelText("Type of picture"), { target: { value: "document_extract" } });
    fireEvent.click(within(form).getByRole("checkbox"));
    fireEvent.click(within(form).getByRole("button", { name: "Keep picture" }));
    await screen.findByText("Suggested picture kept.");
    expect(calls.find((c) => c.key === "PATCH /api/images/i1")?.body).toEqual({
      status: "kept",
      caption: SUGGESTED.caption,
      image_type: "document_extract",
      redaction_confirmed: true,
    });
  });

  it("discarding a suggestion needs no questions", async () => {
    const { calls } = renderSection({
      [LIST]: () => ({ body: [SUGGESTED] }),
      "PATCH /api/images/i1": () => ({ body: { ...SUGGESTED, status: "discarded" } }),
    });
    fireEvent.click(await screen.findByRole("button", { name: `Discard ${SUGGESTED.caption}` }));
    await screen.findByText("Suggested picture discarded.");
    expect(calls.find((c) => c.key === "PATCH /api/images/i1")?.body).toEqual({ status: "discarded" });
  });

  it("removing asks first, naming the picture", async () => {
    const { calls } = renderSection({
      [LIST]: () => ({ body: [UPLOADED] }),
      "DELETE /api/images/i2": () => ({ status: 204, body: null }),
    });
    fireEvent.click(await screen.findByRole("button", { name: `Remove ${UPLOADED.caption}` }));
    const dialog = screen.getByRole("dialog", { name: "Remove this picture?" });
    expect(dialog).toHaveTextContent(`“${UPLOADED.caption}” will be removed from this step.`);
    expect(calls.some((c) => c.key.startsWith("DELETE"))).toBe(false);
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove picture" }));
    await screen.findByText("Picture removed.");
    expect(calls.some((c) => c.key === "DELETE /api/images/i2")).toBe(true);
  });

  it("published: pictures only, no Add, Keep, Discard or Remove", async () => {
    renderSection({ [LIST]: () => ({ body: [SUGGESTED, UPLOADED] }) }, false);
    expect(await screen.findAllByRole("img")).toHaveLength(2);
    expect(screen.queryAllByRole("button")).toEqual([]);
  });

  it("a list that can't be loaded says so and offers Try again", async () => {
    renderSection({
      [LIST]: () => ({ status: 500, body: { error: { code: "INTERNAL", message: "Something broke.", details: {} } } }),
    });
    expect(await screen.findByText("The pictures couldn't be loaded")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
