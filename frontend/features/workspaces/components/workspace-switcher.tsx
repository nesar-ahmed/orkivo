"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Check, ChevronsUpDown, Lock, Plus, Settings2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  WORKSPACE_ROLE_LABELS,
  findWorkspaceForPath,
  workspacePath,
  workspaceRefFromPath,
} from "@/features/workspaces/workspace-utils";
import { cn } from "@/lib/utils/cn";
import type { Workspace } from "@/types/workspace";

/**
 * Move between the private workspace and the companies the caller belongs to.
 *
 * An ARIA menu (Radix): arrow keys move, typing a letter jumps to a company,
 * Escape closes and returns focus. Every entry is still a real link, so it can be
 * opened in a new tab. The list is the caller's memberships as the API returned
 * them --- it can only ever offer workspaces the backend would let them open.
 *
 * Switching keeps the section when it can: from one company's people page to
 * another's people page, and to the tasks board otherwise. The open state
 * remembers *which page* it was opened on, so any navigation --- including the
 * browser's Back button --- closes it.
 */
export function WorkspaceSwitcher({
  workspaces,
  className,
}: {
  workspaces: readonly Workspace[];
  className?: string;
}) {
  const pathname = usePathname();
  const [openOnPath, setOpenOnPath] = useState<string | null>(null);
  const open = openOnPath === pathname;

  const current = findWorkspaceForPath(pathname, workspaces);
  const section = workspaceRefFromPath(pathname)?.section ?? "tasks";
  const personal = workspaces.filter((workspace) => workspace.kind === "personal");
  const companies = workspaces.filter((workspace) => workspace.kind === "team");

  return (
    <DropdownMenu open={open} onOpenChange={(next) => setOpenOnPath(next ? pathname : null)}>
      <DropdownMenuTrigger
        className={cn(
          "group flex h-10 w-full min-w-0 items-center gap-2.5 rounded-lg border border-border bg-card px-2",
          "text-left text-sm font-medium text-card-foreground shadow-xs transition-colors",
          "hover:border-border-strong hover:bg-muted data-[state=open]:bg-muted",
          className,
        )}
      >
        <WorkspaceMark workspace={current} />
        <span className="min-w-0 flex-1 truncate">
          {current ? switcherLabel(current) : "Choose a workspace"}
        </span>
        <span className="sr-only">, switch workspace</span>
        <ChevronsUpDown aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
      </DropdownMenuTrigger>

      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuGroup>
          <DropdownMenuLabel>Private</DropdownMenuLabel>
          {personal.map((workspace) => (
            <SwitcherItem
              key={workspace.id}
              workspace={workspace}
              href={workspacePath(workspace)}
              current={current?.id === workspace.id}
            />
          ))}
        </DropdownMenuGroup>

        <DropdownMenuGroup>
          <DropdownMenuLabel>Companies</DropdownMenuLabel>
          {companies.length > 0 ? (
            companies.map((workspace) => (
              <SwitcherItem
                key={workspace.id}
                workspace={workspace}
                href={workspacePath(workspace, section)}
                current={current?.id === workspace.id}
              />
            ))
          ) : (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">You are not in a company yet.</p>
          )}
        </DropdownMenuGroup>

        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/app/workspaces#create">
            <Plus aria-hidden="true" />
            Create a company
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link href="/app/workspaces">
            <Settings2 aria-hidden="true" />
            Manage workspaces
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function SwitcherItem({
  workspace,
  href,
  current,
}: {
  workspace: Workspace;
  href: string;
  current: boolean;
}) {
  return (
    <DropdownMenuItem asChild>
      <Link href={href} aria-current={current ? "page" : undefined} className="py-2">
        <WorkspaceMark workspace={workspace} />
        <span className="min-w-0 flex-1">
          <span className="block truncate font-medium">{switcherLabel(workspace)}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {workspace.kind === "personal"
              ? "Only you"
              : `/${workspace.slug} · ${WORKSPACE_ROLE_LABELS[workspace.my_role]}`}
          </span>
        </span>
        {workspace.status !== "active" ? <Badge variant="warning">View only</Badge> : null}
        {current ? <Check aria-hidden="true" className="text-primary" /> : null}
      </Link>
    </DropdownMenuItem>
  );
}

/** A small initial tile, so companies are told apart before their names are read. */
export function WorkspaceMark({
  workspace,
  className,
}: {
  workspace: Workspace | null;
  className?: string;
}) {
  if (workspace?.kind === "personal") {
    return (
      <span
        aria-hidden="true"
        className={cn(
          "flex size-6 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground",
          className,
        )}
      >
        <Lock className="size-3.5" />
      </span>
    );
  }
  const letter = workspace ? switcherLabel(workspace).charAt(0).toUpperCase() : "?";
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-6 shrink-0 items-center justify-center rounded-md text-xs font-bold",
        workspace ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
        className,
      )}
    >
      {letter}
    </span>
  );
}

function switcherLabel(workspace: Workspace): string {
  return workspace.kind === "personal" ? "Private" : workspace.name;
}
