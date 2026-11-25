import { useState } from "react";
import type { ElementDetail, GraphRole } from "../../lib/mapTypes";
import { paperDiffers, splits, type Rights } from "../../lib/accountability";
import { Button, SelectField } from "../common";
import { PanelSection as Section } from "./PanelSections";

// Who decides (PRD §3.20; DECISIONS 110): the decider the documents name, the one deciding in
// practice and the one accountable, side by side, marked "decides ≠ accountable" when they differ.
// Eric records the decider on paper with the passage naming it; when it differs from the decider in
// practice and the step has no Different role discrepancy, a hint asks (it creates nothing).
// Presentational: the screen saves the choice.

const NOT_NAMED = "not_named";
const NONE = "";

export interface PaperChoice {
  busy: boolean;
  error?: string | null | undefined;
  onSave: (body: { status: "named" | "not_named" | null; role_id?: string | null; segment_id?: string | null }) => void;
}

export interface DeciderSectionProps {
  element: ElementDetail;
  rights: Rights;
  roles: readonly GraphRole[];
  /** Omitted where the version can't change. */
  choice?: PaperChoice | undefined;
}

export function DeciderSection({ element, rights, roles, choice }: DeciderSectionProps) {
  const [editing, setEditing] = useState(false);
  const paper = element.paper_decider ?? null;
  const onPaper =
    paper === null
      ? "Not recorded"
      : paper.status === "not_named"
        ? "Not named in any document"
        : `${element.paper_decider_role_name || "Unknown role"} · ${element.paper_decider_anchor || "not cited"}`;
  const split = splits(rights);
  return (
    <Section title="Who decides">
      <dl className="panel-rows">
        <div>
          <dt>Named in the documents</dt>
          <dd>{onPaper}</dd>
        </div>
        <div>
          <dt>Decides in practice</dt>
          <dd>{rights.decidedBy || "Not known"}</dd>
        </div>
        <div>
          <dt>Accountable</dt>
          <dd>
            {rights.accountable || "Nobody holds A"}
            {rights.contested && " (A?: the sources disagree, or two roles hold A)"}
          </dd>
        </div>
      </dl>
      {split && (
        <p className="decider-split">
          <span aria-hidden="true">≠ </span>decides ≠ accountable
        </p>
      )}
      {paperDiffers(rights) && !element.paper_decider_hint && (
        <p className="sense-note">The documents name a different decider; a Different role discrepancy records it.</p>
      )}
      {element.paper_decider_hint && <p className="inline-note">{element.paper_decider_hint}</p>}
      {choice && !editing && (
        <div className="work-type-choice__actions">
          <Button disabled={choice.busy} onClick={() => setEditing(true)}>
            {paper ? "Change the decider named in the documents" : "Record the decider named in the documents"}
          </Button>
        </div>
      )}
      {choice && editing && (
        <PaperForm element={element} roles={roles} choice={choice} onDone={() => setEditing(false)} />
      )}
      {choice?.error && (
        <p className="panel-danger" role="alert">
          {choice.error}
        </p>
      )}
    </Section>
  );
}

function PaperForm({
  element,
  roles,
  choice,
  onDone,
}: {
  element: ElementDetail;
  roles: readonly GraphRole[];
  choice: PaperChoice;
  onDone: () => void;
}) {
  const paper = element.paper_decider ?? null;
  const [role, setRole] = useState(
    paper === null ? NONE : paper.status === "not_named" ? NOT_NAMED : (paper.role_id ?? NONE),
  );
  const [passage, setPassage] = useState(paper?.segment_id ?? NONE);
  // The step's own checked passages from documents (not interviews): the ones that can name it.
  const passages = element.evidence.filter(
    (c) => c.segment_id && c.verified && c.source_kind !== "interview_transcript",
  );
  const people = roles.filter((r) => !r.is_system);
  return (
    <form
      className="stack work-type-choice"
      onSubmit={(event) => {
        event.preventDefault();
        if (role === NONE) choice.onSave({ status: null });
        else if (role === NOT_NAMED) choice.onSave({ status: "not_named" });
        else choice.onSave({ status: "named", role_id: role, segment_id: passage || null });
        onDone();
      }}
    >
      <SelectField
        label="Decider named in the documents"
        value={role}
        options={[
          { value: NONE, label: "Not recorded" },
          ...people.map((r) => ({ value: r.id, label: r.name })),
          { value: NOT_NAMED, label: "Not named in any document" },
        ]}
        onChange={setRole}
      />
      {role !== NONE && role !== NOT_NAMED && (
        <SelectField
          label="The passage that names it"
          value={passage}
          options={[
            { value: NONE, label: "Not cited" },
            ...passages.map((c) => ({ value: c.segment_id ?? "", label: `${c.source_name} ${c.anchor}` })),
          ]}
          onChange={setPassage}
          help={passages.length === 0 ? "This step cites no document passage; it will be shown as not cited." : undefined}
        />
      )}
      <div className="work-type-choice__actions">
        <Button type="submit" variant="primary" disabled={choice.busy}>
          Save
        </Button>
        <Button onClick={onDone}>Cancel</Button>
      </div>
    </form>
  );
}
