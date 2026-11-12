import { GRADE_LABELS, GRADE_MEANINGS, GRADE_OPTIONS, type Grade, type GradeKey } from "../../lib/grade";
import { Chip } from "./Chip";
import { SelectField } from "./Field";

export interface GradeControlProps {
  grade: Grade;
  /** What is graded, for the control's name: "X1", or a finding's title. */
  subject: string;
  /** Given when Eric may change the grade; choosing the suggested grade again clears his choice. */
  onChange?: ((grade: GradeKey | null) => void) | undefined;
}

/**
 * The shared grade of a discrepancy or gap finding: the word, whether it is the suggested one or
 * Eric's own, and (when he may change it) a list to choose another. Words only, never colour.
 */
export function GradeControl({ grade, subject, onChange }: GradeControlProps) {
  const origin = grade.chosen_by_owner
    ? `your choice; suggested: ${GRADE_LABELS[grade.suggested]}`
    : "suggested";
  return (
    <span className="grade">
      <Chip title={`${GRADE_LABELS[grade.grade]}: ${GRADE_MEANINGS[grade.grade]}`}>
        Grade: {GRADE_LABELS[grade.grade]}
      </Chip>{" "}
      <span className="grade__origin">({origin})</span>
      {onChange && (
        <SelectField
          label={`Grade for ${subject}`}
          value={grade.grade}
          options={GRADE_OPTIONS}
          onChange={(value) => onChange(value === grade.suggested ? null : (value as GradeKey))}
        />
      )}
    </span>
  );
}
