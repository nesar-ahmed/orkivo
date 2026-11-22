/**
 * Typed read operations against the task dependencies API.
 *
 * Read through the task: a task the caller cannot reach answers "not found", so
 * its dependencies are never visible on their own.
 */

import { apiClient } from "@/lib/api/client";
import type { TaskDependencies } from "@/types/dependency";

export function fetchDependencies(taskId: string, cookie?: string): Promise<TaskDependencies> {
  return apiClient.get<TaskDependencies>(
    `/tasks/${taskId}/dependencies`,
    cookie ? { cookie } : {},
  );
}
