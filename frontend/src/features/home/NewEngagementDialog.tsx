import { useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import type { EngagementCreate, HandoffPilot, HandoffPreview } from "../../api/types";
import { Button, CheckboxField, Dialog, SelectField, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { usePreviewHandoff } from "../../hooks/useCompass";
import { useCreateEngagement, useEngagement } from "../../hooks/useEngagements";
import { useRoles } from "../../hooks/useRoles";
import { engagementPath } from "../../lib/engagementSteps";
import { messageOf } from "../../lib/errors";
import { plural } from "../../lib/format";
import { validateEngagementName } from "../../lib/validation";
import "./home.css";

const NOT_JSON = "This file couldn't be read as a hand-off: it isn't a JSON file.";

interface Scope {
  process_name: string;
  process_kpi: string;
  industry: string;
}
const scopeOf = (pilot: HandoffPilot): Scope => ({
  process_name: pilot.process_name,
  process_kpi: pilot.process_kpi,
  industry: pilot.industry,
});

/**
 * Asks for a name, creates the engagement and opens its Setup screen (PRD §5.4 Home). Optionally
 * starts from a Capability Compass hand-off (DECISIONS 95): the file is previewed, Eric picks the
 * pilot and edits what it pre-fills, and nothing is created until he confirms.
 */
export function NewEngagementDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateEngagement();
  const preview = usePreviewHandoff();
  const navigate = useNavigate();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  // The hand-off as read from the file, its preview, and what Eric has chosen or typed over it.
  const [handoff, setHandoff] = useState<{ file: unknown; found: HandoffPreview } | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [pilotRef, setPilotRef] = useState("");
  const [scope, setScope] = useState<Scope>({ process_name: "", process_kpi: "", industry: "" });
  const [unticked, setUnticked] = useState<ReadonlySet<string>>(new Set());
  const pilot = handoff?.found.pilots.find((p) => p.ref === pilotRef) ?? null;
  // DECISIONS 98: the same pilot already mapped in another country, and whether to start from it.
  const [referenceId, setReferenceId] = useState("");
  const reference = useEngagement(referenceId || undefined).data;
  const referenceLanes = (useRoles(referenceId).data ?? []).map((r) => r.name);
  const fromReference = Boolean(referenceId && reference);
  const lanes = fromReference ? referenceLanes : (pilot?.in_scope_roles ?? []);
  const sameProcess = pilot?.same_process ?? [];

  function drop() {
    setHandoff(null);
    setFileError(null);
    setPilotRef("");
    setUnticked(new Set());
    setReferenceId("");
  }

  function close() {
    setName("");
    setError(null);
    drop();
    onClose();
  }

  function pick(next: HandoffPilot) {
    setPilotRef(next.ref);
    setName(next.name);
    setScope(scopeOf(next));
    setUnticked(new Set());
    setReferenceId("");
    setError(null);
  }

  async function read(file: File) {
    drop();
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      setFileError(NOT_JSON);
      return;
    }
    preview.mutate(parsed, {
      onSuccess: (found) => {
        setHandoff({ file: parsed, found });
        const first = found.pilots[0];
        if (first) pick(first);
      },
      onError: (e) => setFileError(messageOf(e)),
    });
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const problem = validateEngagementName(name);
    setError(problem);
    if (problem || create.isPending) return;
    const roles = pilot ? lanes.filter((r) => !unticked.has(r)) : [];
    const body: EngagementCreate =
      handoff && pilot && fromReference
        ? {
            // The other country's process name, trigger, end point, KPI, in-scope roles and
            // conventions are copied by the backend (DECISIONS 98); the lanes are those ticked.
            name: name.trim(),
            industry: scope.industry.trim(),
            role_names: roles,
            compass: { handoff: handoff.file, pilot_ref: pilot.ref },
            reference_engagement_id: referenceId,
          }
        : handoff && pilot
        ? {
            name: name.trim(),
            process_name: scope.process_name.trim(),
            process_kpi: scope.process_kpi.trim(),
            industry: scope.industry.trim(),
            in_scope_roles: roles,
            role_names: roles,
            compass: { handoff: handoff.file, pilot_ref: pilot.ref },
          }
        : { name: name.trim() };
    create.mutate(body, {
      onSuccess: (engagement) => {
        toast("Engagement created.");
        close();
        void navigate(engagementPath(engagement.id, "setup"));
      },
      onError: (e) => setError(messageOf(e)),
    });
  }

  return (
    <Dialog
      open={open}
      title="New engagement"
      description="One engagement maps one process. You can change the name and add its scope on the next screen."
      onClose={close}
      actions={
        <>
          <Button onClick={close}>Cancel</Button>
          <Button variant="primary" type="submit" form="new-engagement-form">
            {create.isPending ? "Creating…" : "Create engagement"}
          </Button>
        </>
      }
    >
      <form id="new-engagement-form" className="new-engagement" onSubmit={onSubmit} noValidate>
        {!handoff && (
          <div className="handoff-start">
            <Button onClick={() => input.current?.click()}>
              {preview.isPending ? "Reading the file…" : "Start from a Capability Compass hand-off…"}
            </Button>
            <p className="field__help">
              Optional. Choose the hand-off file to pre-fill this engagement; you check everything before it is created.
            </p>
            <input
              ref={input}
              type="file"
              accept=".json,application/json"
              className="visually-hidden"
              tabIndex={-1}
              aria-hidden="true"
              data-testid="handoff-file-input"
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void read(file);
              }}
            />
            {fileError && (
              <p className="field__error" role="alert">
                {fileError}
              </p>
            )}
          </div>
        )}
        {handoff && pilot && (
          <div className="handoff-found">
            <p className="handoff-found__from">
              <span className="mono">{handoff.found.key}</span> · {handoff.found.organisation}
            </p>
            {!handoff.found.ready && (
              <p className="handoff-found__warning" role="note">
                Capability Compass marks this hand-off as not ready
                {handoff.found.verdict ? `: ${handoff.found.verdict}.` : "."} You can still use it.
                {handoff.found.open.length > 0 && ` Still open there: ${handoff.found.open.join("; ")}.`}
              </p>
            )}
            <SelectField
              label="Pilot"
              value={pilot.ref}
              options={handoff.found.pilots.map((p) => ({ value: p.ref, label: `${p.ref} · ${p.process_name}` }))}
              onChange={(ref) => {
                const next = handoff.found.pilots.find((p) => p.ref === ref);
                if (next) pick(next);
              }}
              help={
                <>
                  Cluster <span className="mono">{pilot.cluster_ref}</span> {pilot.cluster_name}
                </>
              }
            />
          </div>
        )}
        {handoff && pilot && sameProcess.length > 0 && (
          <fieldset className="role-picks">
            <legend>{sameProcessQuestion(sameProcess, pilot.ref, pilot.process_name)}</legend>
            <p className="field__help">
              Yes copies its process name, trigger, end point, KPI, in-scope roles, conventions and the lanes you tick.
              No document, transcript, map or code is copied: this country has its own sources.
            </p>
            {sameProcess.map((m) => (
              <label key={m.engagement_id} className="radio-row">
                <input
                  type="radio"
                  name="start-from"
                  checked={referenceId === m.engagement_id}
                  onChange={() => {
                    setReferenceId(m.engagement_id);
                    setUnticked(new Set());
                  }}
                />
                Yes, start from {m.name}
                {m.country ? ` (${m.country})` : ""}
              </label>
            ))}
            <label className="radio-row">
              <input
                type="radio"
                name="start-from"
                checked={referenceId === ""}
                onChange={() => {
                  setReferenceId("");
                  setUnticked(new Set());
                }}
              />
              No, use the hand-off only
            </label>
          </fieldset>
        )}
        <TextField
          label="Engagement name"
          value={name}
          onChange={setName}
          error={error}
          help="Usually the process, for example “Aircraft load control”."
        />
        {handoff && pilot && fromReference && reference && (
          <p className="field__help" role="note">
            From {reference.name}: process name “{reference.process_name || "not given"}”, trigger “
            {reference.trigger || "not given"}”, end point “{reference.end_point || "not given"}”, KPI “
            {reference.process_kpi || "not given"}”. You can change them on Setup.
          </p>
        )}
        {handoff && pilot && (
          <>
            {!fromReference && (
              <>
                <TextField
                  label="Process name"
                  value={scope.process_name}
                  onChange={(v) => setScope((s) => ({ ...s, process_name: v }))}
                />
                <TextField
                  label="Process KPI"
                  value={scope.process_kpi}
                  onChange={(v) => setScope((s) => ({ ...s, process_kpi: v }))}
                />
              </>
            )}
            <TextField
              label="Industry"
              value={scope.industry}
              onChange={(v) => setScope((s) => ({ ...s, industry: v }))}
            />
            {lanes.length > 0 && (
              <fieldset className="role-picks">
                <legend>Roles to create as lanes</legend>
                <p className="field__help">
                  {fromReference
                    ? `The lanes of ${reference?.name ?? "the other country"}. Untick any this country doesn't have.`
                    : "Untick any this map doesn't need. You can add or remove roles later."}
                </p>
                {lanes.map((role) => (
                  <CheckboxField
                    key={role}
                    label={role}
                    checked={!unticked.has(role)}
                    onChange={(checked) =>
                      setUnticked((current) => {
                        const next = new Set(current);
                        if (checked) next.delete(role);
                        else next.add(role);
                        return next;
                      })
                    }
                  />
                ))}
              </fieldset>
            )}
            <p className="field__help">
              Also brought along: {plural(handoff.found.principles.length, "design principle")} to test and{" "}
              {plural(pilot.interview_prompts.length, "suggested interview probe")} (prompts for your guides, never
              evidence). Its IDs are kept exactly as written.
            </p>
            <div>
              <Button variant="link" onClick={drop}>
                Don't use this hand-off
              </Button>
            </div>
          </>
        )}
      </form>
    </Dialog>
  );
}

/** "Arden already maps VS-01 Bid to contract renewal. Start from its scope card, conventions and lanes?" */
function sameProcessQuestion(found: { name: string; country: string }[], ref: string, process: string): string {
  const who = found.map((f) => f.country || f.name).join(" and ");
  if (found.length === 1) return `${who} already maps ${ref} ${process}. Start from its scope card, conventions and lanes?`;
  return `${who} already map ${ref} ${process}. Start from one's scope card, conventions and lanes?`;
}
