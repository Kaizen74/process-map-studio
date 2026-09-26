import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../../src/App";

describe("placeholder page", () => {
  it("shows the product name as the only top-level heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Process Map Studio");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });

  it("explains in plain language what works now", () => {
    render(<App />);
    expect(screen.getByText(/foundations are in place/i)).toBeInTheDocument();
  });
});
