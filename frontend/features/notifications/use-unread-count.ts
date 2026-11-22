"use client";

/**
 * The unread badge, kept fresh without real-time transport.
 *
 * Polls the cheap count endpoint every 30 seconds while the tab is visible, and
 * again whenever the tab regains focus or the page changes --- which is when a
 * person would expect to see something new. A hidden tab does not poll at all.
 * The layout's server render supplies the first value, so the badge never
 * flashes from empty.
 */

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { fetchUnreadCount } from "@/features/notifications/api/notification-queries";

const POLL_INTERVAL_MS = 30_000;

export function useUnreadCount(initial: number): {
  count: number;
  refresh: () => Promise<void>;
  setCount: (count: number) => void;
} {
  const [count, setCount] = useState(initial);
  const pathname = usePathname();

  const refresh = useCallback(async () => {
    try {
      setCount((await fetchUnreadCount()).count);
    } catch {
      // A failed poll keeps the last known count; the next one may succeed.
    }
  }, []);

  useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    const timer = window.setInterval(tick, POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", tick);
    window.addEventListener("focus", tick);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", tick);
      window.removeEventListener("focus", tick);
    };
  }, [refresh]);

  // A navigation is a natural moment to catch up (e.g. after opening a task).
  // The answer is ignored if the person has already moved on again.
  useEffect(() => {
    let current = true;
    fetchUnreadCount()
      .then((result) => {
        if (current) setCount(result.count);
      })
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [pathname]);

  return { count, refresh, setCount };
}
