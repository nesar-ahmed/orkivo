"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { workspacePath, type WorkspaceSection } from "@/features/workspaces/workspace-utils";
import { cn } from "@/lib/utils/cn";
import type { Workspace } from "@/types/workspace";

const SECTION_LABELS: Record<WorkspaceSection, string> = {
  tasks: "Tasks",
  people: "People",
};

/**
 * The pages inside one workspace. A client component only because the active tab
 * follows the current path. A private workspace has one member, so it has no
 * people page to link to.
 */
export function WorkspaceTabs({ workspace }: { workspace: Workspace }) {
  const pathname = usePathname();
  const sections: WorkspaceSection[] =
    workspace.kind === "team" ? ["tasks", "people"] : ["tasks"];

  return (
    <nav aria-label={`${workspace.name} sections`} className="flex gap-1 border-b border-border">
      {sections.map((section) => {
        const href = workspacePath(workspace, section);
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={section}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium",
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
