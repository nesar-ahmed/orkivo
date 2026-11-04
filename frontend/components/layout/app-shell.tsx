import type { ReactNode } from "react";
import Link from "next/link";

/**
 * Application shell: branding, navigation and page container.
 * Shared layouts own the shell (architecture doc 8.1).
 */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center gap-3 px-4">
          <span
            aria-hidden="true"
            className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-sm font-bold text-primary-foreground"
          >
            O
          </span>
          <span className="text-sm font-semibold tracking-tight">Orkivo</span>
          <span className="hidden text-xs text-muted-foreground sm:inline">
            Think. Organize. Build.
          </span>
          <nav aria-label="Main" className="ml-auto flex items-center gap-1 text-sm">
            <Link
              href="/"
              className="rounded-md px-3 py-1.5 font-medium text-foreground hover:bg-muted"
              aria-current="page"
            >
              Tasks
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>

      <footer className="border-t border-border py-4 text-center text-xs text-muted-foreground">
        Orkivo baseline — one module (tasks) today, more on the roadmap.
      </footer>
    </div>
  );
}
