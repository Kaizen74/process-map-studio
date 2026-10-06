import { useState } from "react";
import { useParams } from "react-router";
import { Button, EmptyState, ErrorState, Skeleton } from "../../components/common";
import { GuideEditor, ProfileForm, ProfileList, TemplateCard } from "../../components/interview";
import { TabBar } from "../../components/tabs";
import { useEngagement } from "../../hooks/useEngagements";
import {
  useAddProfile,
  useEditGuide,
  useEditProfile,
  useGuide,
  useGuides,
  useMakeGuide,
  useProfiles,
} from "../../hooks/useInterview";
import { useRoles } from "../../hooks/useRoles";
import { profileName, type Profile } from "../../lib/interview";
import { useTemplatePlans } from "../../hooks/useTemplates";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { QUESTION_ID_TIP } from "../../lib/templates";
import { EngagementProblem } from "../engagement/EngagementProblem";
import "./interview.css";

/** The server's refusal of a profile, as the form shows it. */
function refusal(error: unknown) {
  if (!error) return null;
  const field = (error as { details?: { field?: unknown } }).details?.field;
  return { message: messageOf(error), field: typeof field === "string" ? field : undefined };
}

/** The editor for one interviewee's latest guide (C5c). */
function GuidePanel({ engagementId, profileId, onClose }: { engagementId: string; profileId: string; onClose: () => void }) {
  const guide = useGuide(engagementId, profileId);
  const save = useEditGuide(engagementId, profileId);
  if (guide.isPending) return <Skeleton height="240px" />;
  if (guide.isError) {
    return (
      <ErrorState
        title="The guide couldn't be loaded"
        message={messageOf(guide.error)}
        details={copyDetailsOf(guide.error)}
        onRetry={() => void guide.refetch()}
      />
    );
  }
  return (
    <GuideEditor
      key={`${guide.data.id}-${guide.data.version}`}
      guide={guide.data}
      busy={save.isPending}
      error={refusal(save.error)}
      saved={save.isSuccess}
      onSave={(body) => save.mutate(body)}
      onClose={onClose}
    />
  );
}

/** Interviewees (C5a): whose interviews the tailored guides are for. */
function Interviewees({ engagementId }: { engagementId: string }) {
  const profiles = useProfiles(engagementId);
  const roles = useRoles(engagementId);
  const add = useAddProfile(engagementId);
  const edit = useEditProfile(engagementId);
  const guides = useGuides(engagementId);
  const make = useMakeGuide(engagementId);
  const [editing, setEditing] = useState<Profile | "new" | null>(null);
  const [open, setOpen] = useState<Profile | null>(null);
  const close = () => {
    setEditing(null);
    add.reset();
    edit.reset();
  };
  const list = profiles.data ?? [];
  const latest = new Map((guides.data ?? []).flatMap((g) => (g.profile_id ? [[g.profile_id, g] as const] : [])));
  // A refusal to start (the job never ran) shows under the interviewee like a failed job.
  const outcome =
    make.outcome && make.outcome.failed && !make.outcome.message && make.startError
      ? { ...make.outcome, message: messageOf(make.startError) }
      : make.outcome;
  return (
    <section className="interview-templates" aria-labelledby="interviewees-title">
      <h2 id="interviewees-title" className="interview-templates__title">
        Interviewees
      </h2>
      <p className="interview-tip">
        Who each interview is with, by role or stakeholder group (never a name). Make a tailored guide for each: the standard
        template of their interview type with the header, the opener and extra probes filled in from this engagement.
      </p>
      {profiles.isPending && <Skeleton height="96px" />}
      {profiles.isError && (
        <ErrorState
          title="The interviewees couldn't be loaded"
          message={messageOf(profiles.error)}
          details={copyDetailsOf(profiles.error)}
          onRetry={() => void profiles.refetch()}
        />
      )}
      {profiles.data && list.length === 0 && editing === null && (
        <EmptyState
          message="No interviewees yet. Add the role or stakeholder group you are about to interview, and the type of interview."
          action={<Button variant="primary" onClick={() => setEditing("new")}>Add interviewee</Button>}
        />
      )}
      {guides.isError && (
        <ErrorState
          title="The tailored guides couldn't be loaded"
          message={messageOf(guides.error)}
          details={copyDetailsOf(guides.error)}
          onRetry={() => void guides.refetch()}
        />
      )}
      {list.length > 0 && (
        <ProfileList
          profiles={list}
          onEdit={(p) => setEditing(p)}
          guides={latest}
          onMakeGuide={(p) => make.make(p.id)}
          onEditGuide={(p) => setOpen(p)}
          making={make.making}
          stage={make.stage}
          outcome={outcome}
        />
      )}
      {list.length > 0 && editing === null && (
        <div>
          <Button onClick={() => setEditing("new")}>Add interviewee</Button>
        </div>
      )}
      {editing !== null && (
        <ProfileForm
          key={editing === "new" ? "new" : editing.id}
          roles={roles.data ?? []}
          earlier={list.filter((p) => editing === "new" || p.id !== editing.id)}
          initial={editing === "new" ? undefined : editing}
          busy={add.isPending || edit.isPending}
          error={refusal(editing === "new" ? add.error : edit.error)}
          onSave={(body) => {
            if (editing === "new") add.mutate(body, { onSuccess: close });
            else edit.mutate({ id: editing.id, patch: body }, { onSuccess: close });
          }}
          onCancel={close}
        />
      )}
      {open && (
        <section className="interview-templates" aria-labelledby="guide-editor-title">
          <h2 id="guide-editor-title" className="interview-templates__title">
            Guide for {profileName(open)}
          </h2>
          <GuidePanel key={open.id} engagementId={engagementId} profileId={open.id} onClose={() => setOpen(null)} />
        </section>
      )}
    </section>
  );
}

type InterviewTab = "templates" | "guide";
const TABS: readonly { id: InterviewTab; label: string }[] = [
  { id: "templates", label: "Templates" },
  { id: "guide", label: "Guide" },
];

/** The three standard templates (always available). */
function Templates() {
  const plans = useTemplatePlans();
  return (
    <section className="interview-templates" aria-labelledby="templates-title">
      <h2 id="templates-title" className="interview-templates__title">
        Templates
      </h2>
      <p className="interview-tip">{QUESTION_ID_TIP}</p>
      {plans.isPending && (
        <div className="interview-templates__grid" aria-busy="true">
          <Skeleton height="260px" />
          <Skeleton height="260px" />
          <Skeleton height="260px" />
        </div>
      )}
      {plans.isError && (
        <ErrorState
          title="The interview templates couldn't be loaded"
          message={messageOf(plans.error)}
          details={copyDetailsOf(plans.error)}
          onRetry={() => void plans.refetch()}
        />
      )}
      {plans.data && (
        <div className="interview-templates__grid">
          {plans.data.map((template) => (
            <TemplateCard key={template.type} template={template} />
          ))}
        </div>
      )}
      <p className="interview-note">
        The coverage report is not available on this screen yet; the standard templates and tailored guides work for every
        interview in the meantime.
      </p>
    </section>
  );
}

/**
 * Interview (PRD §5.4): tabs for the standard templates (always available) and the Guide tab with
 * the interviewees and their tailored guides (C5a, G2, C5c). The Coverage tab follows (C5d).
 */
export function InterviewScreen() {
  const { engagementId = "" } = useParams();
  const engagement = useEngagement(engagementId);
  const [tab, setTab] = useState<InterviewTab>("templates");

  if (engagement.isError) {
    return <EngagementProblem error={engagement.error} onRetry={() => void engagement.refetch()} />;
  }

  return (
    <main className="screen" aria-labelledby="interview-title">
      <div>
        <h1 id="interview-title">Interview</h1>
        <p className="screen__intro">
          Standard interview templates give every interviewer the same questions, question IDs and minute plan. Download one,
          or make a guide tailored to an interviewee on the Guide tab, and use it during the interview; then upload the
          transcript on Sources.
        </p>
      </div>
      <TabBar label="Interview" tabs={TABS} active={tab} onChange={setTab}>
        {tab === "templates" && <Templates />}
        {tab === "guide" &&
          (engagement.data ? <Interviewees engagementId={engagementId} /> : <Skeleton height="96px" />)}
      </TabBar>
    </main>
  );
}
