/**
 * Restores a session that only looks signed out.
 *
 * The access cookie expires after 15 minutes while the refresh session lasts 30
 * days, and only the browser can spend the latter --- so this is where a
 * server-rendered page that read "no session" gets one more chance before the
 * visitor is asked for a password. It runs once, from the login screen, and
 * never handles token material.
 *
 * The one-shot mark is what stops the loop: a renewal the dashboard still
 * refuses (an API host mismatch, say) would otherwise bounce between this screen
 * and `/` forever.
 */

"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { renewSession } from "@/features/auth/api/auth-api";
import { safeRedirectTarget } from "@/features/auth/auth-policy";
import { waitForOtherTab } from "@/lib/api/client";

const ATTEMPT_KEY = "orkivo.session-recovery";
/** Long enough to cover one bounce, short enough not to strand a real user. */
const ATTEMPT_WINDOW_MS = 30_000;

function hasAttemptedRecently(): boolean {
  if (typeof window === "undefined") return true;
  try {
    const previous = Number(window.sessionStorage.getItem(ATTEMPT_KEY) ?? 0);
    return Number.isFinite(previous) && Date.now() - previous < ATTEMPT_WINDOW_MS;
  } catch {
    // No sessionStorage (private mode): one attempt per load is still bounded by
    // the dashboard's own redirect, so allow it.
    return false;
  }
}

function markAttempted(): void {
  try {
    window.sessionStorage.setItem(ATTEMPT_KEY, String(Date.now()));
  } catch {
    // Nothing to mark; the loop guard degrades to "this load only".
  }
}

/** Forget the one-shot mark, so a later sign-out can attempt recovery again. */
export function clearSessionRecoveryAttempt(): void {
  try {
    window.sessionStorage.removeItem(ATTEMPT_KEY);
  } catch {
    // Nothing to clear without storage.
  }
}

/** ``next`` is the path the guard was heading for; it is validated on use. */
export function SessionRecovery({ next }: { next?: string }) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  // Decided once, on mount: a re-render must not restart the attempt.
  const [shouldTry] = useState(() => !hasAttemptedRecently());

  useEffect(() => {
    if (!shouldTry) return;
    markAttempted();

    startTransition(async () => {
      const outcome = await renewSession();

      if (outcome === "renewed") {
        router.replace(safeRedirectTarget(next));
        router.refresh();
      } else if (outcome === "deferred") {
        // Another tab is rotating right now. Wait for its cookie, then re-render:
        // the guard sends us on if the session turned out to be live.
        await waitForOtherTab();
        router.refresh();
      }
      // ``failed``: there is nothing to restore, so the form below is the answer.
    });
  }, [next, router, startTransition, shouldTry]);

  if (!isPending) return null;

  return (
    <p
      role="status"
      aria-live="polite"
      className="mb-4 rounded-md border border-border bg-muted px-3 py-2 text-xs text-muted-foreground"
    >
      Restoring your session…
    </p>
  );
}
