"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { logout } from "@/features/auth/api/auth-api";
import { clearSessionRecoveryAttempt } from "@/features/auth/components/session-recovery";

/**
 * Ends the session. The backend revokes the refresh session and expires both
 * cookies; a failed call must not strand the user in an apparently signed-in
 * shell, so the redirect happens either way.
 */
export function SignOutButton() {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  function handleSignOut() {
    startTransition(async () => {
      try {
        await logout();
      } finally {
        // A deliberate sign-out is not a loop, so the login screen's one-shot
        // recovery guard starts clean for whoever signs in next.
        clearSessionRecoveryAttempt();
        router.replace("/login");
        router.refresh();
      }
    });
  }

  return (
    <Button variant="ghost" size="sm" onClick={handleSignOut} disabled={isPending}>
      {isPending ? "Signing out…" : "Sign out"}
    </Button>
  );
}
