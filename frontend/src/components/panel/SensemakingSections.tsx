import type { ReactNode } from "react";
import type {
  AnswerQuote,
  AshenCategory,
  ElementDetail,
  KnowHow,
  StoryCard,
  WorkType,
} from "../../lib/mapTypes";
import {
  CONSTRAINT_TYPES,
  FRAGMENT_TYPES,
  KNOWLEDGE_RISK,
  words,
} from "../../lib/panelText";
import { Chip, WorkTypeGlyph } from "../common";
import { PanelSection as Section } from "./PanelSections";
import { WorkTypeChoice, type WorkTypeChoiceProps } from "./WorkTypeChoice";

// The detail panel's sensemaking sections (PRD §5.7.7 4a-4d; V3): the kind of work, the know-how
// at the step, the stories told about it and the official and lived accounts. The SME's own words
// come first and are shown as quotes; the model's reading is labelled as such. Read-only.

/** A passage the panel can open in the source viewer, at the exact place. */
export interface PassageLink {
  source_id: string;
  segment_id: string | null;
  anchor: string;
  quote: string;
}

type Open = (passage: PassageLink) => void;

/** The mono anchor of a passage; a button opening it where there is one. */
function Anchor({ passage, onOpen }: { passage: PassageLink; onOpen: Open }) {
  if (!passage.segment_id || !passage.anchor) return null;
  return (
    <button
      type="button"
      className="btn btn--link mono sense-anchor"
      onClick={() => onOpen(passage)}
    >
      {passage.anchor}
      <span className="visually-hidden"> (open the passage)</span>
    </button>
  );
}

function Quote({ text }: { text: string }) {
  return <q className="sense-quote">{text}</q>;
}

/** 4a: the work type with its quoted cues; the SME's own word for it first, if a story gave one. */
export function WorkTypeSection({
  element,
  typicalResponses = [],
  onOpen,
  choice,
}: {
  element: ElementDetail;
  typicalResponses?: readonly string[];
  onOpen: Open;
  /** Confirm or change (V3b); omitted where the version can't change. */
  choice?: Omit<WorkTypeChoiceProps, "type" | "confirmed"> | undefined;
}) {
  const type = (element.work_type ?? null) as WorkType | null;
  if (!type) return null;
  const said = [
    ...new Set((element.stories ?? []).flatMap((s) => s.signifiers)),
  ];
  const cues = element.work_type_cues ?? [];
  const complex = type === "complex" || type === "chaotic";
  const knowHow = element.know_how ?? null;
  return (
    <Section title="Work type">
      {said.length > 0 && (
        <p className="sense-said">
          SME said:{" "}
          {said.map((word, i) => (
            <Quote key={i} text={word} />
          ))}
          <span className="sense-note">
            {" "}
            (about one occasion; it doesn't set the step's work type)
          </span>
        </p>
      )}
      <p className="sense-line">
        <WorkTypeGlyph
          type={type}
          proposed={element.work_type_status === "proposed"}
        />
        {element.constraint_type && (
          <span className="sense-note">
            {" "}
            ·{" "}
            {CONSTRAINT_TYPES[element.constraint_type] ??
              words(element.constraint_type)}
          </span>
        )}
      </p>
      {type === "not_classified" ? (
        <p className="sense-note">
          No cue in the interviews shows the kind of work yet; a question asks
          about it.
        </p>
      ) : (
        <ul className="sense-list" aria-label="Cues">
          {cues.map((cue, i) => (
            <li key={i}>
              <Quote text={cue.quote} />{" "}
              <Anchor passage={cue} onOpen={onOpen} />
            </li>
          ))}
        </ul>
      )}
      {complex && (
        <dl className="panel-rows">
          {knowHow && knowHow.attended.length > 0 && (
            <div>
              <dt>Signals watched</dt>
              <dd>{knowHow.attended.join("; ")}</dd>
            </div>
          )}
          {knowHow && knowHow.ashen.heuristics.length > 0 && (
            <div>
              <dt>Rules of thumb</dt>
              <dd>{knowHow.ashen.heuristics.map((h) => h.text).join("; ")}</dd>
            </div>
          )}
          {typicalResponses.length > 0 && (
            <div>
              <dt>Typical responses</dt>
              <dd>{typicalResponses.join(" · ")}</dd>
            </div>
          )}
        </dl>
      )}
      {choice && (
        <WorkTypeChoice
          key={`${element.id}-${type}`}
          type={type}
          confirmed={element.work_type_status === "confirmed"}
          {...choice}
        />
      )}
    </Section>
  );
}

const ASHEN: readonly [AshenCategory, string][] = [
  ["artefacts", "Artefacts"],
  ["skills", "Skills"],
  ["heuristics", "Heuristics"],
  ["experience", "Experience"],
  ["natural_talent", "Natural talent (role level)"],
];

function infoRow(label: string, values: readonly string[]): ReactNode {
  if (values.length === 0) return null;
  return (
    <div>
      <dt>{label}</dt>
      <dd>{values.join("; ")}</dd>
    </div>
  );
}

/** 4b: ASHEN at the knowledge disclosure point, the knowledge risk and why, and the information. */
export function KnowHowSection({
  knowHow,
  onOpen,
}: {
  knowHow: KnowHow | null | undefined;
  onOpen: Open;
}) {
  if (!knowHow) return null;
  return (
    <Section
      title="Know-how"
      note={
        knowHow.kdp_type === "judgment" ? "a judgment step" : "a decision point"
      }
    >
      <ul className="sense-list" aria-label="ASHEN">
        {ASHEN.map(([key, label]) => (
          <li key={key}>
            <span className="sense-label">{label}</span>
            {knowHow.ashen[key].length === 0 ? (
              <span className="sense-note"> Not described</span>
            ) : (
              knowHow.ashen[key].map((item, i) => (
                <span key={i} className="sense-item">
                  {" "}
                  {item.text} <Anchor passage={item} onOpen={onOpen} />
                </span>
              ))
            )}
          </li>
        ))}
      </ul>
      <p>
        Knowledge risk:{" "}
        <strong>
          {KNOWLEDGE_RISK[knowHow.knowledge_risk] ??
            words(knowHow.knowledge_risk)}
        </strong>
        . {knowHow.risk_reason}
      </p>
      <dl className="panel-rows">
        {knowHow.cadence && (
          <div>
            <dt>How often</dt>
            <dd>{words(knowHow.cadence)}</dd>
          </div>
        )}
        {infoRow("Information received", knowHow.received)}
        {infoRow("Paid attention to", knowHow.attended)}
        {infoRow("Would like to have", knowHow.wanted)}
        {infoRow("Passed on by", knowHow.communicated_via)}
      </dl>
    </Section>
  );
}

/** 4c: the stories told about the step, in the SME's words, kept when told once. */
export function StoriesSection({
  stories,
  onOpen,
}: {
  stories: readonly StoryCard[] | undefined;
  onOpen: Open;
}) {
  if (!stories || stories.length === 0) return null;
  return (
    <Section title="Stories">
      <ul className="sense-cards">
        {stories.map((story, i) => (
          <li key={i} className="sense-card">
            <p className="sense-card__label">{story.label}</p>
            <p className="sense-card__meta">
              <Chip>
                {FRAGMENT_TYPES[story.fragment_type] ??
                  words(story.fragment_type)}
              </Chip>
              {story.single_account && <Chip>Single account</Chip>}
              {story.frequency && (
                <span className="sense-note">How often: {story.frequency}</span>
              )}
            </p>
            {story.signifiers.length > 0 && (
              <p>
                In the SME's words:{" "}
                {story.signifiers.map((word, n) => (
                  <Quote key={n} text={word} />
                ))}
              </p>
            )}
            <p>
              <Quote text={story.quote} />{" "}
              <Anchor passage={story} onOpen={onOpen} />
            </p>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function AnswerCard({ answer, onOpen }: { answer: AnswerQuote; onOpen: Open }) {
  return (
    <div className="sense-card">
      <p>
        <Quote text={answer.quote} />{" "}
        <Anchor passage={answer} onOpen={onOpen} />
      </p>
      {answer.stated_reason && (
        <p>
          Reason given: <Quote text={answer.stated_reason} />
        </p>
      )}
      {answer.question_id && (
        <p className="sense-note">
          Asked: <span className="mono">[{answer.question_id}]</span>{" "}
          {answer.question}
        </p>
      )}
    </div>
  );
}

const VARIANT_LABELS: Readonly<Record<string, string>> = {
  owner: "Owner",
  threshold: "Rule or threshold",
  time: "Time",
  trigger: "Trigger",
};

/**
 * 4d: the official account beside the lived one, with the SME's stated reason; "Practice not
 * described" when only the official account exists; and both views' values where they differ.
 */
export function OfficialLivedSection({
  element,
  onOpen,
}: {
  element: ElementDetail;
  onOpen: Open;
}) {
  const answers = element.answers ?? [];
  const official = answers.filter((a) => a.account_type === "official");
  const lived = answers.filter((a) => a.account_type === "lived");
  const variants = element.variants ?? null;
  const keys = variants
    ? [
        ...new Set([
          ...Object.keys(variants.done ?? {}),
          ...Object.keys(variants.documented ?? {}),
        ]),
      ]
    : [];
  if (official.length === 0 && keys.length === 0) return null;
  return (
    <Section title="Official vs lived">
      {official.length > 0 && (
        <div className="panel-pair">
          <div>
            <p className="sense-label">Official</p>
            {official.map((a, i) => (
              <AnswerCard key={i} answer={a} onOpen={onOpen} />
            ))}
          </div>
          <div>
            <p className="sense-label">Lived</p>
            {lived.length === 0 ? (
              <p className="sense-note">Practice not described</p>
            ) : (
              lived.map((a, i) => (
                <AnswerCard key={i} answer={a} onOpen={onOpen} />
              ))
            )}
          </div>
        </div>
      )}
      {keys.length > 0 && <p className="sense-label">Where the views differ</p>}
      {keys.length > 0 && (
        <dl className="panel-rows">
          {keys.map((key) => (
            <div key={key}>
              <dt>{VARIANT_LABELS[key] ?? words(key)}</dt>
              <dd>
                As done: {variants?.done?.[key] ?? "not stated"} · As
                documented: {variants?.documented?.[key] ?? "not stated"}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </Section>
  );
}
