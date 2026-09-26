import { createContext, useContext } from "react";

export type ShowToast = (message: string) => void;

export const ToastContext = createContext<ShowToast>(() => undefined);

/** Show a short success message (saves and uploads; not navigation or selection). */
export function useToast(): ShowToast {
  return useContext(ToastContext);
}
