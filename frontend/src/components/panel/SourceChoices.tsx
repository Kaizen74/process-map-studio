export interface SourceChoice {
  id: string;
  name: string;
  kind: string;
  passages: number;
}

export interface SourceChoicesProps {
  sources: readonly SourceChoice[];
  backLabel: string;
  onChoose: (id: string) => void;
  onBack: () => void;
}

/** The first step of picking a passage (Add missing step): which source it is in. */
export function SourceChoices({ sources, backLabel, onChoose, onBack }: SourceChoicesProps) {
  return (
    <section className="panel-viewer" aria-labelledby="source-choices-title">
      <button type="button" className="btn btn--link" onClick={onBack}>
        ← Back to {backLabel}
      </button>
      <h2 id="source-choices-title" className="panel-viewer__title">
        Pick a passage
      </h2>
      <p className="field__help">Choose the source, then use the passage the step comes from.</p>
      {sources.length === 0 ? (
        <p className="inline-note">
          No source has readable passages yet. Add one on the Sources screen, or add the step as recommended
          practice with a reference.
        </p>
      ) : (
        <ul className="source-choices" aria-label="Sources">
          {sources.map((s) => (
            <li key={s.id}>
              <button type="button" className="source-choice" onClick={() => onChoose(s.id)}>
                <span>{s.name}</span>
                <span className="source-choice__meta">
                  {s.kind} · {s.passages === 1 ? "1 passage" : `${s.passages} passages`}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
