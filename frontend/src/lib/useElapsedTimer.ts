"use client";

import { useEffect, useState } from "react";

/**
 * Seconds elapsed since `active` turned true (0 when inactive). Ticks every second —
 * gives honest "this is working, Xs" feedback on long AI calls (refill, discover)
 * where there's no per-stage progress to stream.
 */
export function useElapsedTimer(active: boolean): number {
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!active) {
      setSeconds(0);
      return;
    }
    const started = Date.now();
    setSeconds(0);
    const t = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(t);
  }, [active]);

  return seconds;
}