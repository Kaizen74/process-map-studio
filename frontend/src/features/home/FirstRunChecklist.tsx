import { Link } from "react-router";
import { Card, Chip } from "../../components/common";
import "./home.css";

export interface ChecklistStep {
  title: string;
  detail: string;
  done: boolean;
  /** Where to go to do this step (omitted when not available yet). */
  to?: string;
  linkLabel?: string;
}

/** The three-step first-run checklist (PRD §5.4, Home). */
export function FirstRunChecklist({ steps }: { steps: readonly ChecklistStep[] }) {
  const doneCount = steps.filter((s) => s.done).length;
  return (
    <Card
      title="Get started"
      description={`${doneCount} of ${steps.length} steps done. Work through these once; the app remembers them.`}
    >
      <ol className="checklist">
        {steps.map((step, index) => (
          <li key={step.title} className="checklist__step">
            <span className="checklist__number">{index + 1}</span>
            <span>
              <span className="checklist__title">{step.title}</span>
              <br />
              <span className="checklist__detail">{step.detail}</span>
            </span>
            <span className="checklist__status">
              {step.to && step.linkLabel && <Link to={step.to}>{step.linkLabel}</Link>}
              {step.done ? (
                <Chip tone="good">Done</Chip>
              ) : (
                <Chip dashed>To do</Chip>
              )}
            </span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
