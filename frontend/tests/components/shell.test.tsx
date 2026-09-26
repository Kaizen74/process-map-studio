import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Button } from "../../src/components/common";
import {
  EngagementNav,
  TOAST_MS,
  ToastProvider,
  TopBar,
  useToast,
  type NavItem,
} from "../../src/components/shell";
import { seriousViolations } from "../axe";

afterEach(() => vi.useRealTimers());

describe("TopBar", () => {
  it("shows the product and app links, marking the current page", () => {
    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <TopBar />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Process Map Studio" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Engagements" })).not.toHaveAttribute("aria-current");
  });

  it("shows the engagement and the illustrative-fixture note", () => {
    render(
      <MemoryRouter>
        <TopBar engagementName="Load control" isFixture />
      </MemoryRouter>,
    );
    expect(screen.getByText("Load control")).toBeInTheDocument();
    expect(screen.getByText("Illustrative fixture")).toBeInTheDocument();
  });
});

describe("EngagementNav", () => {
  const items: NavItem[] = [
    { key: "setup", label: "Setup", to: "/e/1/setup", status: "done" },
    { key: "sources", label: "Sources", to: "/e/1/sources", status: "attention", count: 1 },
    { key: "draft", label: "Draft", to: "/e/1/draft", status: "not_started" },
    { key: "gap", label: "Gap analysis", to: "/e/1/gap", status: "not_started", optional: true },
  ];

  it("shows each step's status in text as well as a glyph", () => {
    render(
      <MemoryRouter>
        <EngagementNav items={items} nextKey="sources" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Setup, done" })).toBeInTheDocument();
    expect(
      screen.getByRole("link", {
        name: "Sources, needs attention, 1 to resolve, recommended next step",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Draft, not started" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Gap analysis, not started, optional" })).toBeInTheDocument();
    expect(screen.getByText("Next")).toBeInTheDocument();
  });

  it("never recommends the optional gap analysis as Next", () => {
    render(
      <MemoryRouter>
        <EngagementNav items={items} nextKey="gap" />
      </MemoryRouter>,
    );
    expect(screen.queryByText("Next")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Gap analysis, not started, optional" })).toBeInTheDocument();
  });

  it("has no serious accessibility violations", async () => {
    const { container } = render(
      <MemoryRouter>
        <EngagementNav items={items} nextKey="draft" />
      </MemoryRouter>,
    );
    expect(await seriousViolations(container)).toEqual([]);
  });
});

describe("Toast", () => {
  function Saver() {
    const toast = useToast();
    return <Button onClick={() => toast("Your name was saved.")}>Save</Button>;
  }

  it("announces a success message and removes it after 4 seconds", () => {
    vi.useFakeTimers();
    render(
      <ToastProvider>
        <Saver />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByRole("status")).toHaveTextContent("Your name was saved.");
    act(() => vi.advanceTimersByTime(TOAST_MS - 1));
    expect(screen.getByRole("status")).toHaveTextContent("Your name was saved.");
    act(() => vi.advanceTimersByTime(1));
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });
});
