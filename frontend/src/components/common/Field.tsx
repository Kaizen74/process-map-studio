import { useId, useState, type ChangeEvent, type KeyboardEvent, type ReactNode } from "react";
import "./common.css";

interface FieldShellProps {
  label: string;
  help?: ReactNode | undefined;
  error?: string | null | undefined;
  children: (ids: { control: string; describedBy: string | undefined }) => ReactNode;
}

function FieldShell({ label, help, error, children }: FieldShellProps) {
  const control = useId();
  const helpId = useId();
  const errorId = useId();
  const describedBy = [help ? helpId : "", error ? errorId : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div className={["field", error ? "field--invalid" : ""].filter(Boolean).join(" ")}>
      <label className="field__label" htmlFor={control}>
        {label}
      </label>
      {children({ control, describedBy })}
      {help && (
        <span id={helpId} className="field__help">
          {help}
        </span>
      )}
      {error && (
        <span id={errorId} className="field__error">
          {error}
        </span>
      )}
    </div>
  );
}

export interface TextFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "password";
  help?: ReactNode;
  error?: string | null;
  placeholder?: string;
  mono?: boolean;
  autoComplete?: string;
}

/** A labelled text input. Errors are announced and linked to the field. */
export function TextField({
  label,
  value,
  onChange,
  type = "text",
  help,
  error,
  placeholder,
  mono = false,
  autoComplete = "off",
}: TextFieldProps) {
  return (
    <FieldShell label={label} help={help} error={error}>
      {({ control, describedBy }) => (
        <input
          id={control}
          className={["field__control", mono ? "field__control--mono" : ""].filter(Boolean).join(" ")}
          type={type}
          value={value}
          placeholder={placeholder}
          autoComplete={autoComplete}
          spellCheck={false}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
        />
      )}
    </FieldShell>
  );
}

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectFieldProps {
  label: string;
  value: string;
  options: readonly SelectOption[];
  onChange: (value: string) => void;
  help?: ReactNode;
  error?: string | null;
}

export function SelectField({ label, value, options, onChange, help, error }: SelectFieldProps) {
  return (
    <FieldShell label={label} help={help} error={error}>
      {({ control, describedBy }) => (
        <select
          id={control}
          className="field__control"
          value={value}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(event) => onChange(event.target.value)}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )}
    </FieldShell>
  );
}

export interface CheckboxFieldProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  help?: ReactNode;
}

export function CheckboxField({ label, checked, onChange, help }: CheckboxFieldProps) {
  const id = useId();
  const helpId = useId();
  return (
    <div className="field">
      <span className="checkbox">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          aria-describedby={help ? helpId : undefined}
          onChange={(event) => onChange(event.target.checked)}
        />
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
      </span>
      {help && (
        <span id={helpId} className="field__help">
          {help}
        </span>
      )}
    </div>
  );
}

export interface TextAreaFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  help?: ReactNode;
  error?: string | null;
  rows?: number;
}

/** A labelled multi-line text box. */
export function TextAreaField({ label, value, onChange, help, error, rows = 3 }: TextAreaFieldProps) {
  return (
    <FieldShell label={label} help={help} error={error}>
      {({ control, describedBy }) => (
        <textarea
          id={control}
          className="field__control field__control--area"
          value={value}
          rows={rows}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </FieldShell>
  );
}

export interface ChipFieldProps {
  label: string;
  values: readonly string[];
  onChange: (values: string[]) => void;
  help?: ReactNode;
  error?: string | null;
  placeholder?: string;
}

/**
 * A list of short entries shown as chips. Type and press Enter (or a comma) to add; each chip has
 * its own Remove button. Duplicates (ignoring case) and blank entries are ignored.
 */
export function ChipField({ label, values, onChange, help, error, placeholder }: ChipFieldProps) {
  const [draft, setDraft] = useState("");

  function add() {
    const item = draft.replace(/\s+/g, " ").trim();
    setDraft("");
    if (!item || values.some((v) => v.toLowerCase() === item.toLowerCase())) return;
    onChange([...values, item]);
  }

  return (
    <FieldShell label={label} help={help} error={error}>
      {({ control, describedBy }) => (
        <div className="chip-field">
          {values.length > 0 && (
            <ul className="chip-field__list" aria-label={`${label} added`}>
              {values.map((value) => (
                <li key={value} className="chip chip--neutral chip-field__chip">
                  <span>{value}</span>
                  <button
                    type="button"
                    className="chip-field__remove"
                    aria-label={`Remove ${value}`}
                    onClick={() => onChange(values.filter((v) => v !== value))}
                  >
                    <span aria-hidden="true">×</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <input
            id={control}
            className="field__control"
            value={draft}
            placeholder={placeholder ?? "Type and press Enter"}
            autoComplete="off"
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            onChange={(event) => setDraft(event.target.value.replace(/,/g, ""))}
            onKeyDown={(event: KeyboardEvent<HTMLInputElement>) => {
              if (event.key === "Enter" || event.key === ",") {
                event.preventDefault();
                add();
              }
            }}
            onBlur={add}
          />
        </div>
      )}
    </FieldShell>
  );
}
