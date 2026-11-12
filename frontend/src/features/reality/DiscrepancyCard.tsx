import { useState } from "react";
import { Button, Card, GradeControl, SelectField, TextField } from "../../components/common";
import { EvidenceChips, ImpactWord } from "../../components/reality";
import { useDecideVerdict, useSetDiscrepancyGrade } from "../../hooks/useReality";
import { messageOf } from "../../lib/errors";
import { VERDICT_LABELS, verdictText, type CodeView, type RealitySnapshot } from "../../lib/reality";

const CHOICES = ["codify", "correct", "rewrite", "ask"].map((v) => ({ value: v, label: VERDICT_LABELS[v] ?? v }));

/**
 * The Discrepancies card (PRD §5.4 Reality): every X code with its types, delta, impact, evidence
 * chips and verdict. On a draft Eric confirms or changes the verdict (a note is required); a
 * published version's verdicts were frozen with it.
 */
export function DiscrepancyCard({
  engagementId,
  snapshot,
  selected,
  onSelect,
}: {
  engagementId: string;
  snapshot: RealitySnapshot;
  selected: string | null;
  onSelect: (code: string) => void;
}) {
  return (
    <Card
      title="Discrepancies"
      description={
        snapshot.draft
          ? "Each gap between the manual, the intent and practice, with where the fix may lie. Verdicts are recommendations; you decide."
          : "Verdicts were frozen when this version was published. Decide verdicts on a draft."
      }
    >
      {snapshot.codes.length === 0 && <p className="inline-note">No discrepancy found in this version.</p>}
      <ul className="discrepancy-list">
        {snapshot.codes.map((c) => (
          <DiscrepancyRow
            key={c.code}
            code={c}
            engagementId={engagementId}
            editable={snapshot.draft}
            selected={selected === c.code}
            dimmed={selected !== null && selected !== c.code}
            onSelect={onSelect}
          />
        ))}
      </ul>
    </Card>
  );
}

interface RowProps {
  code: CodeView;
  engagementId: string;
  editable: boolean;
  selected: boolean;
  dimmed: boolean;
  onSelect: (code: string) => void;
}

function DiscrepancyRow({ code: c, engagementId, editable, selected, dimmed, onSelect }: RowProps) {
  const decide = useDecideVerdict(engagementId);
  const grade = useSetDiscrepancyGrade(engagementId);
  const [open, setOpen] = useState<"confirm" | "change" | null>(null);
  const [verdict, setVerdict] = useState(c.verdict?.shown ?? "ask");
  const [note, setNote] = useState("");
  const [problem, setProblem] = useState<string | null>(null);

  const save = (chosen: string) => {
    if (!note.trim()) {
      setProblem("Add a note saying why: it is kept with your verdict.");
      return;
    }
    setProblem(null);
    decide.mutate({ itemId: c.item_id, verdict: chosen, note: note.trim() }, { onSuccess: () => setOpen(null) });
  };

  return (
    <li className={`discrepancy-row${dimmed ? " is-dimmed" : ""}`}>
      <button type="button" className="discrepancy-row__head" aria-pressed={selected} onClick={() => onSelect(c.code)}>
        <span className={`x-tag x-tag--${c.impact_class}`}>{c.code}</span>{" "}
        <span className="discrepancy-row__title">{c.title}</span>
      </button>
      <span className="discrepancy-row__meta">
        <span>{c.types.join(" ")}</span>
        <span>
          {c.delta.text} ({c.delta.label})
        </span>
        <ImpactWord code={c} />
        <EvidenceChips evidence={c.evidence} />
      </span>
      {c.impact_note && <span className="discrepancy-row__note">{c.impact_note}</span>}
      {c.verdict && (
        <span className="discrepancy-row__verdict">
          Verdict: {verdictText(c.verdict)}. {c.verdict.reason}
          {c.verdict.note && ` Your note: ${c.verdict.note}`}
        </span>
      )}
      {c.grade && (
        <span className="discrepancy-row__grade">
          <GradeControl
            grade={c.grade}
            subject={c.code}
            onChange={editable ? (chosen) => grade.mutate({ itemId: c.item_id, grade: chosen }) : undefined}
          />
          {grade.isError && <span className="danger-note">{messageOf(grade.error)}</span>}
        </span>
      )}
      {editable && c.verdict && open === null && (
        <span className="discrepancy-row__actions">
          {c.verdict.status === "suggested" && c.verdict.suggested && (
            <Button onClick={() => setOpen("confirm")}>
              Confirm verdict{" "}
            <span className="visually-hidden">for {c.code}</span>
            </Button>
          )}
          <Button onClick={() => setOpen("change")}>
            Change{" "}
            <span className="visually-hidden">the verdict for {c.code}</span>
          </Button>
        </span>
      )}
      {open && (
        <form
          className="verdict-form"
          onSubmit={(e) => {
            e.preventDefault();
            save(open === "confirm" ? (c.verdict?.suggested ?? "ask") : verdict);
          }}
        >
          {open === "change" && <SelectField label="Verdict" value={verdict} options={CHOICES} onChange={setVerdict} />}
          <TextField label="Note (why)" value={note} onChange={setNote} error={problem} />
          {decide.isError && <p className="danger-note">{messageOf(decide.error)}</p>}
          <span className="discrepancy-row__actions">
            <Button variant="primary" type="submit" disabled={decide.isPending}>
              Save verdict
            </Button>
            <Button onClick={() => setOpen(null)}>Cancel</Button>
          </span>
        </form>
      )}
    </li>
  );
}
