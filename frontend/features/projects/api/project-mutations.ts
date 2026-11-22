/**
 * Typed write operations against the projects API.
 *
 * A project is created *in* a workspace; after that it is addressed by its own id.
 * Deleting one keeps its tasks: they stay in the workspace, without a project.
 */

import { ApiError, apiClient } from "@/lib/api/client";
import type { Project, ProjectCreateInput, ProjectUpdateInput } from "@/types/project";

export function createProject(workspaceId: string, input: ProjectCreateInput): Promise<Project> {
  return apiClient.post<Project>(`/workspaces/${workspaceId}/projects`, input);
}

/**
 * Rename or describe a project. Pass the `version` you read: if a colleague saved
 * in between, the API refuses with 409 `PROJECT_CONFLICT`.
 */
export function updateProject(projectId: string, input: ProjectUpdateInput): Promise<Project> {
  return apiClient.patch<Project>(`/projects/${projectId}`, input);
}

/** Delete a project (owners and admins); with `version`, only if unchanged since read. */
export function deleteProject(projectId: string, version?: number): Promise<void> {
  const suffix = version !== undefined ? `?version=${version}` : "";
  return apiClient.delete(`/projects/${projectId}${suffix}`);
}

/** Whether an API error means "another project here already has this name". */
export function isProjectNameInUse(error: unknown): boolean {
  return error instanceof ApiError && error.code === "PROJECT_NAME_IN_USE";
}

/** Whether an API error means "someone else changed this project first". */
export function isProjectConflict(error: unknown): boolean {
  return error instanceof ApiError && error.code === "PROJECT_CONFLICT";
}
