import { useState } from "react";
import {
  INTERVIEW_TYPE_LABELS,
  guideUrl,
  profileName,
  type GuideSummary,
  type InterviewType,
  type Profile,
  type ProfileInput,
} from "../../lib/interview";
import { Button, SegmentedControl, SelectField, TextField } from "../common";
import { FORMATS } from "../../lib/templates";
import "./interview.css";

// Interviewee profile form (PRD Appendix F.8 rule 1; C5a): a role or stakeholder group, never a
// person (constraint 10). Presentational: the screen saves it and passes back any refusal.

export interface RoleOption {
  id: string;
  name: string;
}

export interface ProfileFormProps {
  roles: readonly RoleOption[];
  /** Earlier interviews a follow-up can build on (the profile being edited is left out). */
  earlier: readonly Profile[];
  initial?: Profile | undefined;
  busy: boolean;
  /** The server's refusal: its message and the field it names. */
  error?: { message: string; field?: string | undefined } | null | undefined;
  onSave: (body: ProfileInput) => void;
  onCancel: () => void;
}

const TYPES: readonly InterviewType[] = ["landscape", "practice", "follow_up"];
const NO_ROLE = "";
const NO_EARLIER = "";

export function ProfileForm({ roles, earlier, initial, busy, error, onSave, onCancel }: ProfileFormProps) {
  const [type, setType] = useState<InterviewType>(initial?.interview_type ?? "practice");
  const [roleId, setRoleId] = useState(initial?.role_id ?? NO_ROLE);
  const [group, setGroup] = useState(initial?.stakeholder_group ?? "");
  const [referredBy, setReferredBy] = useState(initial?.referred_by_role ?? "");
  const [previous, setPrevious] = useState(initial?.previous_profile_id ?? NO_EARLIER);
  const [missing, setMissing] = useState(false);
  const errorFor = (field: string) => (error?.field === field ? error.message : null);
  return (
    <form
      className="stack profile-form"
      aria-label={initial ? "Edit interviewee" : "Add interviewee"}
      onSubmit={(event) => {
        event.preventDefault();
        if (!roleId && !group.trim()) {
          setMissing(true);
          return;
        }
        setMissing(false);
        onSave({
          interview_type: type,
          role_id: roleId || null,
          stakeholder_group: group.trim(),
          referred_by_role: referredBy.trim(),
          previous_profile_id: previous || null,
        });
      }}
    >
      <SegmentedControl
        label="Interview type"
        options={TYPES.map((value) => ({ value, label: INTERVIEW_TYPE_LABELS[value] }))}
        value={type}
        onChange={setType}
      />
      <SelectField
        label="Role"
        value={roleId}
        options={[{ value: NO_ROLE, label: "No role (stakeholder group only)" }, ...roles.map((r) => ({ value: r.id, label: r.name }))]}
        onChange={setRoleId}
        error={
          missing ? "Say whose interview this is: choose a role or name the stakeholder group." : errorFor("role_id")
        }
      />
      <TextField
        label="Stakeholder group"
        value={group}
        onChange={setGroup}
        help="A team or function, for example Ramp. Roles and groups only, never a person's name."
        error={errorFor("stakeholder_group")}
      />
      <TextField
        label="Referred by (role)"
        value={referredBy}
        onChange={setReferredBy}
        help="Fills the opener: who suggested this interview."
        error={errorFor("referred_by_role")}
      />
      {(type === "follow_up" || previous) && (
        <SelectField
          label="Earlier interview"
          value={previous}
          options={[
            { value: NO_EARLIER, label: "None" },
            ...earlier.map((p) => ({ value: p.id, label: `${profileName(p)} (${INTERVIEW_TYPE_LABELS[p.interview_type]})` })),
          ]}
          onChange={setPrevious}
          help="A follow-up picks up from this session."
          error={errorFor("previous_profile_id")}
        />
      )}
      {error && !error.field && (
        <p className="panel-danger" role="alert">
          {error.message}
        </p>
      )}
      <div className="profile-form__actions">
        <Button type="submit" variant="primary" disabled={busy}>
          {initial ? "Save interviewee" : "Add interviewee"}
        </Button>
        <Button onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  );
}

export interface ProfileListProps {
  profiles: readonly Profile[];
  onEdit: (profile: Profile) => void;
  /** Each interviewee's latest tailored guide (G2), by profile ID. */
  guides?: ReadonlyMap<string, GuideSummary> | undefined;
  /** Make a (new version of the) guide; without it the list shows no guide actions. */
  onMakeGuide?: ((profile: Profile) => void) | undefined;
  /** The interviewee whose guide is being made, and the stage it has reached. */
  making?: string | null | undefined;
  stage?: string | undefined;
  /** What became of the last guide asked for: the job's message, or why it failed. */
  outcome?: { profileId: string; message: string; failed: boolean } | null | undefined;
}

/** Make guide, then Download Word · Download Markdown of the latest version. */
function GuideActions({ profile, guide, onMake, making, stage, outcome }: {
  profile: Profile;
  guide: GuideSummary | undefined;
  onMake: (profile: Profile) => void;
  making: boolean;
  stage: string;
  outcome: { message: string; failed: boolean } | undefined;
}) {
  const name = profileName(profile);
  return (
    <div className="profile-list__guide">
      <p className="profile-list__meta">
        {guide
          ? `Guide version ${guide.version} (${INTERVIEW_TYPE_LABELS[guide.interview_type]})`
          : "No guide yet"}
      </p>
      <span className="template-downloads">
        {guide &&
          FORMATS.map(({ format, label }) => (
            <a
              key={format}
              className="btn btn--secondary"
              href={guideUrl(profile.engagement_id, profile.id, format)}
              download
            >
              Download {label} <span className="visually-hidden">guide for {name}</span>
            </a>
          ))}
        <Button onClick={() => { if (!making) onMake(profile); }} aria-busy={making}>
          {making ? "Making guide…" : guide ? "Make new version" : "Make guide"}{" "}
          <span className="visually-hidden">for {name}</span>
        </Button>
      </span>
      {making && stage && (
        <p className="profile-list__meta" role="status">
          {stage}…
        </p>
      )}
      {outcome?.failed && outcome.message && (
        <p className="panel-danger" role="alert">
          {outcome.message}
        </p>
      )}
      {outcome && !outcome.failed && outcome.message && (
        <p className="profile-list__meta" role="status">
          {outcome.message}
        </p>
      )}
    </div>
  );
}

/** The engagement's interviewees, oldest first, each with its interview type and what it builds on. */
export function ProfileList({ profiles, onEdit, guides, onMakeGuide, making, stage, outcome }: ProfileListProps) {
  const byId = new Map(profiles.map((p) => [p.id, p]));
  return (
    <ul className="profile-list" aria-label="Interviewees">
      {profiles.map((profile) => {
        const before = profile.previous_profile_id ? byId.get(profile.previous_profile_id) : undefined;
        return (
          <li key={profile.id} className="profile-list__item">
            <div className="profile-list__body">
              <p className="profile-list__name">{profileName(profile)}</p>
              <p className="profile-list__meta">
                {INTERVIEW_TYPE_LABELS[profile.interview_type]}
                {profile.referred_by_role && ` · referred by ${profile.referred_by_role}`}
                {before && ` · follows ${profileName(before)}`}
              </p>
              {onMakeGuide && (
                <GuideActions
                  profile={profile}
                  guide={guides?.get(profile.id)}
                  onMake={onMakeGuide}
                  making={making === profile.id}
                  stage={stage ?? ""}
                  outcome={outcome?.profileId === profile.id ? outcome : undefined}
                />
              )}
            </div>
            <Button variant="link" onClick={() => onEdit(profile)}>
              Edit <span className="visually-hidden">{profileName(profile)}</span>
            </Button>
          </li>
        );
      })}
    </ul>
  );
}
