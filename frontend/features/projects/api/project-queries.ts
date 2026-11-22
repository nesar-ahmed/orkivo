/**
 * Typed read operations against the projects API.
 *
 * Lists are read *from a workspace*; the backend answers "not found" for a
 * workspace the caller is not in, and for a project outside the caller's tenants.
 */

import { apiClient } from "@/lib/api/client";
import type { Project, ProjectListResponse } from "@/types/project";

export interface ProjectListParams {
  page?: number;
  page_size?: number;
}

export function fetchProjects(
  workspaceId: string,
  params: ProjectListParams = {},
  cookie?: string,
): Promise<ProjectListResponse> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient.get<ProjectListResponse>(
    `/workspaces/${workspaceId}/projects${suffix}`,
    cookie ? { cookie } : {},
  );
}

export function fetchProject(projectId: string, cookie?: string): Promise<Project> {
  return apiClient.get<Project>(`/projects/${projectId}`, cookie ? { cookie } : {});
}
