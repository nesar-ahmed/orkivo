/** Typed writes: marking notifications read, and following a task. */

import { apiClient } from "@/lib/api/client";
import type { Watchers } from "@/types/notification";

export function markNotificationRead(notificationId: string): Promise<void> {
  return apiClient.post<void>(`/notifications/${notificationId}/read`, undefined);
}

export function markAllNotificationsRead(): Promise<void> {
  return apiClient.post<void>("/notifications/read-all", undefined);
}

/** Follow a task: hear about its comments. Already following is fine. */
export function watchTask(taskId: string): Promise<Watchers> {
  return apiClient.post<Watchers>(`/tasks/${taskId}/watchers`, undefined);
}

/** Stop following a task. Not following is fine. */
export function unwatchTask(taskId: string): Promise<void> {
  return apiClient.delete(`/tasks/${taskId}/watchers`);
}
