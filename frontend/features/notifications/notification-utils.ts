/** Presentation helpers for notifications. */

import { taskPath } from "@/features/workspaces/workspace-utils";
import type { AppNotification, NotificationKind } from "@/types/notification";

const VERBS: Record<NotificationKind, string> = {
  assigned: "assigned you",
  commented: "commented on",
  mentioned: "mentioned you in",
  unblocked: "finished the last task blocking",
  completed: "completed",
};

/** "Olive Owner assigned you", to be followed by the task's title. */
export function notificationHeadline(notification: AppNotification): string {
  const who = notification.actor?.display_name ?? "A former member";
  return `${who} ${VERBS[notification.kind]}`;
}

/** Where a notification leads: the task, in the workspace that holds it. */
export function notificationHref(notification: AppNotification): string {
  return taskPath(notification.workspace, notification.task.id);
}

/** The badge text: the number, or "9+" beyond that. */
export function badgeCount(count: number): string {
  return count > 9 ? "9+" : String(count);
}
