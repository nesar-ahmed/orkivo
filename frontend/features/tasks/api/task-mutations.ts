/** Typed write operations against the tasks API. */

import { apiClient } from "@/lib/api/client";
import type { Task, TaskCreateInput, TaskUpdateInput } from "@/types/task";

export function createTask(input: TaskCreateInput): Promise<Task> {
  return apiClient.post<Task>("/tasks", input);
}

export function updateTask(taskId: string, input: TaskUpdateInput): Promise<Task> {
  return apiClient.patch<Task>(`/tasks/${taskId}`, input);
}

export function deleteTask(taskId: string): Promise<void> {
  return apiClient.delete(`/tasks/${taskId}`);
}
