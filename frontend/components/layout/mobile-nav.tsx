"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import type { User } from "@/types/auth";
import type { Workspace } from "@/types/workspace";
import { SidebarNav } from "./sidebar-nav";

/**
 * The sidebar, as a drawer, below the desktop breakpoint. Opened by the menu
 * button in the top bar; closes on any navigation, like the switcher.
 */
export function MobileNav({
  user,
  workspaces,
}: {
  user: User;
  workspaces: readonly Workspace[] | null;
}) {
  const pathname = usePathname();
  const [openOnPath, setOpenOnPath] = useState<string | null>(null);
  const open = openOnPath === pathname;

  return (
    <Sheet open={open} onOpenChange={(next) => setOpenOnPath(next ? pathname : null)}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open navigation">
          <Menu aria-hidden="true" />
        </Button>
      </SheetTrigger>
      <SheetContent title="Navigation">
        <SidebarNav user={user} workspaces={workspaces} onNavigate={() => setOpenOnPath(null)} />
      </SheetContent>
    </Sheet>
  );
}
