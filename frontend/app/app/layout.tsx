import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { isUnauthenticated, readCurrentUserOnce } from "@/features/auth";
import { getServerCookieHeader } from "@/lib/api/server-cookies";
import type { User } from "@/types/auth";

export const dynamic = "force-dynamic";

/**
 * The authenticated surface, guarded by the only signal that counts.
 *
 * Wraps every route under `/app`. The proxy redirect is cosmetic; this is the
 * front door. Asking the API who the caller is --- rather than trusting that a
 * cookie merely exists --- means a revoked, rotated or expired session cannot
 * render a shell at all, and the role used for navigation comes from the
 * database (architecture doc 8.2 and section 9).
 *
 * The redirect here drops the deep link on purpose. This branch is "cookie
 * present but no longer valid", which `SessionRecovery` on the login screen
 * answers by renewing and returning to the product root; the proxy is what
 * carries `?next=` for a visitor with no session at all.
 */
export default async function AppLayout({ children }: { children: ReactNode }) {
  const cookie = await getServerCookieHeader();
  let user: User;

  try {
    user = await readCurrentUserOnce(cookie);
  } catch (error) {
    if (isUnauthenticated(error)) redirect("/login");
    // Anything else is a genuine fault (the API is unreachable, say). Say so in
    // the error boundary instead of telling people to sign in again.
    throw error;
  }

  return <AppShell user={user}>{children}</AppShell>;
}
