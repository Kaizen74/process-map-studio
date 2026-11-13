import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import type { Engagement } from "../../api/types";
import {
  Button,
  Card,
  CheckboxField,
  Dialog,
  TextField,
} from "../../components/common";
import { useToast } from "../../components/shell";
import { useAnotherCountry } from "../../hooks/useEngagements";
import { useRoles } from "../../hooks/useRoles";
import { useVersions } from "../../hooks/useVersions";
import { fieldOf, messageOf } from "../../lib/errors";

/**
 * Map this process in another country (2026-11-13, DECISIONS 98): a new engagement for another
 * country, started from this one's scope card, conventions and the lane names Eric leaves ticked.
 * Unlike Map another flow, no document, map, code or name to hide comes along: another country
 * has its own sources. Offered once this engagement has a published version.
 */
export function AnotherCountryCard({ engagement }: { engagement: Engagement }) {
  const start = useAnotherCountry(engagement.id);
  const roles = useRoles(engagement.id).data ?? [];
  const versions = useVersions(engagement.id).data ?? [];
  const published = versions.some(
    (v) => v.state === "published" || v.state === "superseded",
  );
  const navigate = useNavigate();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [country, setCountry] = useState("");
  const [name, setName] = useState("");
  const [errors, setErrors] = useState<{ country?: string; name?: string }>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [leftBehind, setLeftBehind] = useState<ReadonlySet<string>>(new Set());
  const kept = roles.filter((r) => !leftBehind.has(r.id));

  function tick(roleId: string, bring: boolean) {
    setLeftBehind((current) => {
      const next = new Set(current);
      if (bring) next.delete(roleId);
      else next.add(roleId);
      return next;
    });
  }

  function close() {
    setOpen(false);
    setCountry("");
    setName("");
    setErrors({});
    setFormError(null);
    setLeftBehind(new Set());
  }

  function onSubmit(event?: FormEvent) {
    event?.preventDefault();
    if (!country.trim()) {
      setErrors({ country: "Type the country this map will cover." });
      return;
    }
    if (start.isPending) return;
    const body = {
      country: country.trim(),
      ...(name.trim() ? { name: name.trim() } : {}),
      ...(leftBehind.size > 0 ? { role_ids: kept.map((r) => r.id) } : {}),
    };
    start.mutate(body, {
      onSuccess: (made) => {
        close();
        toast(
          `Started ${made.name} with this scope card, conventions and lanes. Add its own sources, then draft it.`,
        );
        void navigate(`/engagements/${encodeURIComponent(made.id)}/setup`);
      },
      onError: (e) => {
        const field = fieldOf(e);
        if (field === "country" || field === "name")
          setErrors({ [field]: messageOf(e) });
        else setFormError(messageOf(e));
      },
    });
  }

  const process = engagement.process_name || engagement.name;
  return (
    <Card
      title="The same process in another country"
      description="Map this process in another country to compare the two maps later. The new engagement starts with this scope card, conventions and lanes, and its own sources: no document, map or name crosses."
    >
      {published ? (
        <div>
          <Button onClick={() => setOpen(true)}>
            Map this process in another country…
          </Button>
        </div>
      ) : (
        <p className="field__help">
          Publish a version of this map first: another country starts from a
          published map.
        </p>
      )}
      <Dialog
        open={open}
        title="Map this process in another country"
        description={`A new engagement for ${process} in another country. ${engagement.name} stays as it is.`}
        onClose={close}
        actions={
          <>
            <Button onClick={close}>Cancel</Button>
            <Button variant="primary" onClick={() => onSubmit()}>
              {start.isPending ? "Starting…" : "Start this country"}
            </Button>
          </>
        }
      >
        <form className="setup-form" onSubmit={onSubmit} noValidate>
          <TextField
            label="Country"
            value={country}
            onChange={(v) => {
              setCountry(v);
              setErrors({});
            }}
            error={errors.country ?? null}
            help={
              engagement.country
                ? `This map covers ${engagement.country}.`
                : "For example Belmar."
            }
          />
          <TextField
            label="Engagement name (optional)"
            value={name}
            onChange={setName}
            error={errors.name ?? null}
            help={`Left empty: ${process} — ${country.trim() || "the country"}.`}
          />
          {roles.length > 0 && (
            <fieldset className="role-picks">
              <legend>Lanes to bring along</legend>
              <p className="field__help">
                Lane names only. Untick the roles this country doesn't have.
              </p>
              {roles.map((r) => (
                <CheckboxField
                  key={r.id}
                  label={r.name}
                  checked={!leftBehind.has(r.id)}
                  onChange={(c) => tick(r.id, c)}
                />
              ))}
            </fieldset>
          )}
          {formError && (
            <p className="field__error" role="alert">
              {formError}
            </p>
          )}
        </form>
      </Dialog>
    </Card>
  );
}
