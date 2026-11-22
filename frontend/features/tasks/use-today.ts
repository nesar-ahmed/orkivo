"use client";

/**
 * What "today" is, on the viewer's own clock.
 *
 * The server renders before it knows the viewer's timezone, so it renders with its
 * own UTC day, and the browser moves to its local day straight after hydration ---
 * through `useSyncExternalStore`, which is exactly the hand-over React supports
 * without a hydration mismatch. After that, the value turns over at local
 * midnight, and again whenever the tab comes back into view (a laptop that slept
 * through midnight). A list grouped by "overdue / today" and a calendar's
 * highlighted day therefore never go stale on a tab left open.
 */

import { useSyncExternalStore } from "react";
import { localIsoDate } from "@/features/tasks/task-dates";

function subscribe(onChange: () => void): () => void {
  let timer = 0;
  const schedule = () => {
    const now = new Date();
    const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    // A second past midnight, so the new day has certainly begun.
    timer = window.setTimeout(() => {
      onChange();
      schedule();
    }, midnight.getTime() - now.getTime() + 1_000);
  };
  const onVisible = () => {
    if (document.visibilityState === "visible") onChange();
  };
  schedule();
  document.addEventListener("visibilitychange", onVisible);
  return () => {
    window.clearTimeout(timer);
    document.removeEventListener("visibilitychange", onVisible);
  };
}

const localToday = () => localIsoDate(new Date());
const serverToday = () => new Date().toISOString().slice(0, 10);

/** Today as `YYYY-MM-DD` on the viewer's clock (UTC during the server render). */
export function useToday(): string {
  return useSyncExternalStore(subscribe, localToday, serverToday);
}
