import Link from "next/link";
import { FolderKanban, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { DeleteProjectButton } from "@/features/projects/components/delete-project-button";
import { ProjectFormDialog } from "@/features/projects/components/project-form-dialog";
import { projectTasksHref } from "@/features/projects/project-utils";
import { formatAccountDate } from "@/features/users/user-utils";
import { hasCapability, isShared, readOnlyReason } from "@/features/workspaces/workspace-utils";
import type { ProjectSummary } from "@/types/project";
import type { Workspace } from "@/types/workspace";

/**
 * A workspace's projects: what each is for, how much work it holds, and who
 * opened it.
 *
 * Which controls appear follows the workspace's `capabilities` from the backend's
 * access policy: `manage_projects` (owners, admins and managers) to rename and describe,
 * `manage` (owners and admins) to delete. For members and viewers, and in view
 * mode (a suspended company), neither is present, so the table is read-only
 * without restating that rule here. Each action is still
 * authorized per request (architecture doc 8.2).
 */
export function ProjectTable({
  workspace,
  projects,
}: {
  workspace: Workspace;
  projects: readonly ProjectSummary[];
}) {
  const canEdit = hasCapability(workspace, "manage_projects");
  const canDelete = hasCapability(workspace, "manage");
  const shared = isShared(workspace.kind);

  if (projects.length === 0) {
    return (
      <EmptyState
        icon={<FolderKanban />}
        title="No projects yet"
        description={
          canEdit
            ? "Group related tasks into a project, then filter or group the board by it."
            : readOnlyReason(workspace) === "suspended"
              ? "There are no projects here, and this workspace is in view mode."
              : "There are no projects here yet."
        }
      />
    );
  }

  return (
    // `relative`: see MemberTable --- it keeps screen-reader-only text inside the
    // scroll container on narrow screens.
    <div className="relative overflow-x-auto rounded-xl border border-border bg-card shadow-xs">
      <table className="w-full min-w-[36rem] text-left text-sm">
        <caption className="sr-only">
          Projects in this workspace, how many of their tasks are open, and who created them.
        </caption>
        <thead className="border-b border-border text-xs uppercase tracking-wide text-muted-foreground">
          <tr>
            <th scope="col" className="px-4 py-3 font-medium">
              Project
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Tasks
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              Created
            </th>
            <th scope="col" className="px-4 py-3 font-medium">
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {projects.map((project) => (
            <tr key={project.id}>
              <th scope="row" className="max-w-80 px-4 py-3 font-normal">
                <Link
                  href={projectTasksHref(workspace, project.id)}
                  className="flex items-center gap-2 font-medium text-foreground hover:text-primary"
                >
                  <FolderKanban aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">{project.name}</span>
                </Link>
                {project.description ? (
                  <span className="mt-0.5 line-clamp-2 block pl-6 text-xs text-muted-foreground">
                    {project.description}
                  </span>
                ) : null}
              </th>
              <td className="px-4 py-3 align-top text-xs whitespace-nowrap text-muted-foreground">
                <span className="font-medium text-foreground">{project.open_task_count}</span> open
                <span aria-hidden="true"> · </span>
                <span className="sr-only">, </span>
                {project.task_count} total
              </td>
              <td className="px-4 py-3 align-top text-xs text-muted-foreground">
                <span className="block text-foreground">
                  {project.created_by?.display_name ?? "A former member"}
                </span>
                {formatAccountDate(project.created_at)}
              </td>
              <td className="px-4 py-3 text-right align-top">
                <div className="flex justify-end gap-1">
                  {canEdit ? (
                    <ProjectFormDialog
                      workspaceId={workspace.id}
                      project={project}
                      shared={shared}
                      trigger={
                        <Button variant="ghost" size="icon-sm" aria-label={`Edit ${project.name}`}>
                          <Pencil aria-hidden="true" />
                        </Button>
                      }
                    />
                  ) : null}
                  {canDelete ? <DeleteProjectButton project={project} /> : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
