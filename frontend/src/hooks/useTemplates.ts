import { useQuery } from "@tanstack/react-query";
import { listTemplatePlans } from "../api/templates";

/** The standard interview templates; they never change while the app runs. */
export function useTemplatePlans() {
  return useQuery({ queryKey: ["templates", "interview"], queryFn: listTemplatePlans, staleTime: Infinity });
}
