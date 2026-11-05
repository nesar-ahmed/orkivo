"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight } from "lucide-react";
import { findWorkspaceForPath, workspacePath } from "@/features/workspaces/workspace-utils";
import type { Workspace } from "@/types/workspace";

interface Crumb {
  readonly label: string;
  readonly href?: string;
}

const STATIC_TRAILS: ReadonlyArray<readonly [RegExp, Crumb[]]> = [
  [/^\/app\/workspaces(\/|$)/, [{ label: "Workspaces" }]],
  [/^\/app\/profile(\/|$)/, [{ label: "Invitations & profile" }]],
  [/^\/app\/platform\/tenants/, [{ label: "Platform", href: "/app/platform/tenants" }, { label: "Tenants" }]],
  [/^\/app\/platform\/accounts/, [{ label: "Platform", href: "/app/platform/tenants" }, { label: "Accounts" }]],
];

/**
 * Where am I: `Acme Robotics › Tasks › Task`.
 *
 * Built from the URL and the caller's own memberships only. A company the caller
 * is not in gets no crumb at all, so the 404 page for it reads exactly like the
 * one for a company that does not exist.
 */
export function Breadcrumbs({ workspaces }: { workspaces: readonly Workspace[] }) {
  const pathname = usePathname();
  const trail = crumbsFor(pathname, workspaces);
  if (trail.length === 0) return null;

  return (
    <nav aria-label="Breadcrumb" className="min-w-0">
      <ol className="flex min-w-0 items-center gap-1 text-sm">
        {trail.map((crumb, index) => {
          const last = index === trail.length - 1;
          return (
            <li key={`${crumb.label}-${index}`} className="flex min-w-0 items-center gap-1">
              {index > 0 ? (
                <ChevronRight aria-hidden="true" className="size-3.5 shrink-0 text-muted-foreground" />
              ) : null}
              {crumb.href && !last ? (
                <Link
                  href={crumb.href}
                  className="truncate text-muted-foreground transition-colors hover:text-foreground"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span
                  aria-current={last ? "page" : undefined}
                  className="truncate font-medium text-foreground"
                >
                  {crumb.label}
                </span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function crumbsFor(pathname: string, workspaces: readonly Workspace[]): Crumb[] {
  for (const [pattern, trail] of STATIC_TRAILS) {
    if (pattern.test(pathname)) return trail;
  }
  const workspace = findWorkspaceForPath(pathname, workspaces);
  if (!workspace) return [];

  const root: Crumb = {
    label: workspace.kind === "personal" ? "Private" : workspace.name,
    href: workspacePath(workspace, "tasks"),
  };
  if (/\/people(\/|$)/.test(pathname)) return [root, { label: "People" }];
  if (/\/tasks\/[^/]+/.test(pathname)) {
    return [root, { label: "Tasks", href: workspacePath(workspace, "tasks") }, { label: "Task" }];
  }
  return [root, { label: "Tasks" }];
}
