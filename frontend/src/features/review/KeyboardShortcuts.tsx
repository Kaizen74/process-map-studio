import { useEffect } from "react";

/** Listens for key presses on the whole page while mounted (the Review keyboard, PRD §5.8). */
export function KeyboardShortcuts({ onKey }: { onKey: (event: KeyboardEvent) => void }) {
  useEffect(() => {
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onKey]);
  return null;
}
