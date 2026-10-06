import { Button, Chip } from "../common";
import { DANGER_REASONS, REASONS, byPhase } from "../../lib/questions";
import type { Question } from "../../lib/reviewTypes";

export interface QuestionsTabProps {
  questions: readonly Question[];
  /** Mark answered / Reopen; omitted where the version can't change. */
  onStatus?: ((questionId: string, status: "open" | "answered") => void) | undefined;
  onGoTo: (elementId: string) => void;
  onCopy: () => void;
  onDownload: () => void;
  /** The validation session pack (F.7, criterion 75): a plain link, the server names the file. */
  packUrl?: string | undefined;
}

function PackLink({ href }: { href: string }) {
  return (
    <a className="btn btn--secondary" href={href} download>
      Download validation pack
    </a>
  );
}

/** Validation questions for the offline session (PRD §5.7.10), grouped by phase. */
export function QuestionsTab({ questions, onStatus, onGoTo, onCopy, onDownload, packUrl }: QuestionsTabProps) {
  if (questions.length === 0) {
    return (
      <div className="tab-stack">
        <p className="tab-empty">No questions. Every step was clear enough in your sources to need none.</p>
        {packUrl && (
          <div className="tab-actions">
            <PackLink href={packUrl} />
          </div>
        )}
      </div>
    );
  }
  return (
    <div className="tab-stack">
      <div className="tab-actions">
        <p className="tab-intro">Ask these in the session with the people who do the work, then mark them answered.</p>
        <Button onClick={onCopy}>Copy all</Button>
        <Button onClick={onDownload}>Download .md</Button>
        {packUrl && <PackLink href={packUrl} />}
      </div>
      {byPhase(questions).map((group) => (
        <section key={group.phase} className="tab-group" aria-label={group.phase}>
          <h3 className="tab-group__title">{group.phase}</h3>
          <ul className="tab-cards">
            {group.questions.map((q) => {
              const answered = q.status === "answered";
              return (
                <li key={q.id} className={answered ? "question question--answered" : "question"}>
                  <p className="question__text">{q.question}</p>
                  <div className="question__meta">
                    <Chip tone={DANGER_REASONS.has(q.reason) ? "danger" : "neutral"}>
                      {REASONS[q.reason] ?? q.reason}
                    </Chip>
                    {answered && <Chip tone="good">Answered</Chip>}
                    {q.element_id && (
                      <button type="button" className="btn btn--link" onClick={() => q.element_id && onGoTo(q.element_id)}>
                        Go to {q.element_label}
                      </button>
                    )}
                    {onStatus && (
                      <Button onClick={() => onStatus(q.id, answered ? "open" : "answered")}>
                        {answered ? "Reopen" : "Mark answered"}
                      </Button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
