import type { CapabilityNote, GlossaryEntry, StoryEntry } from "../../lib/mapTypes";
import { FRAGMENT_TYPES } from "../../lib/panelText";
import { byDimension, causeTypeLabel } from "../../lib/registers";
import { Chip } from "../common";
import "../tabs/tabs.css";
import "./registers.css";

// The Registers lists made from the interviews (P9u; PRD §5.4, criteria 59 and 73): Stories,
// Glossary and Preserve / Improve. The SME's own words are shown as quotes; the steps each item is
// about link to the map. Presentational: the screen fetches and knows which steps are on the map.

export interface StepLinks {
  /** The labels of the steps on the map being shown: only these get a Go to link. */
  onMap: ReadonlySet<string>;
  onGoTo: (label: string) => void;
}

function Steps({ steps, links }: { steps: readonly string[]; links: StepLinks }) {
  if (steps.length === 0) return <p className="register-card__meta">Not linked to a step.</p>;
  return (
    <p className="register-card__steps">
      {steps.map((label) =>
        links.onMap.has(label) ? (
          <button key={label} type="button" className="btn btn--link" onClick={() => links.onGoTo(label)}>
            Go to {label}
          </button>
        ) : (
          <span key={label} className="register-card__meta">
            {label} (not on this map)
          </span>
        ),
      )}
    </p>
  );
}

/** Stories (§3.12.2): every fragment the interviews told, kept when told once. */
export function StoryList({ stories, links }: { stories: readonly StoryEntry[]; links: StepLinks }) {
  if (stories.length === 0) {
    return (
      <p className="tab-empty">
        No stories yet. A story appears here when an interviewee tells what happened in a real case, good or bad.
      </p>
    );
  }
  return (
    <ul className="tab-cards" aria-label="Stories">
      {stories.map((story, n) => (
        <li key={`${story.segment_id ?? n}-${story.label}`} className="register-card">
          <p className="register-card__title">
            {story.label} <Chip>{FRAGMENT_TYPES[story.fragment_type] ?? story.fragment_type}</Chip>
            {story.single_account && (
              <Chip dashed>Told once</Chip>
            )}
          </p>
          {story.signifiers.length > 0 && (
            <p>
              <span className="register-card__meta">In their words: </span>
              {story.signifiers.map((word, i) => (
                <q key={i}>{word}</q>
              ))}
            </p>
          )}
          {story.frequency && <p>How often: {story.frequency}</p>}
          <p>
            <q>{story.quote}</q>
            {story.anchor && <span className="register-card__meta mono"> · {story.anchor}</span>}
          </p>
          <Steps steps={story.steps} links={links} />
        </li>
      ))}
    </ul>
  );
}

/** Glossary (§3.12.2): the SME's own terms, in the order first heard, with a plain meaning. */
export function GlossaryList({ entries, links }: { entries: readonly GlossaryEntry[]; links: StepLinks }) {
  if (entries.length === 0) {
    return <p className="tab-empty">No terms yet. A term appears here when interviewees use their own word for something.</p>;
  }
  return (
    <ul className="tab-cards" aria-label="Glossary">
      {entries.map((entry) => (
        <li key={entry.term} className="register-card">
          <p className="register-card__title">
            <q>{entry.term}</q>
            {entry.anchor && <span className="register-card__meta mono"> · {entry.anchor}</span>}
          </p>
          <p>{entry.plain_meaning}</p>
          <Steps steps={entry.steps} links={links} />
        </li>
      ))}
    </ul>
  );
}

function NoteCard({ note, links }: { note: CapabilityNote; links: StepLinks }) {
  return (
    <li className="register-card">
      <p className="register-card__title">{note.text}</p>
      {note.kind === "weakness" && note.cause_type && (
        <p>
          <span className="register-card__meta">Cause type (inferred): </span>
          {causeTypeLabel(note.cause_type)}
        </p>
      )}
      <p>
        <q>{note.quote}</q>
        {note.anchor && <span className="register-card__meta mono"> · {note.anchor}</span>}
      </p>
      <Steps steps={note.steps} links={links} />
    </li>
  );
}

/** Preserve / Improve (§3.12.10 rule 10, criterion 73): strengths and weaknesses by dimension. */
export function PreserveImproveList({ notes, links }: { notes: readonly CapabilityNote[]; links: StepLinks }) {
  if (notes.length === 0) {
    return (
      <p className="tab-empty">
        No strengths or weaknesses yet. They appear here when interviewees say what works well and what doesn&apos;t.
      </p>
    );
  }
  const sides = [
    { kind: "strength", heading: "Preserve: what works well", empty: "No strengths stated." },
    { kind: "weakness", heading: "Improve: what gets in the way", empty: "No weaknesses stated." },
  ] as const;
  return (
    <div className="exceptions">
      {sides.map((side) => {
        const groups = byDimension(notes.filter((n) => n.kind === side.kind));
        return (
          <section key={side.kind} aria-label={side.heading}>
            <h2 className="register-heading">{side.heading}</h2>
            {groups.length === 0 && <p className="tab-empty">{side.empty}</p>}
            {groups.map((group) => (
              <div key={group.dimension}>
                <h3 className="register-subheading">{group.label}</h3>
                <ul className="tab-cards" aria-label={`${side.heading}, ${group.label}`}>
                  {group.notes.map((note, n) => (
                    <NoteCard key={`${note.segment_id ?? n}-${note.text}`} note={note} links={links} />
                  ))}
                </ul>
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
