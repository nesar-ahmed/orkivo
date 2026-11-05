import type { ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { User } from "@/types/auth";
import type { Workspace } from "@/types/workspace";
import { Breadcrumbs } from "./breadcrumbs";
import { MobileNav } from "./mobile-nav";
import { SidebarNav } from "./sidebar-nav";

/**
 * Application shell: a sidebar with the workspace switcher and navigation, a top
 * bar with breadcrumbs, and the page (architecture doc 8.1).
 *
 * Below the `lg` breakpoint the sidebar becomes a drawer behind the menu button,
 * so nothing is pushed off-screen on a phone. The account is the one the `/app`
 * layout just confirmed with the API, so what a person sees here and what the
 * backend authorizes cannot disagree.
 */
export function AppShell({
  user,
  workspaces,
  children,
}: {
  user: User;
  workspaces: Workspace[] | null;
  children: ReactNode;
}) {
  return (
    <TooltipProvider>
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground focus:not-sr-only focus:fixed focus:top-3 focus:left-3"
      >
        Skip to content
      </a>
      <div className="flex min-h-screen w-full">
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-border bg-sidebar lg:block">
          <SidebarNav user={user} workspaces={workspaces} />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border bg-background/85 px-3 backdrop-blur sm:px-6">
            <MobileNav user={user} workspaces={workspaces} />
            <Breadcrumbs workspaces={workspaces ?? []} />
          </header>

          <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
            {children}
          </main>
        </div>
      </div>
    </TooltipProvider>
  );
}
