/** Typed read operations against the tasks API. */

import { apiClient } from "@/lib/api/client";
import type { Task, TaskListResponse, TaskStatus } from "@/types/task";

export interface TaskListParams {
  status?: TaskStatus;
  page?: number;
  page_size?: number;
  search?: string;
}

export function fetchTasks(
  params: TaskListParams = {},
  cookie?: string,
): Promise<TaskListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.search) query.set("search", params.search);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return apiClient.get<TaskListResponse>(`/tasks${suffix}`, cookie ? { cookie } : {});
}

export function fetchTask(taskId: string, cookie?: string): Promise<Task> {
  return apiClient.get<Task>(`/tasks/${taskId}`, cookie ? { cookie } : {});
}
