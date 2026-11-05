"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { logout } from "@/features/auth/api/auth-api";
import { clearSessionRecoveryAttempt } from "@/features/auth/components/session-recovery";

/**
 * Ends the session. The backend revokes the refresh session and expires both
 * cookies; a failed call must not strand the user in an apparently signed-in
 * shell, so the redirect happens either way.
 */
export function useSignOut(): { signOut: () => void; isSigningOut: boolean } {
  const router = useRouter();
  const [isSigningOut, startTransition] = useTransition();

  function signOut() {
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

  return { signOut, isSigningOut };
}
