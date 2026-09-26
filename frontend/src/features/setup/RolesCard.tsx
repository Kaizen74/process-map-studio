import { useId, useState, type DragEvent, type FormEvent } from "react";
import type { Role } from "../../api/types";
import { Button, Card, CheckboxField, Chip, ChipField, EmptyState, TextField } from "../../components/common";
import { useToast } from "../../components/shell";
import { useCreateRole, useUpdateRole } from "../../hooks/useRoles";
import { messageOf } from "../../lib/errors";
import { validateRoleName } from "../../lib/validation";

const EMPTY_ROLES = "Roles are also created from your sources when the draft runs. Add any you already know.";
const SYSTEM_HELP = "A system or tool rather than a person, for example the departure control system.";
const ALIAS_HELP = "Other names the sources use for this role, for example “LC”.";

interface RoleFormProps {
  initial?: Role;
  submitLabel: string;
  pending: boolean;
  serverError: string | null;
  onSubmit: (values: { name: string; aliases: string[]; is_system: boolean }) => void;
  onCancel?: () => void;
}

function RoleForm({ initial, submitLabel, pending, serverError, onSubmit, onCancel }: RoleFormProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [aliases, setAliases] = useState<string[]>(initial?.aliases ?? []);
  const [isSystem, setIsSystem] = useState(initial?.is_system ?? false);
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent) {
    event.preventDefault();
    const problem = validateRoleName(name);
    setError(problem);
    if (problem || pending) return;
    onSubmit({ name: name.trim(), aliases, is_system: isSystem });
  }

  return (
    <form className="role-form" onSubmit={submit} noValidate>
      <TextField label="Role name" value={name} onChange={setName} error={error ?? serverError} />
      <ChipField label="Aliases" values={aliases} onChange={setAliases} help={ALIAS_HELP} />
      {!initial && <CheckboxField label="System role" checked={isSystem} onChange={setIsSystem} help={SYSTEM_HELP} />}
      <div className="setup-form__actions">
        <Button variant={initial ? "primary" : "secondary"} type="submit">
          {pending ? "Saving…" : submitLabel}
        </Button>
        {onCancel && <Button onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  );
}

/** Roles and lanes (PRD §5.4 Setup): lane order, aliases, system roles, add role, lane preview. */
export function RolesCard({ engagementId, roles }: { engagementId: string; roles: readonly Role[] }) {
  const create = useCreateRole(engagementId);
  const update = useUpdateRole(engagementId);
  const toast = useToast();
  const [editing, setEditing] = useState<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [addError, setAddError] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);
  // A new key after a successful add gives a fresh, empty form; a rejected add keeps what was typed.
  const [addFormKey, setAddFormKey] = useState(0);

  function patch(role: Role, change: Parameters<typeof update.mutate>[0]["patch"], done?: string) {
    setRowError(null);
    update.mutate(
      { id: role.id, patch: change },
      {
        onSuccess: () => {
          if (done) toast(done);
        },
        onError: (e) => setRowError(messageOf(e)),
      },
    );
  }

  function move(role: Role, lane: number) {
    patch(role, { lane_order: lane }, `${role.name} moved to lane ${lane}.`);
  }

  function onDrop(event: DragEvent, target: Role) {
    event.preventDefault();
    const dragged = roles.find((r) => r.id === dragging);
    setDragging(null);
    if (dragged && dragged.id !== target.id && target.lane_order) move(dragged, target.lane_order);
  }

  return (
    <Card
      title="Roles and lanes"
      description="Each role becomes a lane on the map, in this order from the top. Drag a role, or use Move up and Move down."
    >
      <div className="stack">
        {roles.length === 0 ? (
          <EmptyState message={EMPTY_ROLES} />
        ) : (
          <ol className="role-list" aria-label="Roles in lane order">
            {roles.map((role, index) => (
              <li
                key={role.id}
                className={["role-row", dragging === role.id ? "role-row--dragging" : ""].filter(Boolean).join(" ")}
                draggable={editing !== role.id}
                onDragStart={(event) => {
                  event.dataTransfer.effectAllowed = "move";
                  event.dataTransfer.setData("text/plain", role.id);
                  setDragging(role.id);
                }}
                onDragEnd={() => setDragging(null)}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => onDrop(event, role)}
              >
                {editing === role.id ? (
                  <RoleForm
                    initial={role}
                    submitLabel="Save role"
                    pending={update.isPending}
                    serverError={editError}
                    onCancel={() => {
                      setEditing(null);
                      setEditError(null);
                    }}
                    onSubmit={(values) => {
                      setEditError(null);
                      update.mutate(
                        { id: role.id, patch: { name: values.name, aliases: values.aliases } },
                        {
                          onSuccess: () => {
                            setEditing(null);
                            toast("Role saved.");
                          },
                          onError: (e) => setEditError(messageOf(e)),
                        },
                      );
                    }}
                  />
                ) : (
                  <>
                    <span className="role-row__handle" aria-hidden="true">
                      ⋮⋮
                    </span>
                    <span className="role-row__lane mono" aria-hidden="true">
                      {role.lane_order ?? index + 1}
                    </span>
                    <div className="role-row__body">
                      <span className="role-row__name">
                        <span className="visually-hidden">Lane {role.lane_order ?? index + 1}: </span>
                        {role.name}
                      </span>
                      {role.aliases.length > 0 && (
                        <span className="role-row__aliases">
                          <span className="visually-hidden">Aliases: </span>
                          {role.aliases.map((alias) => (
                            <Chip key={alias}>{alias}</Chip>
                          ))}
                        </span>
                      )}
                      <CheckboxField
                        label="System role"
                        checked={role.is_system}
                        onChange={(checked) =>
                          patch(role, { is_system: checked }, checked ? `${role.name} is a system role.` : `${role.name} is a person's role.`)
                        }
                      />
                    </div>
                    <div className="role-row__actions">
                      {index > 0 && (
                        <Button variant="link" aria-label={`Move ${role.name} up`} onClick={() => move(role, index)}>
                          Move up
                        </Button>
                      )}
                      {index < roles.length - 1 && (
                        <Button
                          variant="link"
                          aria-label={`Move ${role.name} down`}
                          onClick={() => move(role, index + 2)}
                        >
                          Move down
                        </Button>
                      )}
                      <Button
                        variant="link"
                        aria-label={`Edit ${role.name}`}
                        onClick={() => {
                          setEditError(null);
                          setEditing(role.id);
                        }}
                      >
                        Edit
                      </Button>
                    </div>
                  </>
                )}
              </li>
            ))}
          </ol>
        )}
        {rowError && (
          <p className="field__error" role="alert">
            {rowError}
          </p>
        )}
        <div className="role-add">
          <h3 className="role-add__title">Add a role</h3>
          <RoleForm
            key={addFormKey}
            submitLabel="Add role"
            pending={create.isPending}
            serverError={addError}
            onSubmit={(values) => {
              setAddError(null);
              create.mutate(values, {
                onSuccess: (role) => {
                  setAddFormKey((k) => k + 1);
                  toast(`${role.name} added as lane ${role.lane_order ?? roles.length + 1}.`);
                },
                onError: (e) => setAddError(messageOf(e)),
              });
            }}
          />
        </div>
        {roles.length > 0 && <LanePreview roles={roles} />}
      </div>
    </Card>
  );
}

/** Mini lane preview: the order the lanes will have on the map (PRD §5.4 Setup). */
function LanePreview({ roles }: { roles: readonly Role[] }) {
  const captionId = useId();
  return (
    <figure className="lane-preview" aria-labelledby={captionId}>
      <figcaption id={captionId} className="lane-preview__caption">Lane preview, top to bottom</figcaption>
      <ol className="lane-preview__lanes">
        {roles.map((role) => (
          <li key={role.id} className={["lane-preview__lane", role.is_system ? "lane-preview__lane--system" : ""].join(" ")}>
            <span className="lane-preview__label">{role.name}</span>
            {role.is_system && <span className="lane-preview__tag">System</span>}
          </li>
        ))}
      </ol>
    </figure>
  );
}
