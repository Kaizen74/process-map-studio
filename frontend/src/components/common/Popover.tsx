import { useEffect, useId, useRef, type ReactNode } from "react";
import { Button } from "./Button";
import { useFocusTrap } from "./useFocusTrap";
import "./common.css";

export interface PopoverProps {
  open: boolean;
  title: string;
  onClose: () => void;
  /** Which edge of the anchor the popover lines up with. */
  align?: "start" | "end";
  children: ReactNode;
}

/**
 * A popover shown below its anchor. Place it inside an element with class "popover-anchor".
 * Traps focus, closes on Close, Esc or a click outside, and returns focus (PRD §5.7.9, §5.10).
 */
export function Popover({ open, title, onClose, align = "start", children }: PopoverProps) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(ref, open, onClose);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      const anchor = ref.current?.parentElement;
      if (anchor && event.target instanceof Node && !anchor.contains(event.target)) onClose();
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      ref={ref}
      className={`popover popover--${align}`}
      role="dialog"
      aria-labelledby={titleId}
      tabIndex={-1}
    >
      <div className="popover__header">
        <h2 id={titleId} className="popover__title">
          {title}
        </h2>
        <Button variant="link" onClick={onClose}>
          Close
        </Button>
      </div>
      {children}
    </div>
  );
}
