"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { TIMEZONE_COOKIE, TIMEZONE_COOKIE_MAX_AGE } from "@/lib/time/viewer-day";

/**
 * Tell the server which time zone this browser is in, so pages it renders count
 * "overdue" and "due today" from the viewer's own day (`lib/time/viewer-day.ts`).
 *
 * Renders nothing. When the cookie is missing or out of date --- the first visit,
 * or a laptop that travelled --- it is written and the page re-rendered once, so
 * the numbers on screen match the viewer's calendar straight away.
 */
export function TimezoneSync() {
  const router = useRouter();

  useEffect(() => {
    const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (!zone) return;
    const current = document.cookie
      .split("; ")
      .find((pair) => pair.startsWith(`${TIMEZONE_COOKIE}=`))
      ?.slice(TIMEZONE_COOKIE.length + 1);
    if (current && decodeURIComponent(current) === zone) return;
    document.cookie = `${TIMEZONE_COOKIE}=${encodeURIComponent(zone)}; path=/; max-age=${TIMEZONE_COOKIE_MAX_AGE}; samesite=lax`;
    router.refresh();
  }, [router]);

  return null;
}
