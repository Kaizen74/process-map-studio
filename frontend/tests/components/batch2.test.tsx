import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CompassRole, Role } from "../../src/api/types";
import { DataSection } from "../../src/components/panel";
import { RolesCard } from "../../src/features/setup/RolesCard";
import { DataTable } from "../../src/features/review/DataTable";
import { ToastProvider } from "../../src/components/shell";
import type { Graph, GraphEdge } from "../../src/lib/mapTypes";
import { seriousViolations } from "../axe";
import sample from "../fixtures/accountability_sample.json";
import { fakeApi } from "../renderApp";
import { elementByLabel } from "../sampleMap";

// Batch 2 of the four-app review (DECISIONS 113): a lane's Capability Compass role, what checks
// the data at a handoff, and the data fields of every step in one table.

afterEach(() => vi.unstubAllGlobals());

function withClient(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>{node}</ToastProvider>
    </QueryClientProvider>,
  );
}

const ROLES: Role[] = [
  { id: "r1", engagement_id: "e1", name: "Shift supervisor", aliases: [], is_system: false, lane_order: 1 },
  { id: "r2", engagement_id: "e1", name: "Load control system", aliases: [], is_system: true, lane_order: 2 },
];
const OFFERED: CompassRole[] = [
  { ref: "RL-009", title: "Cargo Coordinator", cluster_ref: "CAP-01" },
  { ref: "RL-014", title: "Duty Manager", cluster_ref: "CAP-04" },
];

describe("a lane's Capability Compass role", () => {
  it("offers the hand-off's roles, the pilot's cluster first, and saves the choice", async () => {
    const { calls } = fakeApi({ "PATCH /api/roles/r1": () => ({ body: { ...ROLES[0], compass_role_ref: "RL-014" } }) });
    const { container } = withClient(
      <RolesCard engagementId="e1" roles={ROLES} compassRoles={OFFERED} clusterRef="CAP-04" />,
    );
    const select = screen.getByLabelText("Capability Compass role of Shift supervisor") as HTMLSelectElement;
    expect([...select.options].map((o) => o.textContent)).toEqual([
      "Not linked",
      "RL-014 · Duty Manager",
      "RL-009 · Cargo Coordinator",
    ]);
    expect(screen.queryByLabelText("Capability Compass role of Load control system")).toBeNull(); // a system
    fireEvent.change(select, { target: { value: "RL-014" } });
    await waitFor(() => expect(calls.find((c) => c.key === "PATCH /api/roles/r1")?.body).toEqual({ compass_role_ref: "RL-014" }));
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("offers nothing for an engagement made without a hand-off", () => {
    fakeApi({});
    withClient(<RolesCard engagementId="e1" roles={ROLES} />);
    expect(screen.queryByLabelText(/Capability Compass role of/)).toBeNull();
  });
});

describe("what moves and what checks it at a handoff", () => {
  const element = { ...elementByLabel("Draft load plan"), system_of_record: null };
  const edge = {
    id: "a",
    from: element.id,
    to: "b",
    kind: "sequence",
    label: "",
    data_move: "re_keyed",
    information_payload: "Loading instruction",
    data_check: "Weight checked against the booking",
  } as GraphEdge;

  it("shows both under how the data moves and saves a changed check", () => {
    const onCheck = vi.fn();
    const onMove = vi.fn();
    render(
      <DataSection
        element={element}
        roles={[]}
        handoffs={[{ edge, toLabel: "Check the plan", logged: false }]}
        choice={{ busy: false, onSystem: vi.fn(), onMove, onCheck }}
      />,
    );
    const section = screen.getByRole("region", { name: "Data" });
    expect(section).toHaveTextContent("Re-keyedWhat moves: Loading instructionWhat checks it: Weight checked against the booking");
    fireEvent.click(within(section).getByRole("button", { name: "Change the data record" }));
    fireEvent.change(within(section).getByLabelText("What checks the data going to Check the plan"), {
      target: { value: "Weight and pieces checked" },
    });
    fireEvent.click(within(section).getByRole("button", { name: "Save" }));
    expect(onCheck).toHaveBeenCalledWith("a", "Weight and pieces checked");
    expect(onMove).not.toHaveBeenCalled(); // unchanged: not sent
  });
});

describe("the data fields of every step in one table", () => {
  const graph = sample.graph as unknown as Graph;
  const versionId = graph.version.id;

  it("lists the Belmar steps with what is recorded and saves a choice at once", async () => {
    const { calls } = fakeApi({
      [`PUT /api/versions/${versionId}/edges/x/data-move`]: () => ({ body: {} }),
    });
    const { container } = withClient(
      <DataTable graph={graph} versionId={versionId} engagementId="e1" editable onSelect={vi.fn()} />,
    );
    const table = screen.getByRole("table", { name: "The data fields of each step" });
    expect(within(table).getAllByRole("row")).toHaveLength(12); // header + 11 steps
    const s03 = graph.elements.find((e) => e.code === "S-03");
    const paper = within(table).getByLabelText(`Decider named in the documents for ${s03?.label}`) as HTMLSelectElement;
    expect(paper.selectedOptions[0]?.textContent).toBe("Certified load controller");
    const s02 = graph.elements.find((e) => e.code === "S-02");
    const sys = within(table).getByLabelText(`System of record for ${s02?.label}`) as HTMLSelectElement;
    expect(sys.selectedOptions[0]?.textContent).toBe("Load control system");
    const s01 = graph.elements.find((e) => e.code === "S-01");
    const moves = within(table).getByLabelText(`How data moves from ${s01?.label} to ${s02?.label}`) as HTMLSelectElement;
    expect(moves.selectedOptions[0]?.textContent).toBe("Re-keyed");
    // An activity has no decider to name.
    expect(within(table).queryByLabelText(`Decider named in the documents for ${s01?.label}`)).toBeNull();
    fireEvent.change(sys, { target: { value: "__none" } });
    await waitFor(() =>
      expect(calls.find((c) => c.key.endsWith("/system-of-record"))?.body).toEqual({ status: "none" }),
    );
    expect(await seriousViolations(container)).toEqual([]);
  });

  it("is read only where the version can't change", () => {
    fakeApi({});
    withClient(<DataTable graph={graph} versionId={versionId} engagementId="e1" editable={false} onSelect={vi.fn()} />);
    const table = screen.getByRole("table", { name: "The data fields of each step" });
    expect(within(table).queryAllByRole("combobox")).toHaveLength(0);
    expect(table).toHaveTextContent("Certified load controller");
    expect(table).toHaveTextContent("Re-keyed");
  });
});
