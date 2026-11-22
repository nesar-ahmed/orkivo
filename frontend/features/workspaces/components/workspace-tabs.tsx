"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  workspacePath,
  workspaceSections,
  type WorkspaceSection,
} from "@/features/workspaces/workspace-utils";
import { cn } from "@/lib/utils/cn";
import type { Workspace } from "@/types/workspace";

const SECTION_LABELS: Record<WorkspaceSection, string> = {
  overview: "Overview",
  tasks: "Tasks",
  projects: "Projects",
  labels: "Labels",
  activity: "Activity",
  people: "People",
  automations: "Automations",
};

/**
 * The pages inside one workspace. A client component only because the active tab
 * follows the current path. A private workspace has one member, so it has no
 * people page to link to.
 *
 * On a narrow screen the row scrolls sideways on its own rather than widening
 * the page, and the active tab is scrolled into view.
 */
export function WorkspaceTabs({ workspace }: { workspace: Workspace }) {
  const pathname = usePathname();
  const sections = workspaceSections(workspace.kind);

  return (
    <nav
      aria-label={`${workspace.name} sections`}
      className="flex gap-1 overflow-x-auto border-b border-border [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {sections.map((section) => {
        const href = workspacePath(workspace, section);
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={section}
            href={href}
            aria-current={active ? "page" : undefined}
            ref={active ? revealTab : undefined}
            className={cn(
              "-mb-px shrink-0 border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap",
              active
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {SECTION_LABELS[section]}
          </Link>
        );
      })}
    </nav>
  );
}

/**
 * Scroll the tab row --- and only the row, never the page --- so the active tab is
 * visible. Left alone when it already is, so a re-render never fights a person
 * who scrolled the row themselves.
 */
function revealTab(tab: HTMLAnchorElement | null): void {
  const row = tab?.parentElement;
  if (!tab || !row) return;
  const start = tab.offsetLeft - row.offsetLeft;
  const end = start + tab.offsetWidth;
  if (start < row.scrollLeft || end > row.scrollLeft + row.clientWidth) {
    row.scrollLeft = Math.max(0, start - 16);
  }
}
