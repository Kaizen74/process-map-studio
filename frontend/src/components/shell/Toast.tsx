import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ToastContext, type ShowToast } from "./toastContext";
import "./shell.css";

/** Success toasts last 4 seconds, bottom-left (PRD §5.3). */
export const TOAST_MS = 4000;

interface ToastItem {
  id: number;
  message: string;
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const timers = useRef<number[]>([]);

  const show = useCallback<ShowToast>((message) => {
    const id = nextId.current++;
    setToasts((current) => [...current, { id, message }]);
    timers.current.push(
      window.setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), TOAST_MS),
    );
  }, []);

  useEffect(() => () => timers.current.forEach((timer) => window.clearTimeout(timer)), []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className="toast">
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
