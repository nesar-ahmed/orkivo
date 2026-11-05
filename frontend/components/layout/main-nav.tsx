"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { SignOutButton } from "@/features/auth";
import { PLATFORM_ROLE_BADGES, PLATFORM_ROLE_LABELS } from "@/features/users";
import { cn } from "@/lib/utils/cn";
import type { User } from "@/types/auth";

interface NavItem {
  readonly href: string;
  readonly label: string;
}

/**
 * Navigation and identity for the signed-in shell.
 *
 * A client component because an active link needs the current path. Which items
 * are *shown* follows the platform role the backend sent, but that is presentation
 * only: `/app/platform/tenants` answers 403 for everyone else whatever this list
 * says, and no navigation item can grant access to a company --- that is decided
 * per tenant by the API (architecture doc 8.2, section 5).
 */
export function MainNav({ user }: { user: User }) {
  const pathname = usePathname();

  const items: NavItem[] = [
    { href: "/app/dashboard", label: "Tasks" },
    { href: "/app/workspaces", label: "Workspaces" },
    { href: "/app/profile", label: "Profile" },
    ...(user.platform_role === "operator"
      ? [{ href: "/app/platform/tenants", label: "Platform" }]
      : []),
  ];

  return (
    <>
      <nav aria-label="Main" className="ml-auto flex items-center gap-1 text-sm">
        {items.map((item) => {
          const active = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 font-medium hover:bg-muted",
                active ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="ml-2 flex items-center gap-2 border-l border-border pl-3">
        <span className="hidden max-w-40 truncate text-xs text-muted-foreground sm:inline">
          {user.display_name}
        </span>
        <Badge variant={PLATFORM_ROLE_BADGES[user.platform_role]}>
          {PLATFORM_ROLE_LABELS[user.platform_role]}
        </Badge>
      </div>

      <SignOutButton />
    </>
  );
}
