import { useState } from "react";
import { Button } from "./Button";
import "./common.css";

export interface ErrorStateProps {
  /** What happened, in plain language. */
  title: string;
  /** What it affects and what to do next. */
  message: string;
  /** Error code and request or job ID for bug reports ("Copy details"). */
  details?: string;
  onRetry?: () => void;
}

/** The standard error pattern (PRD §5.3): plain message, next step, Copy details. Never a stack trace. */
export function ErrorState({ title, message, details, onRetry }: ErrorStateProps) {
  const [copied, setCopied] = useState<"idle" | "copied" | "failed">("idle");

  async function copyDetails() {
    try {
      await navigator.clipboard.writeText(details ?? "");
      setCopied("copied");
    } catch {
      setCopied("failed");
    }
  }

  return (
    <div className="state-message state-message--error" role="alert">
      <p className="state-message__title">{title}</p>
      <p>{message}</p>
      <div className="state-message__actions">
        {onRetry && (
          <Button variant="primary" onClick={onRetry}>
            Try again
          </Button>
        )}
        {details && <Button onClick={() => void copyDetails()}>Copy details</Button>}
        <span className="state-message__note" aria-live="polite">
          {copied === "copied" && "Details copied. Paste them into the Bug-fix prompt."}
          {copied === "failed" && `Copy didn't work. The details are: ${details ?? ""}`}
        </span>
      </div>
    </div>
  );
}
