import { SelectField } from "../common";
import { plural } from "../../lib/format";
import type { ResourceRow } from "../../lib/systemRecords";
import "./system.css";

export const UNKNOWN_ROLE = "unknown";

export interface RoleMapTableProps {
  resources: readonly ResourceRow[];
  roles: readonly { id: string; name: string }[];
  /** User ID → role ID, `UNKNOWN_ROLE`, or "" while not chosen. */
  value: Record<string, string>;
  onChange: (userId: string, choice: string) => void;
}

/**
 * Wizard step 3: each user ID in the file to a role (constraint 24). The IDs are shown only here,
 * while the file is held in memory; they are converted to roles on import and never stored.
 */
export function RoleMapTable({ resources, roles, value, onChange }: RoleMapTableProps) {
  const options = [
    { value: "", label: "Choose a role" },
    ...roles.map((r) => ({ value: r.id, label: r.name })),
    { value: UNKNOWN_ROLE, label: "Unknown role" },
  ];
  const left = resources.filter((r) => !value[r.value]).length;
  return (
    <div className="log-roles">
      <p className="log-roles__note">
        <strong>These are not stored.</strong> The user IDs below are held in memory only while you map them; the
        import keeps the role and forgets the ID. No figure is ever shown per person.
      </p>
      {resources.length === 0 ? (
        <p>The file has no user ID column, so there is nothing to map.</p>
      ) : (
        <ul className="log-roles__list">
          {resources.map((r) => (
            <li key={r.value} className="log-roles__row">
              <SelectField
                label={`User ID ${r.value}`}
                help={plural(r.events, "event")}
                value={value[r.value] ?? ""}
                options={options}
                onChange={(choice) => onChange(r.value, choice)}
              />
            </li>
          ))}
        </ul>
      )}
      {left > 0 && (
        <p className="log-roles__left" role="status">
          Choose a role or Unknown role for every user ID ({left} left).
        </p>
      )}
    </div>
  );
}
