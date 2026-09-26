import { useId, type ChangeEvent, type ReactNode } from "react";
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
