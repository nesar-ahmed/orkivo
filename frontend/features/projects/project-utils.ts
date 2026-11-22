/** Presentation helpers for the projects feature. */

import { workspacePath } from "@/features/workspaces/workspace-utils";
import type { Workspace } from "@/types/workspace";

/** Mirrors the backend's name limit, so the field never accepts what the API refuses. */
export const PROJECT_NAME_MAX_LENGTH = 120;
export const PROJECT_DESCRIPTION_MAX_LENGTH = 2000;

/** The workspace's tasks, filtered to one project: where "open tasks" leads. */
export function projectTasksHref(
  workspace: Pick<Workspace, "kind" | "slug">,
  projectId: string,
): string {
  return `${workspacePath(workspace, "tasks")}?project=${encodeURIComponent(projectId)}`;
}
