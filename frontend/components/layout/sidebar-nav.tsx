"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Building2, CheckSquare, Inbox, ShieldCheck, Users } from "lucide-react";
import { type ReactNode } from "react";
import { WorkspaceSwitcher } from "@/features/workspaces/components/workspace-switcher";
import { findWorkspaceForPath, workspacePath } from "@/features/workspaces/workspace-utils";
import { cn } from "@/lib/utils/cn";
import type { User } from "@/types/auth";
import type { Workspace } from "@/types/workspace";
import { UserMenu } from "./user-menu";

interface NavItem {
  readonly href: string;
  readonly label: string;
  readonly icon: ReactNode;
  readonly active: boolean;
}

/**
 * Everything the sidebar shows: the workspace switcher, the current workspace's
 * sections, the product-wide pages, and the account menu.
 *
 * The workspace section follows the URL, so inside a company it is that
 * company's board and people; anywhere else it is the private workspace. Which
 * items appear follows what the backend sent (the platform role, the workspace
 * kind) --- presentation only, since every page is authorized by the API
 * (architecture doc 8.2).
 *
 * Used twice: in the desktop sidebar and inside the mobile drawer.
 */
export function SidebarNav({
  user,
  workspaces,
  onNavigate,
}: {
  user: User;
  workspaces: readonly Workspace[] | null;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const list = workspaces ?? [];
  const current =
    findWorkspaceForPath(pathname, list) ?? list.find((w) => w.kind === "personal") ?? null;
  const under = (prefix: string) => pathname === prefix || pathname.startsWith(`${prefix}/`);

  const workspaceItems: NavItem[] = current
    ? [
        {
          href: workspacePath(current, "tasks"),
          label: "Tasks",
          icon: <CheckSquare />,
          active: under(workspacePath(current, "tasks")),
        },
        ...(current.kind === "team"
          ? [
              {
                href: workspacePath(current, "people"),
                label: "People",
                icon: <Users />,
                active: under(workspacePath(current, "people")),
              },
            ]
          : []),
      ]
    : [];

  const generalItems: NavItem[] = [
    {
      href: "/app/workspaces",
      label: "Workspaces",
      icon: <Building2 />,
      active: under("/app/workspaces"),
    },
    { href: "/app/profile", label: "Invitations & profile", icon: <Inbox />, active: under("/app/profile") },
    ...(user.platform_role === "operator"
      ? [
          {
            href: "/app/platform/tenants",
            label: "Platform",
            icon: <ShieldCheck />,
            active: under("/app/platform"),
          },
        ]
      : []),
  ];

  return (
    <div className="flex h-full flex-col gap-4 p-3">
      <Link
        href="/app/personal/tasks"
        onClick={onNavigate}
        className="flex items-center gap-2.5 rounded-md px-1.5 py-1"
      >
        <span
          aria-hidden="true"
          className="flex size-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary-hover text-sm font-bold text-primary-foreground shadow-xs"
        >
          O
        </span>
        <span className="text-sm font-semibold tracking-tight">Orkivo</span>
      </Link>

      {workspaces ? (
        <WorkspaceSwitcher workspaces={workspaces} />
      ) : (
        <Link href="/app/workspaces" className="px-2 text-xs font-medium text-muted-foreground">
          Workspaces
        </Link>
      )}

      <nav aria-label="Main" className="flex flex-1 flex-col gap-5 overflow-y-auto">
        {workspaceItems.length > 0 ? (
          <NavSection
            title={current?.kind === "team" ? current.name : "Private workspace"}
            items={workspaceItems}
            onNavigate={onNavigate}
          />
        ) : null}
        <NavSection title="Orkivo" items={generalItems} onNavigate={onNavigate} />
      </nav>

      <UserMenu user={user} />
    </div>
  );
}

function NavSection({
  title,
  items,
  onNavigate,
}: {
  title: string;
  items: NavItem[];
  onNavigate?: () => void;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <p className="truncate px-2 pb-1 text-[0.7rem] font-medium tracking-wide text-muted-foreground uppercase">
        {title}
      </p>
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          onClick={onNavigate}
          aria-current={item.active ? "page" : undefined}
          className={cn(
            "flex h-8 items-center gap-2.5 rounded-md px-2 text-sm transition-colors [&_svg]:size-4",
            item.active
              ? "bg-card font-medium text-foreground shadow-xs ring-1 ring-border"
              : "text-muted-foreground hover:bg-muted hover:text-foreground",
          )}
        >
          {item.icon}
          {item.label}
        </Link>
      ))}
    </div>
  );
}
