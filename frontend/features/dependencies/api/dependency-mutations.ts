/**
 * Typed write operations against the task dependencies API.
 *
 * A link is always written from the *waiting* task's side: "this task is blocked
 * by that one". Adding answers with both directions again, so a screen redraws
 * from one response.
 */

import { apiClient } from "@/lib/api/client";
import type { TaskDependencies } from "@/types/dependency";

/** Make `waitingTaskId` wait on `blockingTaskId` (same workspace only). */
export function addBlocker(
  waitingTaskId: string,
  blockingTaskId: string,
): Promise<TaskDependencies> {
  return apiClient.post<TaskDependencies>(`/tasks/${waitingTaskId}/dependencies`, {
    blocking_task_id: blockingTaskId,
  });
}

/** `waitingTaskId` no longer waits on `blockingTaskId`. */
export function removeBlocker(waitingTaskId: string, blockingTaskId: string): Promise<void> {
  return apiClient.delete(`/tasks/${waitingTaskId}/dependencies/${blockingTaskId}`);
}
