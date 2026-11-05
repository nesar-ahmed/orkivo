import type { ReactNode } from "react";
import Link from "next/link";

import { MainNav } from "@/components/layout/main-nav";
import type { User } from "@/types/auth";

/**
 * Application shell: branding, navigation and page container.
 * Shared layouts own the shell (architecture doc 8.1).
 *
 * The account is the one the dashboard layout just confirmed with the API, so
 * what a person sees here and what the backend authorizes cannot disagree.
 */
export function AppShell({ user, children }: { user: User; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center gap-3 px-4">
          <Link
            href="/app/dashboard"
            className="flex items-center gap-3 rounded-md hover:opacity-90"
            aria-label="Orkivo — go to the tasks dashboard"
          >
            <span
              aria-hidden="true"
              className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground"
            >
              O
            </span>
            <span className="text-sm font-semibold tracking-tight">Orkivo</span>
          </Link>
          <span className="hidden text-xs text-muted-foreground sm:inline">
            Think. Organize. Build.
          </span>

          <MainNav user={user} />
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>

      <footer className="border-t border-border py-4 text-center text-xs text-muted-foreground">
        Orkivo — tasks, accounts and roles are yours; the backend decides what any
        of them may do.
      </footer>
    </div>
  );
}
