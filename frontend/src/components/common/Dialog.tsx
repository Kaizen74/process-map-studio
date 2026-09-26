import { useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useFocusTrap } from "./useFocusTrap";
import "./common.css";

export interface DialogProps {
  open: boolean;
  title: string;
  /** Plain-language description, e.g. exactly what will be removed. */
  description?: ReactNode;
  /** Buttons, e.g. Cancel and the confirming action. */
  actions: ReactNode;
  onClose: () => void;
  children?: ReactNode;
}

/** A modal dialog: traps focus, closes on Esc or a click outside, returns focus on close. */
export function Dialog({ open, title, description, actions, onClose, children }: DialogProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descriptionId = useId();
  useFocusTrap(ref, open, onClose);
  if (!open) return null;
  return createPortal(
    <div
      className="overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={ref}
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
      >
        <h2 id={titleId} className="dialog__title">
          {title}
        </h2>
        {description && <p id={descriptionId}>{description}</p>}
        {children}
        <div className="dialog__actions">{actions}</div>
      </div>
    </div>,
    document.body,
  );
}
