import { Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { WorkspaceMark } from "@/features/workspaces/components/workspace-switcher";
import { WorkspaceTabs } from "@/features/workspaces/components/workspace-tabs";
import {
  WORKSPACE_ROLE_BADGES,
  WORKSPACE_ROLE_LABELS,
  hasCapability,
} from "@/features/workspaces/workspace-utils";
import type { Workspace } from "@/types/workspace";

/**
 * Identity of the workspace a page belongs to: its name, its address, the
 * caller's standing in it, and its sections.
 *
 * Shared by the private workspace and every company, so "where am I, and who can
 * see what I type here?" is answered in the same place on every board. A
 * suspended company says so up front instead of letting a refused save be the
 * first sign of it.
 */
export function WorkspaceHeader({ workspace }: { workspace: Workspace }) {
  const viewMode = workspace.status === "suspended" && !hasCapability(workspace, "edit_content");
  const isCompany = workspace.kind === "team";

  return (
    <header className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <WorkspaceMark workspace={workspace} className="size-9 rounded-lg text-base" />
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold tracking-tight">
            {isCompany ? workspace.name : "Private workspace"}
          </h1>
          <p className="text-xs text-muted-foreground">
            {isCompany ? (
              <span className="font-mono">/{workspace.slug}</span>
            ) : (
              "Only you can see this workspace"
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {isCompany ? (
            <Badge variant={WORKSPACE_ROLE_BADGES[workspace.my_role]}>
              {WORKSPACE_ROLE_LABELS[workspace.my_role]}
            </Badge>
          ) : null}
          {viewMode ? (
            <Badge variant="warning">
              <Lock aria-hidden="true" />
              View only
            </Badge>
          ) : null}
        </div>
      </div>

      {viewMode ? (
        <div
          role="status"
          className="flex gap-3 rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
        >
          <Lock aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
          <p>
            <span className="font-semibold">View mode.</span>{" "}
            {isCompany
              ? "This company is suspended by the platform. Everyone in it can still see its tasks and people, but nothing can be added, changed or removed, and nobody can join or leave, until it is restored."
              : "This workspace is suspended by the platform. You can still see your tasks, but nothing can be changed until it is restored."}
          </p>
        </div>
      ) : null}

      <WorkspaceTabs workspace={workspace} />
    </header>
  );
}
