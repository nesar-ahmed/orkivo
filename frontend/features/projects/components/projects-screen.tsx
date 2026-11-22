import { Lock, Plus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Pagination } from "@/components/ui/pagination";
import { ProjectFormDialog } from "@/features/projects/components/project-form-dialog";
import { ProjectTable } from "@/features/projects/components/project-table";
import {
  hasCapability,
  isShared,
  readOnlyReason,
  workspacePath,
} from "@/features/workspaces/workspace-utils";
import type { ProjectListResponse } from "@/types/project";
import type { Workspace } from "@/types/workspace";

/**
 * One workspace's projects: the list, and creating a new one.
 *
 * The same screen serves the private workspace and every company, like the task
 * board. What differs is what the backend says the caller may do there: without
 * `manage_projects` (members and viewers, or anyone in view mode) nothing can be
 * added or changed.
 */
export function ProjectsScreen({
  workspace,
  projects,
}: {
  workspace: Workspace;
  projects: ProjectListResponse;
}) {
  const canEdit = hasCapability(workspace, "manage_projects");

  return (
    <section aria-labelledby="projects-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="projects-heading" className="text-lg font-semibold tracking-tight">
          Projects
        </h2>
        <Badge variant="neutral">{projects.total}</Badge>
        {canEdit ? (
          <div className="ml-auto">
            <ProjectFormDialog
              workspaceId={workspace.id}
              shared={isShared(workspace.kind)}
              trigger={
                <Button size="sm">
                  <Plus aria-hidden="true" />
                  New project
                </Button>
              }
            />
          </div>
        ) : null}
      </div>

      {canEdit ? null : (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Lock aria-hidden="true" className="size-4" />
          {readOnlyReason(workspace) === "suspended"
            ? "View mode: projects can be read, but not added or changed."
            : "Your role lets you read projects and use them on tasks, but not add or change them."}
        </p>
      )}

      <ProjectTable workspace={workspace} projects={projects.items} />
      <Pagination
        page={projects.page}
        pages={projects.pages}
        total={projects.total}
        basePath={workspacePath(workspace, "projects")}
        noun="projects"
      />
    </section>
  );
}
