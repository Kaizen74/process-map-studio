import type { ButtonHTMLAttributes, ReactNode } from "react";
import "./common.css";

export type ButtonVariant = "primary" | "secondary" | "danger" | "link";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  children: ReactNode;
}

/** A button. Defaults to type="button" so it never submits a form by accident. */
export function Button({ variant = "secondary", className, type, children, ...rest }: ButtonProps) {
  const classes = ["btn", `btn--${variant}`, className].filter(Boolean).join(" ");
  return (
    <button type={type ?? "button"} className={classes} {...rest}>
      {children}
    </button>
  );
}
