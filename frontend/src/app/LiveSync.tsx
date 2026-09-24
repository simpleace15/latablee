"use client";

import { useEffect, useRef } from "react";
import { api } from "@/lib/api";

/**
 * Live sync poller: every 15s, ask the backend for integration events newer
 * than the last seen id and dispatch a window CustomEvent when the plan or a
 * shopping list changed. Pages listen for "latablee:changed" and reload their
 * data — so a partner's edits show up without a manual refresh.
 */
export default function LiveSync() {
  const lastId = useRef(0);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let stopped = false;

    async function tick() {
      if (stopped) return;
      try {
        const res = await api.eventsSince(lastId.current);
        if (res.events?.length) {
          const changed = res.events.filter(
            (e) => e.event === "meal_plan_updated" || e.event === "shopping_list_updated",
          );
          lastId.current = res.events[res.events.length - 1].id;
          if (changed.length > 0) {
            window.dispatchEvent(new CustomEvent("latablee:changed"));
          }
        }
      } catch {
        /* offline or token refresh mid-flight — next tick retries */
      }
    }

    void tick();
    timer.current = setInterval(() => void tick(), 15000);
    return () => {
      stopped = true;
      if (timer.current) clearInterval(timer.current);
    };
  }, []);

  return null;
}