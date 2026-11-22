"use client";

import { useEffect } from "react";
import { rememberRecent, type RecentItem } from "@/features/command-palette/recent-items";

/**
 * Note that the person opened something, so the command palette offers it under
 * "Recent" next time. Renders nothing; rendered by pages worth coming back to (a
 * task's own page). Opening from the palette itself is remembered there.
 */
export function RememberVisit({ userId, item }: { userId: string | null; item: RecentItem }) {
  const { id, label } = item;
  useEffect(() => {
    if (userId) rememberRecent(userId, item);
    // Once per thing and its name, not on every re-render of the page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, id, label]);
  return null;
}
