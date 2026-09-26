import { useQuery } from "@tanstack/react-query";
import { getHealth } from "../api/system";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: getHealth, staleTime: Infinity });
}
