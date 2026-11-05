"use client";

import { Button } from "@/components/ui/button";
import { useSignOut } from "@/features/auth/components/use-sign-out";

/** A plain sign-out button, for screens outside the app shell's user menu. */
export function SignOutButton() {
  const { signOut, isSigningOut } = useSignOut();
  return (
    <Button variant="ghost" size="sm" onClick={signOut} disabled={isSigningOut}>
      {isSigningOut ? "Signing out…" : "Sign out"}
    </Button>
  );
}
