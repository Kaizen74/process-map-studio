import { useState } from "react";
import { Link } from "react-router";
import type { Role, Speaker } from "../../api/types";
import { Button, Card, ErrorState, Skeleton } from "../../components/common";
import { useToast } from "../../components/shell";
import { useMapSpeakers, useSpeakers } from "../../hooks/useSources";
import { engagementPath } from "../../lib/engagementSteps";
import { copyDetailsOf, messageOf } from "../../lib/errors";
import { plural } from "../../lib/format";

const INTERVIEWER = "interviewer";

function current(speaker: Speaker): string {
  return speaker.is_interviewer ? INTERVIEWER : (speaker.role_id ?? "");
}

export interface SpeakerMappingProps {
  engagementId: string;
  sourceId: string;
  roles: readonly Role[];
  /** An email thread (R11): its speakers are the senders, and there is no interviewer. */
  senders?: boolean;
}

/**
 * Speaker mapping (PRD §5.4 Sources): each speaker label → a role or Interviewer; for an email
 * thread (R11), each sender → a role. One of the three owner-only places where speaker names are
 * shown (PRD §3.8 G10).
 */
export function SpeakerMapping({ engagementId, sourceId, roles, senders = false }: SpeakerMappingProps) {
  const who = senders ? "sender" : "speaker";
  const speakers = useSpeakers(sourceId);
  const save = useMapSpeakers(engagementId, sourceId);
  const toast = useToast();
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  if (speakers.isError) {
    return (
      <ErrorState
        title="The speakers couldn't be loaded"
        message={messageOf(speakers.error)}
        details={copyDetailsOf(speakers.error)}
        onRetry={() => void speakers.refetch()}
      />
    );
  }
  const list = speakers.data ?? [];
  if (speakers.isSuccess && list.length === 0) return null;

  const chosen = (s: Speaker) => choices[s.label] ?? current(s);
  const changed = list.filter((s) => chosen(s) !== current(s));
  const unmapped = list.filter((s) => chosen(s) === "").length;

  function onSave() {
    setError(null);
    if (changed.length === 0) {
      setError(`Nothing has changed. Choose a role for a ${who} first.`);
      return;
    }
    const mapping = Object.fromEntries(changed.map((s) => [s.label, chosen(s) || null]));
    save.mutate(mapping, {
      onSuccess: () => {
        setChoices({});
        toast(`${plural(changed.length, who)} saved.`);
      },
      onError: (e) => setError(messageOf(e)),
    });
  }

  return (
    <div data-owner-only="speaker-mapping">
      <Card
        title={senders ? "Sender mapping" : "Speaker mapping"}
        description={
          senders
            ? "Map each sender to their role. Names stay in this card and the list of names to hide; everywhere else the app shows the role."
            : "Map each speaker to their role, or mark the interviewer. Names stay in this card and the list of names to hide; everywhere else the app shows the role."
        }
      >
        {speakers.isPending ? (
          <div className="stack" aria-busy="true">
            <Skeleton height="28px" />
            <Skeleton height="28px" />
          </div>
        ) : (
          <div className="stack">
            {roles.length === 0 && (
              <p className="inline-note">
                There are no roles yet.{" "}
                <Link to={engagementPath(engagementId, "setup")}>Add roles on the Setup screen</Link>, then come back
                to map the {who}s.
              </p>
            )}
            <table className="speakers">
              <caption className="visually-hidden">{senders ? "Senders in this email" : "Speakers in this transcript"}</caption>
              <thead>
                <tr>
                  <th scope="col">{senders ? "Sender in the file" : "Speaker in the file"}</th>
                  <th scope="col">Passages</th>
                  <th scope="col">Role</th>
                </tr>
              </thead>
              <tbody>
                {list.map((speaker) => (
                  <tr key={speaker.label}>
                    <th scope="row">{speaker.label}</th>
                    <td className="mono">{speaker.segment_count}</td>
                    <td>
                      <select
                        className="field__control speakers__select"
                        aria-label={`Role for ${speaker.label}`}
                        value={chosen(speaker)}
                        onChange={(event) =>
                          setChoices((c) => ({ ...c, [speaker.label]: event.target.value }))
                        }
                      >
                        <option value="">Not mapped yet</option>
                        {!senders && <option value={INTERVIEWER}>Interviewer</option>}
                        {roles.map((role) => (
                          <option key={role.id} value={role.id}>
                            {role.name}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="speakers__actions">
              <Button variant="primary" onClick={onSave}>
                {save.isPending ? "Saving…" : senders ? "Save senders" : "Save speakers"}
              </Button>
              <span className="inline-note" aria-live="polite">
                {unmapped === 0 ? `Every ${who} is mapped.` : `${plural(unmapped, who)} not mapped yet.`}
              </span>
            </div>
            {error && (
              <p className="field__error" role="alert">
                {error}
              </p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
