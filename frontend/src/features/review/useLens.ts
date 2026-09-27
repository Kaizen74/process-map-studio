import { useState } from "react";
import { LENS_STORAGE_KEY, isLens, type Lens } from "../../lib/lens";

function stored(): Lens {
  try {
    const value = window.localStorage.getItem(LENS_STORAGE_KEY);
    return isLens(value) ? value : "plain";
  } catch {
    return "plain"; // storage blocked: the default lens still works
  }
}

/** The map lens, remembered in this browser (PRD §5.5 `pms.lens`). */
export function useLens(): [Lens, (lens: Lens) => void] {
  const [lens, setLens] = useState<Lens>(stored);
  function choose(next: Lens) {
    setLens(next);
    try {
      window.localStorage.setItem(LENS_STORAGE_KEY, next);
    } catch {
      // Not remembered, but the choice still applies now.
    }
  }
  return [lens, choose];
}
