"use client";

import { useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronsUpDown, LogOut, Monitor, Moon, Sun, UserRound } from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useSignOut } from "@/features/auth/components/use-sign-out";
import { PLATFORM_ROLE_LABELS } from "@/features/users/user-utils";
import {
  applyThemePreference,
  readThemePreference,
  type ThemePreference,
} from "@/lib/theme/theme";
import type { User } from "@/types/auth";

const THEME_LABELS: Record<ThemePreference, string> = {
  system: "System",
  light: "Light",
  dark: "Dark",
};
const THEME_ICONS: Record<ThemePreference, typeof Sun> = {
  system: Monitor,
  light: Sun,
  dark: Moon,
};

// The preference lives in a cookie; this keeps the menu's checkmark in sync.
const THEME_EVENT = "orkivo-theme";
function subscribe(onChange: () => void): () => void {
  window.addEventListener(THEME_EVENT, onChange);
  return () => window.removeEventListener(THEME_EVENT, onChange);
}

/**
 * The signed-in account: who it is, the theme, and signing out.
 *
 * The platform role is shown because it decides whether the Platform console
 * appears; it says nothing about any company.
 */
export function UserMenu({ user }: { user: User }) {
  const router = useRouter();
  const { signOut, isSigningOut } = useSignOut();
  const theme = useSyncExternalStore(subscribe, readThemePreference, () => "system" as const);

  function chooseTheme(value: string) {
    applyThemePreference(value as ThemePreference);
    window.dispatchEvent(new Event(THEME_EVENT));
    // Re-render on the server too, so the layout's `data-theme` matches the cookie.
    router.refresh();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full min-w-0 items-center gap-2.5 rounded-lg p-1.5 text-left transition-colors hover:bg-muted data-[state=open]:bg-muted">
        <Avatar name={user.display_name} seed={user.id} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-foreground">
            {user.display_name}
          </span>
          <span className="block truncate text-xs text-muted-foreground">
            {PLATFORM_ROLE_LABELS[user.platform_role]}
          </span>
        </span>
        <span className="sr-only">, account menu</span>
        <ChevronsUpDown aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
      </DropdownMenuTrigger>

      <DropdownMenuContent side="top" align="start" className="w-64">
        <DropdownMenuLabel className="normal-case tracking-normal">
          <span className="block truncate text-sm font-medium text-foreground">
            {user.display_name}
          </span>
          <span className="block truncate text-xs font-normal">{user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link href="/app/profile">
            <UserRound aria-hidden="true" />
            Profile & invitations
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Theme</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={theme} onValueChange={chooseTheme}>
          {(Object.keys(THEME_LABELS) as ThemePreference[]).map((value) => {
            const Icon = THEME_ICONS[value];
            return (
              <DropdownMenuRadioItem key={value} value={value}>
                <Icon aria-hidden="true" />
                {THEME_LABELS[value]}
              </DropdownMenuRadioItem>
            );
          })}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={signOut} disabled={isSigningOut}>
          <LogOut aria-hidden="true" />
          {isSigningOut ? "Signing out…" : "Sign out"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
