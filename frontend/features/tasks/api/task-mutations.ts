/**
 * Typed write operations against the tasks API.
 *
 * A task is created *in* a workspace; after that it is addressed by its own id,
 * which stays valid wherever the workspace is linked from.
 */

import { ApiError, apiClient } from "@/lib/api/client";
import type { Task, TaskCreateInput, TaskUpdateInput } from "@/types/task";

export function createTask(workspaceId: string, input: TaskCreateInput): Promise<Task> {
  return apiClient.post<Task>(`/workspaces/${workspaceId}/tasks`, input);
}

/**
 * Change a task. Pass the `version` you read: if a colleague saved in between, the
 * API refuses with 409 `TASK_CONFLICT` instead of silently undoing their change.
 */
export function updateTask(taskId: string, input: TaskUpdateInput): Promise<Task> {
  return apiClient.patch<Task>(`/tasks/${taskId}`, input);
}

/** Delete a task; with `version`, only if nobody changed it since it was read. */
export function deleteTask(taskId: string, version?: number): Promise<void> {
  const suffix = version !== undefined ? `?version=${version}` : "";
  return apiClient.delete(`/tasks/${taskId}${suffix}`);
}

/** Whether an API error means "someone else changed this task first". */
export function isTaskConflict(error: unknown): boolean {
  return error instanceof ApiError && error.code === "TASK_CONFLICT";
}
