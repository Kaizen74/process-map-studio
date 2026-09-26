import { act, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import {
  Button,
  Card,
  Chip,
  Dialog,
  EmptyState,
  ErrorState,
  Popover,
  SegmentedControl,
  Skeleton,
  StateGlyph,
} from "../../src/components/common";
import { STATE_GLYPHS, type StanceOrState } from "../../src/lib/stateGlyph";
import { seriousViolations } from "../axe";

describe("Button", () => {
  it("never submits a form by accident and passes clicks through", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("type", "button");
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("applies the variant", () => {
    render(<Button variant="primary">Publish</Button>);
    expect(screen.getByRole("button")).toHaveClass("btn", "btn--primary");
  });
});

describe("Chip and Card", () => {
  it("chip carries its meaning in text", () => {
    render(<Chip tone="danger">Contested</Chip>);
    expect(screen.getByText("Contested")).toHaveClass("chip--danger");
  });

  it("a titled card is a labelled region", () => {
    render(
      <Card title="Your name" description="Shown as the validator.">
        body
      </Card>,
    );
    expect(screen.getByRole("region", { name: "Your name" })).toHaveTextContent("body");
  });
});

describe("SegmentedControl", () => {
  const options = [
    { value: "map", label: "Map" },
    { value: "table", label: "Table" },
  ] as const;

  function Harness() {
    const [value, setValue] = useState<"map" | "table">("map");
    return <SegmentedControl label="View" options={options} value={value} onChange={setValue} />;
  }

  it("is a radio group with one checked option", () => {
    render(<Harness />);
    expect(screen.getByRole("radiogroup", { name: "View" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Map" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Table" })).toHaveAttribute("tabindex", "-1");
  });

  it("changes on click and with arrow keys, wrapping round", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("radio", { name: "Table" }));
    expect(screen.getByRole("radio", { name: "Table" })).toHaveAttribute("aria-checked", "true");
    fireEvent.keyDown(screen.getByRole("radio", { name: "Table" }), { key: "ArrowRight" });
    expect(screen.getByRole("radio", { name: "Map" })).toHaveAttribute("aria-checked", "true");
    expect(document.activeElement).toBe(screen.getByRole("radio", { name: "Map" }));
  });
});

describe("Skeleton, EmptyState, ErrorState", () => {
  it("skeleton is hidden from screen readers", () => {
    const { container } = render(<Skeleton width="40px" />);
    expect(container.firstChild).toHaveAttribute("aria-hidden", "true");
  });

  it("empty state has one sentence and one action", () => {
    render(<EmptyState message="Add the interview transcript." action={<Button>Upload</Button>} />);
    expect(screen.getByText("Add the interview transcript.")).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(1);
  });

  it("error state is announced and copies its details", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const onRetry = vi.fn();
    render(
      <ErrorState
        title="Settings couldn't be saved"
        message="Nothing was changed. Try again."
        details="INTERNAL · request 1234"
        onRetry={onRetry}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Settings couldn't be saved");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
    });
    expect(writeText).toHaveBeenCalledWith("INTERNAL · request 1234");
    expect(screen.getByText(/Details copied/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("error state shows the details if copying fails", async () => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error()) } });
    render(<ErrorState title="Oops" message="Try again." details="CODE-9" />);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy details" }));
    });
    expect(screen.getByText(/The details are: CODE-9/)).toBeInTheDocument();
  });
});

describe("StateGlyph", () => {
  const states = Object.keys(STATE_GLYPHS) as StanceOrState[];

  it.each(states)("%s shows a shape and a text label", (state) => {
    const { container } = render(<StateGlyph state={state} />);
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText(STATE_GLYPHS[state].label)).toBeVisible();
  });

  it("keeps the label as the accessible name when hidden visually", () => {
    render(<StateGlyph state="silent" showLabel={false} />);
    expect(screen.getByText("Silent")).toHaveClass("visually-hidden");
  });

  it("contested uses danger text; states that differ never share shape and label", () => {
    const { container } = render(<StateGlyph state="contested" />);
    expect(container.firstChild).toHaveClass("glyph--danger-text");
    const signatures = states.map((s) => `${STATE_GLYPHS[s].shape}|${STATE_GLYPHS[s].label}`);
    expect(new Set(signatures).size).toBe(states.length);
  });
});

describe("Dialog", () => {
  function Harness({ onClose }: { onClose?: () => void }) {
    const [open, setOpen] = useState(false);
    const [name, setName] = useState("");
    return (
      <>
        <Button onClick={() => setOpen(true)}>Delete engagement</Button>
        <Dialog
          open={open}
          title="Delete this engagement?"
          description="This removes the engagement, its sources and its maps."
          onClose={() => {
            onClose?.();
            setOpen(false);
          }}
          actions={
            <>
              <Button onClick={() => setOpen(false)}>Cancel</Button>
              <Button variant="primary">Delete</Button>
            </>
          }
        >
          <Button>Show an example</Button>
          <label>
            Type the name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
        </Dialog>
      </>
    );
  }

  it("opens as a labelled modal and moves focus inside", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Delete engagement" }));
    const dialog = screen.getByRole("dialog", { name: "Delete this engagement?" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleDescription(/removes the engagement/);
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("keeps Tab inside and closes on Esc, returning focus", () => {
    const onClose = vi.fn();
    render(<Harness onClose={onClose} />);
    const trigger = screen.getByRole("button", { name: "Delete engagement" });
    trigger.focus();
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog");
    const deleteButton = screen.getByRole("button", { name: "Delete" });
    deleteButton.focus();
    fireEvent.keyDown(dialog, { key: "Tab" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Show an example" }));
    fireEvent.keyDown(dialog, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(deleteButton);
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.activeElement).toBe(trigger);
  });

  it("keeps focus in a field while typing (parent re-renders)", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Delete engagement" }));
    const input = screen.getByRole("textbox");
    input.focus();
    fireEvent.change(input, { target: { value: "L" } });
    fireEvent.change(input, { target: { value: "Lo" } });
    expect(document.activeElement).toBe(input);
    expect(input).toHaveValue("Lo");
  });

  it("closes on a click outside", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Delete engagement" }));
    const overlay = screen.getByRole("dialog").parentElement as HTMLElement;
    fireEvent.mouseDown(overlay);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("Popover", () => {
  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <div>
        <span className="popover-anchor">
          <Button onClick={() => setOpen(true)}>Quality card</Button>
          <Popover open={open} title="Quality card" onClose={() => setOpen(false)}>
            <p>8 of 9 green</p>
          </Popover>
        </span>
        <p>Outside</p>
      </div>
    );
  }

  it("opens with focus inside and closes with Close, Esc or a click outside", () => {
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Quality card" });
    trigger.focus();
    fireEvent.click(trigger);
    const popover = screen.getByRole("dialog", { name: "Quality card" });
    expect(popover.contains(document.activeElement)).toBe(true);
    fireEvent.keyDown(popover, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(document.activeElement).toBe(trigger);

    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(trigger);
    fireEvent.mouseDown(screen.getByText("Outside"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("accessibility (axe-core, serious and critical)", () => {
  it("common components have no serious or critical violations", async () => {
    const { container } = render(
      <main>
        <h1>Components</h1>
        <Button variant="primary">Save</Button>
        <Chip tone="good">Confirmed</Chip>
        <Card title="Card">
          <SegmentedControl
            label="Lens"
            options={[
              { value: "plain", label: "Plain" },
              { value: "time", label: "Time" },
            ]}
            value="plain"
            onChange={() => undefined}
          />
        </Card>
        <EmptyState message="Nothing here yet." />
        <ErrorState title="Failed" message="Try again." details="X" />
        {(Object.keys(STATE_GLYPHS) as StanceOrState[]).map((s) => (
          <StateGlyph key={s} state={s} />
        ))}
        <Skeleton />
      </main>,
    );
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("an open dialog has no serious or critical violations", async () => {
    render(
      <Dialog open title="Confirm" description="Are you sure?" onClose={() => undefined} actions={<Button>OK</Button>} />,
    );
    expect(await seriousViolations(document.body)).toEqual([]);
  });
});
