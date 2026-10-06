import { useState } from "react";
import type { Theme, ThemeStatus } from "../../lib/registers";
import { Button, Chip, TextField } from "../common";
import "./registers.css";

// Emerging themes (PRD Appendix E tier 3, §3.12.9 rule 3, criterion 58; C7b): patterns across two
// or more stories, proposed by Claude and checked by the app. Eric accepts, renames or dismisses
// them; they never change the map. Presentational: the screen saves.

const STATUS_LABELS: Record<ThemeStatus, string> = {
  proposed: "Proposed",
  accepted: "Accepted",
  dismissed: "Dismissed",
};

export interface ThemeListProps {
  themes: readonly Theme[];
  busyId: string | null;
  /** The server's refusal of a rename, for that theme. */
  error?: { themeId: string; message: string } | null | undefined;
  onDecide: (theme: Theme, status: ThemeStatus, name?: string) => void;
}

function ThemeCard({ theme, busy, error, onDecide }: {
  theme: Theme;
  busy: boolean;
  error: string | undefined;
  onDecide: ThemeListProps["onDecide"];
}) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(theme.theme);
  const proposed = theme.status === "proposed";
  return (
    <li className="register-card" aria-busy={busy || undefined}>
      <p className="register-card__title">
        {theme.theme}{" "}
        <Chip tone={theme.status === "accepted" ? "good" : "neutral"} dashed={proposed}>
          {STATUS_LABELS[theme.status as ThemeStatus] ?? theme.status}
        </Chip>
      </p>
      <p>
        <span className="register-card__meta">What the stories have in common (inferred): </span>
        {theme.basis}
      </p>
      <ul className="register-card__fragments" aria-label={`Stories behind ${theme.theme}`}>
        {theme.fragments.map((f) => (
          <li key={f.claim_id}>
            {f.text}
            {f.anchor && <span className="register-card__meta mono"> · {f.anchor}</span>}
          </li>
        ))}
      </ul>
      {renaming ? (
        <form
          className="question__meta"
          aria-label={`Rename ${theme.theme}`}
          onSubmit={(event) => {
            event.preventDefault();
            onDecide(theme, "accepted", name);
            setRenaming(false);
          }}
        >
          <TextField label="New name" value={name} onChange={setName} error={error ?? null} />
          <Button type="submit" variant="primary">
            Accept with this name
          </Button>
          <Button onClick={() => setRenaming(false)}>Cancel</Button>
        </form>
      ) : (
        <div className="question__meta">
          {theme.status !== "accepted" && <Button onClick={() => onDecide(theme, "accepted")}>Accept</Button>}
          <Button onClick={() => setRenaming(true)}>
            Rename <span className="visually-hidden">{theme.theme}</span>
          </Button>
          {theme.status !== "dismissed" && <Button onClick={() => onDecide(theme, "dismissed")}>Dismiss</Button>}
          {!proposed && <Button onClick={() => onDecide(theme, "proposed")}>Reopen</Button>}
        </div>
      )}
      {error && !renaming && (
        <p className="panel-danger" role="alert">
          {error}
        </p>
      )}
    </li>
  );
}

export function ThemeList({ themes, busyId, error, onDecide }: ThemeListProps) {
  if (themes.length === 0) {
    return (
      <p className="tab-empty">
        No emerging themes. One is proposed when two or more stories share a pattern that fits no existing category.
      </p>
    );
  }
  return (
    <ul className="tab-cards">
      {themes.map((theme) => (
        <ThemeCard
          key={theme.id}
          theme={theme}
          busy={busyId === theme.id}
          error={error?.themeId === theme.id ? error.message : undefined}
          onDecide={onDecide}
        />
      ))}
    </ul>
  );
}
