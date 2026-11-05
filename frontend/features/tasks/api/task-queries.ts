/**
 * Typed read operations against the tasks API.
 *
 * Lists are always read *from a workspace*: the board shows one tenant at a time,
 * and the backend answers "not found" for a workspace the caller is not in.
 */

import { apiClient } from "@/lib/api/client";
import type { Task, TaskListResponse, TaskPriority, TaskStatus } from "@/types/task";

export interface TaskListParams {
  status?: TaskStatus;
  priority?: TaskPriority;
  page?: number;
  page_size?: number;
  search?: string;
}

export function fetchTasks(
  workspaceId: string,
  params: TaskListParams = {},
  cookie?: string,
): Promise<TaskListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.priority) query.set("priority", params.priority);
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.search) query.set("search", params.search);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient.get<TaskListResponse>(
    `/workspaces/${workspaceId}/tasks${suffix}`,
    cookie ? { cookie } : {},
  );
}

export function fetchTask(taskId: string, cookie?: string): Promise<Task> {
  return apiClient.get<Task>(`/tasks/${taskId}`, cookie ? { cookie } : {});
}
