"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils/cn";

const LINKS = [
  { href: "/app/platform/tenants", label: "Tenants" },
  { href: "/app/platform/accounts", label: "Accounts" },
] as const;

/**
 * Sub-navigation for the platform console.
 *
 * Separate from the product navigation because it is a different kind of surface:
 * it crosses every tenant boundary rather than working inside one, and only
 * operators can reach it at all. The links are for orientation --- each page is
 * refused by the API for anyone else.
 */
export function PlatformNav() {
  const pathname = usePathname();

  return (
    <nav aria-label="Platform console" className="flex items-center gap-1 text-xs">
      {LINKS.map((link) => {
        const active = pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded-md px-3 py-1.5 font-medium",
              active ? "text-foreground hover:bg-muted" : "text-muted-foreground hover:bg-muted",
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
