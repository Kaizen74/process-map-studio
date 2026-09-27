import { useCallback, useRef, useState } from "react";

/** Smallest scale "Fit" goes to (PRD §5.5); below it the map scrolls instead. */
export const MIN_FIT = 0.5;

export function fitScale(containerWidth: number, canvasWidth: number): number {
  if (containerWidth <= 0 || canvasWidth <= 0) return 1;
  return Math.max(MIN_FIT, Math.min(1, containerWidth / canvasWidth));
}

/**
 * Fit = min(1, container width / canvas width), floor 0.5, kept up to date as the window resizes.
 * Returns a callback ref for the map's box: measuring starts when the box appears (not when the
 * screen first shows its loading state) and stops when it goes.
 */
export function useFitScale(canvasWidth: number): [(element: HTMLElement | null) => void, number] {
  const [width, setWidth] = useState(0);
  const observer = useRef<ResizeObserver | null>(null);
  const ref = useCallback((element: HTMLElement | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!element) return;
    setWidth(element.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    observer.current = new ResizeObserver(() => setWidth(element.clientWidth));
    observer.current.observe(element);
  }, []);
  return [ref, fitScale(width, canvasWidth)];
}
